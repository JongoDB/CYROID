# Multi-Architecture Support Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable CYROID to run on both x86_64 and ARM64 architectures with native performance where possible and transparent x86 emulation with warnings where necessary.

**Architecture:** Add architecture detection layer, extend VM templates with ARM64 ISO URLs, modify Docker service to handle emulation flags, add frontend warnings for emulated VMs, and document platform support in README.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Alembic, React, TypeScript, Zustand, Tailwind CSS

---

## Task 1: Create Architecture Detection Utility

**Files:**
- Create: `backend/cyroid/utils/arch.py`

**Step 1: Create the architecture detection module**

```python
# backend/cyroid/utils/arch.py
"""
Architecture detection utilities for multi-platform support.

Provides detection of host CPU architecture and emulation requirements
for running x86 VMs on ARM hosts and vice versa.
"""
import platform
from typing import Literal

# Detect host architecture
_machine = platform.machine().lower()

IS_ARM: bool = _machine in ('arm64', 'aarch64')
IS_X86: bool = _machine in ('x86_64', 'amd64', 'x86')
HOST_ARCH: Literal['arm64', 'x86_64'] = 'arm64' if IS_ARM else 'x86_64'


def requires_emulation(target_arch: str) -> bool:
    """
    Check if running a target architecture requires emulation on this host.

    Args:
        target_arch: Target architecture ('x86_64', 'arm64', etc.)

    Returns:
        True if emulation is required, False if native execution
    """
    target = target_arch.lower()
    if target in ('x86_64', 'amd64', 'x86'):
        return IS_ARM
    if target in ('arm64', 'aarch64'):
        return IS_X86
    # Unknown architecture, assume no emulation needed
    return False


def get_system_info() -> dict:
    """
    Return system architecture information for API responses.

    Returns:
        Dictionary with host architecture details
    """
    return {
        "host_arch": HOST_ARCH,
        "is_arm": IS_ARM,
        "is_x86": IS_X86,
        "emulation_available": True,  # QEMU available via Docker
        "platform": platform.system().lower(),
        "machine": platform.machine(),
    }
```

**Step 2: Verify module imports correctly**

Run: `cd /Users/JonWFH/jondev/CYROID && docker compose exec api python -c "from cyroid.utils.arch import IS_ARM, HOST_ARCH; print(f'ARM: {IS_ARM}, Arch: {HOST_ARCH}')"`

Expected output showing architecture detection working.

**Step 3: Commit**

```bash
git add backend/cyroid/utils/arch.py
git commit -m "feat: add architecture detection utility for multi-platform support"
```

---

## Task 2: Create System Info API Endpoint

**Files:**
- Create: `backend/cyroid/api/system.py`
- Modify: `backend/cyroid/main.py`

**Step 1: Create the system API module**

```python
# backend/cyroid/api/system.py
"""
System information API endpoints.

Provides endpoints for retrieving host system information including
architecture details for frontend emulation warnings.
"""
from fastapi import APIRouter

from cyroid.utils.arch import get_system_info, HOST_ARCH, IS_ARM

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/info")
async def system_info():
    """
    Return host system information including architecture.

    Used by frontend to determine if VMs will run natively or emulated.
    No authentication required - this is public system metadata.
    """
    return get_system_info()


@router.get("/health")
async def system_health():
    """
    Detailed health check with architecture info.
    """
    return {
        "status": "healthy",
        "architecture": HOST_ARCH,
        "arm_host": IS_ARM,
    }
```

**Step 2: Register the router in main.py**

Add import at top with other imports:
```python
from cyroid.api.system import router as system_router
```

Add router registration after other routers:
```python
app.include_router(system_router, prefix="/api/v1")
```

**Step 3: Test the endpoint**

Run: `docker compose up -d && curl http://localhost/api/v1/system/info`

Expected: JSON response with architecture info

**Step 4: Commit**

```bash
git add backend/cyroid/api/system.py backend/cyroid/main.py
git commit -m "feat: add system info API endpoint for architecture detection"
```

---

## Task 3: Add Multi-Architecture Columns to Template Model

**Files:**
- Modify: `backend/cyroid/models/template.py`

**Step 1: Add new columns to VMTemplate model**

Add after `cached_iso_path` field (around line 84):

