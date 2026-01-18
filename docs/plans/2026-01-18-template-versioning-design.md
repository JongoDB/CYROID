# Template Versioning Design

> OS family grouping with version dropdown for wizard template selection.

**Goal:** Users select OS families (e.g., "Windows Server") with expandable version dropdowns (2019, 2022, 2025) instead of hardcoded template names.

**Architecture:** Separate seed template files per version, frontend groups by `os_family` field, version selection in Services step UI.

---

## 1. Seed Template Organization

Directory structure with OS family subdirectories:

```
data/seed-templates/
├── windows/
│   ├── windows-server-2019.yaml
│   ├── windows-server-2022.yaml
│   ├── windows-server-2025.yaml
│   ├── windows-10-desktop.yaml
│   └── windows-11-desktop.yaml
├── linux/
│   ├── ubuntu-server-22.04.yaml
│   ├── ubuntu-server-24.04.yaml
│   ├── ubuntu-desktop-22.04.yaml
│   ├── kali-desktop.yaml
│   ├── security-onion.yaml
│   └── pfsense.yaml
├── network/
│   └── vyos-router.yaml
└── manifest.yaml
```

Each template includes grouping metadata:

```yaml
seed_id: windows-server-2022
name: "Windows Server 2022"
os_family: windows-server    # For grouping in UI
os_version: "2022"           # Version identifier
os_type: windows
# ... rest of template
```

## 2. Service Catalog Changes

Update `servicePresets.ts` to reference OS families:

```typescript
export const SERVICE_CATALOG: ServiceConfig[] = [
  {
    id: 'ad',
    name: 'Active Directory',
    osFamily: 'windows-server',
    defaultVersion: '2022',
    description: 'Domain controller',
    category: 'infrastructure',
    defaultNetwork: 'Corporate'
  },
  {
    id: 'dns',
    name: 'DNS Server',
    osFamily: 'ubuntu-server',
    defaultVersion: '22.04',
    description: 'DNS resolution',
    category: 'infrastructure',
    defaultNetwork: 'Corporate'
  },
  // ...
];
```

VMPlacement interface additions:

```typescript
interface VMPlacement {
  // ... existing fields
  osFamily?: string;      // e.g., 'windows-server'
  osVersion?: string;     // e.g., '2022'
}
```

## 3. Version Selection UI

In ServicesStep "Your Selections" section:

```
┌─────────────────────────────────────────────┐
│ Your Selections                             │
├─────────────────────────────────────────────┤
│ ▼ Active Directory                      [×] │
│   └─ Windows Server ▼ [2019|2022|2025]     │
│                                             │
│ ▶ DNS Server                            [×] │
│   └─ Ubuntu Server: 22.04                   │
└─────────────────────────────────────────────┘
```

- Collapsed (▶): Shows OS family and current version
- Expanded (▼): Shows dropdown to select different version
- Version options fetched from templates matching `os_family`

## 4. Deploy Flow

Resolution pattern in `RangeWizardPage.handleDeploy()`:

```typescript
// Resolve osFamily + osVersion to template name
const templateName = resolveTemplateName(vm.osFamily, vm.osVersion);
// e.g., "windows-server" + "2022" → "Windows Server 2022"

const template = templates.find(t => t.name === templateName);
```

Template name format must be consistent:
- Seed template `name`: "Windows Server 2022"
- Pattern: `{OS Family Title Case} {Version}`

## 5. Templates to Create

| OS Family | Versions | Services |
|-----------|----------|----------|
| `windows-server` | 2019, 2022, 2025 | AD, File Server, SQL Server |
| `ubuntu-server` | 22.04, 24.04 | DNS, DHCP, SIEM, Web, Email, MySQL |
| `pfsense` | 2.7 | Firewall/Router |
| `security-onion` | 2.4 | IDS/IPS |

Existing templates to update:
- `ubuntu-server` → `ubuntu-server-22.04` (add os_family, os_version)
- `windows-server-2022` → move to windows/ subdir, add os_family

New templates to create:
- `windows-server-2019.yaml`
- `windows-server-2025.yaml`
- `ubuntu-server-24.04.yaml`
- `pfsense.yaml`
- `security-onion.yaml`

## 6. Backend Changes

Update template seeding to:
1. Scan subdirectories (`windows/`, `linux/`, `network/`)
2. Parse new `os_family` and `os_version` fields
3. Store in database for frontend grouping queries

Add API support:
- `GET /api/v1/templates?group_by=os_family` - Returns templates grouped by family

## Files to Modify

**Backend:**
- `backend/cyroid/services/template_seeder.py` - Scan subdirs, parse new fields
- `backend/cyroid/models/template.py` - Add os_family, os_version columns
- `backend/cyroid/api/templates.py` - Add grouping query param

**Frontend:**
- `frontend/src/stores/wizardStore.ts` - Add osFamily, osVersion to VMPlacement
- `frontend/src/components/wizard-v2/data/servicePresets.ts` - Use osFamily
- `frontend/src/components/wizard-v2/steps/ServicesStep.tsx` - Version dropdown UI
- `frontend/src/pages/RangeWizardPage.tsx` - Template name resolution

**Seed Templates:**
- Reorganize into subdirectories
- Add os_family/os_version to all templates
- Create missing templates (pfsense, security-onion, version variants)
