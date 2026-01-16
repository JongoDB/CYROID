# Multi-Architecture Support Design

**Date:** 2026-01-16
**Status:** Approved
**Author:** Claude Code + Jon

## Overview

Enable CYROID to run on both x86_64 and ARM64 architectures, with native performance where possible and transparent x86 emulation with user warnings where necessary.

## Goals

1. Full development workflow support on ARM64 (Apple Silicon Macs)
2. Production deployment capability on either architecture
3. Native ARM64 Linux VMs for supported distributions
4. Transparent x86 emulation with clear performance warnings
5. No breaking changes for existing x86 deployments

## Non-Goals (Deferred)

- Windows ARM64 VM support (added to roadmap)
- Automatic architecture detection for ISO downloads at runtime
- Multi-arch Docker image builds for CYROID itself

---

## Architecture Detection Layer

### New Utility Module

**File:** `backend/cyroid/utils/arch.py`

```python
"""
Architecture detection utilities for multi-platform support.
"""
import platform
from typing import Literal

# Detect host architecture
_machine = platform.machine().lower()

IS_ARM: bool = _machine in ('arm64', 'aarch64')
IS_X86: bool = _machine in ('x86_64', 'amd64', 'x86')
HOST_ARCH: Literal['arm64', 'x86_64'] = 'arm64' if IS_ARM else 'x86_64'

def requires_emulation(target_arch: str) -> bool:
    """Check if running a target architecture requires emulation."""
    if target_arch in ('x86_64', 'amd64', 'x86'):
        return IS_ARM
    if target_arch in ('arm64', 'aarch64'):
        return IS_X86
    return False

def get_system_info() -> dict:
    """Return system architecture information."""
    return {
        "host_arch": HOST_ARCH,
        "is_arm": IS_ARM,
        "is_x86": IS_X86,
        "emulation_available": True,  # QEMU available via Docker
        "platform": platform.system().lower(),
    }
```

### API Endpoint

**File:** `backend/cyroid/api/system.py` (new)

```python
from fastapi import APIRouter
from cyroid.utils.arch import get_system_info

router = APIRouter(prefix="/api/system", tags=["system"])

@router.get("/info")
async def system_info():
    """Return host system information including architecture."""
    return get_system_info()
```

Register in `main.py`:
```python
from cyroid.api import system
app.include_router(system.router)
```

---

## Template Model Changes

### Database Schema Update

**File:** `backend/cyroid/models/template.py`

Add new columns to `VMTemplate`:

```python
class VMTemplate(Base):
    # ... existing fields ...

    # Multi-architecture support
    iso_url_x86: Optional[str] = Column(String, nullable=True)
    iso_url_arm64: Optional[str] = Column(String, nullable=True)
    native_arch: str = Column(String, default='x86_64')  # 'x86_64', 'arm64', 'both'
```

### Migration

**File:** `alembic/versions/xxx_add_multi_arch_support.py`

```python
def upgrade():
    op.add_column('vm_templates', sa.Column('iso_url_x86', sa.String(), nullable=True))
    op.add_column('vm_templates', sa.Column('iso_url_arm64', sa.String(), nullable=True))
    op.add_column('vm_templates', sa.Column('native_arch', sa.String(), server_default='x86_64'))

    # Migrate existing iso_url to iso_url_x86
    op.execute("UPDATE vm_templates SET iso_url_x86 = iso_url WHERE iso_url IS NOT NULL")

def downgrade():
    op.drop_column('vm_templates', 'native_arch')
    op.drop_column('vm_templates', 'iso_url_arm64')
    op.drop_column('vm_templates', 'iso_url_x86')
```

---

## ARM64 ISO URL Mappings

### Supported Distributions