```python
    # Multi-architecture support
    iso_url_x86: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    iso_url_arm64: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    native_arch: Mapped[str] = mapped_column(String(20), default='x86_64')  # 'x86_64', 'arm64', or 'both'
```

**Step 2: Commit model changes**

```bash
git add backend/cyroid/models/template.py
git commit -m "feat: add multi-architecture columns to VMTemplate model"
```

---

## Task 4: Create Database Migration

**Files:**
- Create: `alembic/versions/xxxx_add_multi_arch_support.py`

**Step 1: Generate migration**

Run: `docker compose exec api alembic revision --autogenerate -m "add multi-architecture support to templates"`

**Step 2: Verify migration content**

The generated migration should include:
- `op.add_column('vm_templates', sa.Column('iso_url_x86', sa.String(500), nullable=True))`
- `op.add_column('vm_templates', sa.Column('iso_url_arm64', sa.String(500), nullable=True))`
- `op.add_column('vm_templates', sa.Column('native_arch', sa.String(20), server_default='x86_64'))`

**Step 3: Add data migration to copy existing iso_url values**

Edit the generated migration to add after the add_column statements in upgrade():

```python
    # Migrate existing iso_url to iso_url_x86 for existing templates
    op.execute("UPDATE vm_templates SET iso_url_x86 = base_image WHERE vm_type IN ('linux_vm', 'windows_vm') AND iso_url_x86 IS NULL")
```

**Step 4: Apply migration**

Run: `docker compose exec api alembic upgrade head`

Expected: Migration applies successfully

**Step 5: Commit**

```bash
git add alembic/versions/
git commit -m "feat: add migration for multi-architecture template support"
```

---

## Task 5: Update Template Schema for API Responses

**Files:**
- Modify: `backend/cyroid/schemas/template.py`

**Step 1: Read current schema**

First check the current template schema structure.

**Step 2: Add architecture fields to response schemas**

Add to `VMTemplateResponse` (or equivalent response model):

```python
    iso_url_x86: Optional[str] = None
    iso_url_arm64: Optional[str] = None
    native_arch: str = "x86_64"

    # Computed field for frontend convenience
    @property
    def supports_arm64(self) -> bool:
        return self.native_arch in ('arm64', 'both') or self.iso_url_arm64 is not None
```

**Step 3: Commit**

```bash
git add backend/cyroid/schemas/template.py
git commit -m "feat: add multi-architecture fields to template schemas"
```

---

## Task 6: Add ARM64 ISO URLs to Seed Data

**Files:**
- Modify: `backend/cyroid/api/cache.py` (contains ISO URL definitions)

**Step 1: Locate ISO URL definitions**

The ISO URLs are defined in cache.py. Update the LINUX_DISTRO_ISOS dict to include ARM64 URLs.

**Step 2: Create ARM64 ISO URL mappings**

Add a new dict for ARM64 URLs:

```python
# ARM64 ISO URLs for supported distributions
LINUX_DISTRO_ARM64_ISOS = {
    "ubuntu": "https://releases.ubuntu.com/24.04/ubuntu-24.04.1-live-server-arm64.iso",
    "debian": "https://cdimage.debian.org/debian-cd/current/arm64/iso-cd/debian-12.9.0-arm64-netinst.iso",
    "fedora": "https://download.fedoraproject.org/pub/fedora/linux/releases/41/Server/aarch64/iso/Fedora-Server-dvd-aarch64-41-1.4.iso",
    "alpine": "https://dl-cdn.alpinelinux.org/alpine/v3.21/releases/aarch64/alpine-virt-3.21.2-aarch64.iso",
    "rocky": "https://download.rockylinux.org/pub/rocky/9/isos/aarch64/Rocky-9.5-aarch64-minimal.iso",
    "alma": "https://repo.almalinux.org/almalinux/9/isos/aarch64/AlmaLinux-9-latest-aarch64-minimal.iso",
    "kali": "https://cdimage.kali.org/kali-2024.4/kali-linux-2024.4-installer-arm64.iso",
    # These distros don't have official ARM64 ISOs
    # "arch": None,  # x86_64 only
    # "manjaro": None,  # x86_64 only for VMs
    # "opensuse": None,  # Complex ARM situation
}

# Distributions with native ARM64 support
ARM64_NATIVE_DISTROS = {"ubuntu", "debian", "fedora", "alpine", "rocky", "alma", "kali"}
```

**Step 3: Commit**