| Distribution | x86_64 URL | ARM64 URL |
|--------------|------------|-----------|
| Ubuntu 24.04 | `ubuntu-24.04-live-server-amd64.iso` | `ubuntu-24.04-live-server-arm64.iso` |
| Ubuntu 22.04 | `ubuntu-22.04-live-server-amd64.iso` | `ubuntu-22.04-live-server-arm64.iso` |
| Debian 13 | `debian-13-amd64-netinst.iso` | `debian-13-arm64-netinst.iso` |
| Debian 12 | `debian-12-amd64-netinst.iso` | `debian-12-arm64-netinst.iso` |
| Fedora 41 | `Fedora-Server-dvd-x86_64-41.iso` | `Fedora-Server-dvd-aarch64-41.iso` |
| Alpine 3.21 | `alpine-virt-3.21-x86_64.iso` | `alpine-virt-3.21-aarch64.iso` |
| Rocky 9 | `Rocky-9-x86_64-dvd.iso` | `Rocky-9-aarch64-dvd.iso` |
| AlmaLinux 9 | `AlmaLinux-9-x86_64-dvd.iso` | `AlmaLinux-9-aarch64-dvd.iso` |
| Kali 2024 | `kali-linux-2024-installer-amd64.iso` | `kali-linux-2024-installer-arm64.iso` |

### x86-Only Distributions

These will run via emulation on ARM hosts:

- Arch Linux (no official ARM ISO for VMs)
- Security Onion
- DVWA / Metasploitable
- Windows (all versions)
- VyOS Router

---

## Docker Service Changes

### VM Creation Logic

**File:** `backend/cyroid/services/docker_service.py`

Update `create_linux_vm()` and `create_windows_vm()`:

```python
from cyroid.utils.arch import IS_ARM, requires_emulation

async def create_linux_vm(self, vm: VM, template: VMTemplate) -> str:
    # Determine which ISO to use
    if IS_ARM and template.iso_url_arm64:
        iso_url = template.iso_url_arm64
        emulated = False
    else:
        iso_url = template.iso_url_x86 or template.iso_url
        emulated = IS_ARM

    # Log emulation status
    if emulated:
        logger.warning(
            f"VM {vm.name} will run via x86 emulation on ARM host. "
            "Performance will be significantly reduced."
        )

    environment = {
        # ... existing env vars ...
        "EMULATED": "Y" if emulated else "N",
    }

    # For QEMU on ARM, may need additional flags
    if emulated:
        environment["QEMU_CPU"] = "max"
        environment["ARCH"] = "x86_64"

    # ... rest of VM creation ...

    return container.id, emulated  # Return emulation status
```

### API Response Enhancement

Update VM creation endpoints to return emulation status:

```python
class VMCreateResponse(BaseModel):
    id: int
    name: str
    status: str
    emulated: bool = False
    emulation_warning: Optional[str] = None
```

---

## Frontend Changes

### System Info Store

**File:** `frontend/src/stores/systemStore.ts` (new or extend existing)

```typescript
import { create } from 'zustand';
import api from '../services/api';

interface SystemState {
  hostArch: 'x86_64' | 'arm64' | null;
  isArm: boolean;
  loaded: boolean;
  fetchSystemInfo: () => Promise<void>;
}

export const useSystemStore = create<SystemState>((set) => ({
  hostArch: null,
  isArm: false,
  loaded: false,
  fetchSystemInfo: async () => {
    const info = await api.get('/api/system/info');
    set({
      hostArch: info.host_arch,
      isArm: info.is_arm,
      loaded: true,
    });
  },
}));
```

### Emulation Warning Component

**File:** `frontend/src/components/EmulationWarning.tsx`

```typescript
interface EmulationWarningProps {
  className?: string;
}

export function EmulationWarning({ className }: EmulationWarningProps) {
  return (
    <div className={`bg-yellow-50 border-l-4 border-yellow-400 p-4 ${className}`}>
      <div className="flex">
        <svg className="h-5 w-5 text-yellow-400" viewBox="0 0 20 20" fill="currentColor">
          <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
        </svg>
        <div className="ml-3">
          <p className="text-sm text-yellow-700">
            <strong>Performance Notice:</strong> This VM will run via x86 emulation
            on your ARM host. Expect significantly slower performance (10-20x).
            For production use, deploy to x86 hardware.
          </p>
        </div>
      </div>
    </div>
  );
}
```

### VM Creation Form Integration

Show warning when template requires emulation:

```typescript
// In VM creation form component
const { isArm } = useSystemStore();
const templateRequiresEmulation = isArm && !selectedTemplate?.iso_url_arm64;

return (
  <form>
    {/* Template selector */}

    {templateRequiresEmulation && (
      <EmulationWarning className="mb-4" />
    )}

    {/* Rest of form */}
  </form>
);
```