```bash
git add backend/cyroid/api/cache.py
git commit -m "feat: add ARM64 ISO URLs for supported Linux distributions"
```

---

## Task 7: Update Docker Service for Emulation Detection

**Files:**
- Modify: `backend/cyroid/services/docker_service.py`

**Step 1: Add import for arch utilities**

At top of file with other imports:

```python
from cyroid.utils.arch import IS_ARM, HOST_ARCH, requires_emulation
```

**Step 2: Update create_windows_container method (around line 743)**

Replace the KVM detection block:

```python
        # Check if KVM is available for hardware acceleration
        kvm_available = os.path.exists("/dev/kvm")

        # Check if emulation is required (x86 VM on ARM host)
        emulated = IS_ARM  # Windows VMs are always x86

        if kvm_available and not emulated:
            environment["KVM"] = "Y"
            logger.info("KVM acceleration enabled for Windows VM")
        else:
            environment["KVM"] = "N"
            if emulated:
                logger.warning(
                    f"Windows VM '{name}' will run via x86 emulation on ARM host. "
                    "Expect significantly slower performance (10-20x)."
                )
            else:
                logger.warning("KVM not available, Windows VM will run in software emulation mode")
```

**Step 3: Update create_linux_vm_container method (around line 990)**

Replace the KVM detection block with emulation-aware version:

```python
        # Check if KVM is available for hardware acceleration
        kvm_available = os.path.exists("/dev/kvm")

        # Determine if this distro needs emulation
        # ARM64-native distros: ubuntu, debian, fedora, alpine, rocky, alma, kali
        arm64_native = linux_distro.lower() in ('ubuntu', 'debian', 'fedora', 'alpine', 'rocky', 'alma', 'kali')
        emulated = IS_ARM and not arm64_native

        if kvm_available:
            if emulated:
                logger.warning(
                    f"Linux VM '{name}' ({linux_distro}) will run via x86 emulation on ARM host. "
                    "Expect significantly slower performance (10-20x)."
                )
            else:
                logger.info(f"KVM acceleration enabled for Linux VM (native {'ARM64' if IS_ARM else 'x86_64'})")
        else:
            logger.warning("KVM not available, Linux VM will run in software emulation mode")
```

**Step 4: Add emulation flag to return values**

Modify the return statements for both methods to include emulation status. This may require updating the method signatures and callers.

**Step 5: Commit**

```bash
git add backend/cyroid/services/docker_service.py
git commit -m "feat: add emulation detection for x86 VMs on ARM hosts"
```

---

## Task 8: Update VM API to Return Emulation Status

**Files:**
- Modify: `backend/cyroid/schemas/vm.py`
- Modify: `backend/cyroid/api/vms.py`

**Step 1: Add emulated field to VM response schema**

In VM response schema:

```python
    emulated: bool = False
    emulation_warning: Optional[str] = None
```

**Step 2: Update VM creation endpoint to include emulation info**

The VM creation response should include whether the VM is running emulated.

**Step 3: Commit**

```bash
git add backend/cyroid/schemas/vm.py backend/cyroid/api/vms.py
git commit -m "feat: add emulation status to VM API responses"
```

---

## Task 9: Create Frontend System Store

**Files:**
- Create: `frontend/src/stores/systemStore.ts`

**Step 1: Create the system store**

```typescript
// frontend/src/stores/systemStore.ts
import { create } from 'zustand'
import { api } from '../services/api'

interface SystemInfo {
  host_arch: 'x86_64' | 'arm64'
  is_arm: boolean
  is_x86: boolean
  emulation_available: boolean
  platform: string
  machine: string
}

interface SystemState {
  info: SystemInfo | null
  isLoading: boolean
  error: string | null

  fetchSystemInfo: () => Promise<void>
}

export const useSystemStore = create<SystemState>((set) => ({
  info: null,
  isLoading: false,
  error: null,

  fetchSystemInfo: async () => {
    set({ isLoading: true, error: null })
    try {
      const response = await api.get<SystemInfo>('/system/info')
      set({ info: response.data, isLoading: false })
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to fetch system info'
      set({ error: message, isLoading: false })
      // Don't throw - system info is not critical for app function
      console.warn('System info fetch failed:', message)
    }
  },
}))

// Convenience hooks
export const useIsArmHost = () => useSystemStore((state) => state.info?.is_arm ?? false)
export const useHostArch = () => useSystemStore((state) => state.info?.host_arch ?? 'x86_64')
```

**Step 2: Commit**

```bash
git add frontend/src/stores/systemStore.ts
git commit -m "feat: add system store for architecture detection in frontend"
```

---

## Task 10: Fetch System Info on App Load

**Files:**
- Modify: `frontend/src/App.tsx`

**Step 1: Import and call fetchSystemInfo**

Add import:
```typescript
import { useSystemStore } from './stores/systemStore'
```

In the App component, add useEffect to fetch system info:
```typescript
const fetchSystemInfo = useSystemStore((state) => state.fetchSystemInfo)

useEffect(() => {
  fetchSystemInfo()
}, [fetchSystemInfo])
```

**Step 2: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: fetch system info on app initialization"
```

---

## Task 11: Create Emulation Warning Component

**Files:**
- Create: `frontend/src/components/common/EmulationWarning.tsx`

**Step 1: Create the warning component**

```typescript
// frontend/src/components/common/EmulationWarning.tsx
interface EmulationWarningProps {
  className?: string
  compact?: boolean
}

export function EmulationWarning({ className = '', compact = false }: EmulationWarningProps) {
  if (compact) {
    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-yellow-100 text-yellow-800 ${className}`}>
        <svg className="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
        </svg>
        Emulated
      </span>
    )
  }

  return (
    <div className={`bg-yellow-50 border-l-4 border-yellow-400 p-4 ${className}`}>
      <div className="flex">
        <div className="flex-shrink-0">
          <svg className="h-5 w-5 text-yellow-400" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
          </svg>
        </div>
        <div className="ml-3">
          <p className="text-sm text-yellow-700">
            <strong>Performance Notice:</strong> This VM will run via x86 emulation on your ARM host.
            Expect significantly slower performance (10-20x). For production use, deploy to x86 hardware.
          </p>
        </div>
      </div>
    </div>
  )
}

export default EmulationWarning
```

**Step 2: Commit**

```bash
git add frontend/src/components/common/EmulationWarning.tsx
git commit -m "feat: add EmulationWarning component for ARM hosts"
```

---

## Task 12: Add Warning to VM Creation in RangeDetail

**Files:**
- Modify: `frontend/src/pages/RangeDetail.tsx`

**Step 1: Import dependencies**

```typescript
import { useIsArmHost } from '../stores/systemStore'
import { EmulationWarning } from '../components/common/EmulationWarning'
```

**Step 2: Add emulation check logic**

In the VM creation form section, add logic to determine if warning should show:

```typescript
const isArmHost = useIsArmHost()

// Determine if selected template requires emulation
const templateRequiresEmulation = useMemo(() => {
  if (!isArmHost || !selectedTemplate) return false

  // Windows always requires emulation on ARM
  if (selectedTemplate.vm_type === 'windows_vm') return true

  // Check if Linux distro has ARM64 support
  const arm64Distros = ['ubuntu', 'debian', 'fedora', 'alpine', 'rocky', 'alma', 'kali']
  const distro = selectedTemplate.linux_distro?.toLowerCase()
  return distro && !arm64Distros.includes(distro)
}, [isArmHost, selectedTemplate])
```

**Step 3: Add warning in form**

Where the VM creation form is rendered, add:

```typescript
{templateRequiresEmulation && (
  <EmulationWarning className="mb-4" />
)}
```

**Step 4: Commit**

```bash
git add frontend/src/pages/RangeDetail.tsx
git commit -m "feat: add emulation warning to VM creation form"
```

---

## Task 13: Add Emulation Badge to VM Cards

**Files:**
- Modify: `frontend/src/components/execution/VMGrid.tsx` (or equivalent VM card component)

**Step 1: Import EmulationWarning component**

```typescript
import { EmulationWarning } from '../common/EmulationWarning'
```

**Step 2: Add compact badge to VM cards**

In the VM card render, add badge when VM is emulated:

```typescript
{vm.emulated && (
  <EmulationWarning compact className="ml-2" />
)}
```

**Step 3: Commit**

```bash
git add frontend/src/components/execution/VMGrid.tsx
git commit -m "feat: add emulation badge to VM cards"
```

---

## Task 14: Update README with Platform Support Section

**Files:**
- Modify: `README.md`

**Step 1: Add Platform Support section after Quick Start**

Add new section:

```markdown
---

## Platform Support

CYROID runs natively on both **x86_64** and **ARM64** architectures (Apple Silicon, AWS Graviton, Raspberry Pi, etc.).

### Architecture Compatibility Matrix

| Feature | x86_64 | ARM64 |
|---------|--------|-------|
| Core Platform (API, Frontend, DB) | ✅ Native | ✅ Native |
| Linux Containers | ✅ Native | ✅ Native |
| Linux VMs (Ubuntu, Debian, Fedora, Alpine, Rocky, Alma, Kali) | ✅ Native | ✅ Native |
| Linux VMs (Arch, Manjaro, Security Onion, others) | ✅ Native | ⚠️ Emulated |
| Windows VMs (all versions) | ✅ Native | ⚠️ Emulated |
| VyOS Router | ✅ Native | ⚠️ Emulated |

### Running on ARM64 Hosts

When running CYROID on ARM64 hosts (e.g., Apple Silicon Macs, AWS Graviton instances):

**Native Performance:**
- All core platform services (API, database, cache, storage) run natively
- Docker containers run natively
- Linux VMs for supported distributions download ARM64 ISOs automatically

**Emulated (x86 via QEMU):**
- Arch Linux, Manjaro, Security Onion, and other x86-only distributions
- All Windows VMs (Windows ARM support planned for future release)
- VyOS routers

**Performance Expectations:**
| Mode | Performance | Use Case |
|------|-------------|----------|
| Native ARM64 | 100% | Production on ARM infrastructure |
| Emulated x86 | 5-10% | Development, testing, demos |

> **Note:** The UI displays inline warnings when VMs will run via emulation, allowing you to understand performance implications before deployment.

### Development on ARM

CYROID fully supports development workflows on ARM64:

1. All features remain fully functional
2. The UI clearly indicates when emulation is active
3. No code changes required between ARM development and x86 production deployment

The platform automatically detects host architecture and selects native ISOs where available.
```

**Step 2: Add Windows ARM to roadmap section**

In the Planned Features table, add:

```markdown
| Windows ARM64 VM Support | 7 | Low |
```

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add platform support section with ARM64 compatibility matrix"
```

---

## Task 15: Update CLAUDE.md Roadmap

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Add to Phase 7 Planned Items**

```markdown
- [ ] Windows ARM64 VM support (Win11 ARM)
```

**Step 2: Update Feature Implementation Status table**

Add row:
```markdown
| Multi-Architecture Support | ✅ | x86_64 + ARM64 native, emulation warnings |
```

**Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update roadmap with multi-architecture support and Windows ARM future item"
```

---

## Task 16: Final Integration Test

**Step 1: Restart services**

```bash
docker compose down && docker compose up -d --build
```

**Step 2: Verify system info endpoint**

```bash
curl http://localhost/api/v1/system/info
```

Expected: JSON with architecture info

**Step 3: Verify frontend loads without errors**

Open http://localhost in browser, check console for errors.

**Step 4: Verify database migration applied**

```bash
docker compose exec api alembic current
```

**Step 5: Create final commit**

```bash
git add -A
git commit -m "feat: complete multi-architecture support implementation

- Architecture detection utility (backend/cyroid/utils/arch.py)
- System info API endpoint (/api/v1/system/info)
- Multi-arch template columns (iso_url_x86, iso_url_arm64, native_arch)
- ARM64 ISO URLs for 7 Linux distributions
- Emulation detection in Docker service
- Frontend system store for architecture awareness
- EmulationWarning component with inline and badge variants
- VM creation form shows warnings for emulated VMs
- VM cards show emulation badge
- README platform support documentation
- Roadmap updated with Windows ARM future item

Supports development on ARM (Apple Silicon) with full production
deployment capability on x86_64 infrastructure."
```

---

## Verification Checklist

- [ ] `GET /api/v1/system/info` returns correct architecture
- [ ] Database migration applies cleanly
- [ ] Frontend fetches system info on load
- [ ] EmulationWarning component renders correctly
- [ ] VM creation form shows warning for Windows templates on ARM
- [ ] VM creation form shows warning for x86-only Linux distros on ARM
- [ ] VM cards display emulation badge when applicable
- [ ] README platform support section renders correctly
- [ ] All services start without errors on ARM host
- [ ] All services start without errors on x86 host