### VM Card Badge

Add emulation indicator to VM cards:

```typescript
// In VM card component
{vm.emulated && (
  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-yellow-100 text-yellow-800">
    Emulated
  </span>
)}
```

---

## README Documentation

### New Section: Platform Support

```markdown
## Platform Support

CYROID runs natively on both x86_64 and ARM64 architectures (Apple Silicon, AWS Graviton, Raspberry Pi, etc.).

### Architecture Compatibility Matrix

| Feature | x86_64 | ARM64 |
|---------|--------|-------|
| Core Platform (API, Frontend, DB) | ✅ Native | ✅ Native |
| Linux Containers | ✅ Native | ✅ Native |
| Linux VMs - Ubuntu, Debian, Fedora, Alpine, Rocky, Alma, Kali | ✅ Native | ✅ Native |
| Linux VMs - Arch, Security Onion | ✅ Native | ⚠️ Emulated |
| Windows VMs | ✅ Native | ⚠️ Emulated |
| VyOS Router | ✅ Native | ⚠️ Emulated |

### Running on ARM64

When running on ARM64 hosts (e.g., Apple Silicon Macs, AWS Graviton):

**Native Performance:**
- All core platform services run natively
- Linux containers run natively
- Supported Linux VMs (Ubuntu, Debian, Fedora, Alpine, Rocky, Alma, Kali) run natively with ARM64 ISOs

**Emulated (x86 via QEMU):**
- Arch Linux, Security Onion, and other x86-only distros
- All Windows VMs
- VyOS routers

**Performance Expectations:**
- Native ARM VMs: Full performance
- Emulated x86 VMs: Expect 10-20x slower performance
- Recommended for: Development, testing, demos
- Production with full VM support: Deploy to x86_64

### Development on ARM

CYROID fully supports development workflows on ARM64:

1. The UI displays inline warnings when emulation is active
2. All features remain functional for testing
3. No code changes needed between ARM development and x86 production

The platform automatically detects the host architecture and selects native ISOs where available.
```

### Roadmap Addition

Add to Future Enhancements:

```markdown
### Future Enhancements

- [ ] Windows ARM64 VM support (Windows 11 ARM)
- [ ] Multi-architecture Docker image builds
- [ ] Runtime ISO architecture selection
```

---

## Implementation Order

1. **Backend: Architecture detection** - `utils/arch.py`, system info endpoint
2. **Backend: Database migration** - Add ARM columns to templates
3. **Backend: Update template seeding** - Add ARM64 ISO URLs
4. **Backend: Docker service changes** - Emulation detection and flags
5. **Frontend: System store** - Fetch and store architecture info
6. **Frontend: Warning components** - EmulationWarning, badges
7. **Frontend: Form integration** - Show warnings in VM creation
8. **Documentation** - README platform support section
9. **Testing** - Verify on both architectures

---

## Testing Checklist

- [ ] Architecture detection returns correct values on x86
- [ ] Architecture detection returns correct values on ARM (Mac)
- [ ] System info endpoint returns expected data
- [ ] Migration runs successfully (up and down)
- [ ] ARM64 ISO URLs resolve correctly
- [ ] x86 VM creation on ARM shows warning
- [ ] ARM VM creation on ARM shows no warning
- [ ] x86 VM creation on x86 shows no warning
- [ ] Emulation badge appears on emulated VMs
- [ ] README renders correctly with new section

---

## Files Changed

### New Files
- `backend/cyroid/utils/arch.py`
- `backend/cyroid/api/system.py`
- `alembic/versions/xxx_add_multi_arch_support.py`
- `frontend/src/components/EmulationWarning.tsx`
- `frontend/src/stores/systemStore.ts` (or extend existing)

### Modified Files
- `backend/cyroid/main.py` - Register system router
- `backend/cyroid/models/template.py` - Add ARM columns
- `backend/cyroid/services/docker_service.py` - Emulation logic
- `backend/cyroid/data/seed_templates.py` - ARM64 URLs
- `frontend/src/App.tsx` - Fetch system info on load
- `frontend/src/pages/RangeDetail.tsx` - Show emulation warnings
- `frontend/src/components/VMCard.tsx` - Emulation badge
- `README.md` - Platform support documentation
- `CLAUDE.md` - Update roadmap
