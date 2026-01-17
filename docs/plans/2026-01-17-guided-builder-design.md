# Guided Range Builder Design

## Overview

The Guided Range Builder provides a wizard-style interface for creating complete cyber training environments with minimal manual configuration. Users select a scenario preset, customize zones and systems, configure basic settings, and deploy with auto-assigned IPs and networking.

## Design Goals

1. **Simplicity**: 5-10 questions max, no manual IP configuration
2. **Flexibility**: Presets are starting points, not locked configurations
3. **Cyber Defense Focus**: Prioritize blue team training scenarios
4. **Integration**: Uses existing CYROID APIs, no backend changes needed

## Entry Points

1. **"Guided Builder" button** next to "New Range" on Ranges page
2. **Empty state CTA** for first-time users

## Wizard Flow

```
Step 0: Scenario Selection
    ↓
Step 1: Zone Configuration
    ↓
Step 2: System Selection
    ↓
Step 3: Configuration Options
    ↓
Step 4: Review & Deploy
```

## Scenario Presets

### 1. AD Enterprise Lab

**Target Audience**: Blue team defenders practicing AD security

**Zones:**
| Zone | Subnet | Purpose |
|------|--------|---------|
| Internal | 10.100.0.0/24 | Corporate network |

**Systems:**
| System | IP | Template | Purpose |
|--------|-------|----------|---------|
| Domain Controller | 10.100.0.10 | Windows Server 2022 | AD DS, DNS |
| File Server | 10.100.0.20 | Windows Server 2022 | File/Print services |
| Workstation 1 | 10.100.0.50 | Windows 11 | Domain-joined client |
| Workstation 2 | 10.100.0.51 | Windows 11 | Domain-joined client |

**Configuration:**
- Domain Name (default: lab.local)
- Admin Password (generated)
- Number of Domain Users (5/10/25/50)

---

### 2. Segmented Network (DMZ)

**Target Audience**: Network defense, firewall management, zone-based security

**Zones:**
| Zone | Subnet | Purpose |
|------|--------|---------|
| External | 10.200.0.0/24 | Attacker/Internet simulation |
| DMZ | 10.201.0.0/24 | Public-facing services |
| Internal | 10.202.0.0/24 | Protected corporate network |

**Systems:**
| Zone | System | IP | Template | Purpose |
|------|--------|-------|----------|---------|
| External | Kali Linux | 10.200.0.100 | Kali | Attack platform |
| DMZ | Web Server | 10.201.0.10 | Ubuntu + Apache | Public web app |
| DMZ | Mail Server | 10.201.0.20 | Ubuntu + Postfix | Email gateway |
| Internal | Domain Controller | 10.202.0.10 | Windows Server 2022 | AD DS |
| Internal | Workstation | 10.202.0.50 | Windows 11 | User endpoint |

**Configuration:**
- Domain Name
- Admin Password
- Vulnerability Level (none/some/many)

**Routing:**
VyOS router connects all zones with default-deny firewall rules.

---

### 3. Incident Response Lab

**Target Audience**: Forensics, incident investigation, threat hunting

**Zones:**
| Zone | Subnet | Purpose |
|------|--------|---------|
| Internal | 10.150.0.0/24 | "Compromised" corporate network |

**Systems:**
| System | IP | Template | Purpose |
|--------|-------|----------|---------|
| Domain Controller | 10.150.0.10 | Windows Server 2022 | AD DS |
| Compromised Workstation | 10.150.0.50 | Windows 11 | Attack artifacts staged |
| SIFT Workstation | 10.150.0.100 | SIFT/REMnux | Forensics analysis |

**Configuration:**
- Domain Name
- Artifact Level (minimal/moderate/extensive)

---

### 4. Penetration Testing Target

**Target Audience**: Red team practice, vulnerability exploitation

**Zones:**
| Zone | Subnet | Purpose |
|------|--------|---------|
| Lab Network | 10.50.0.0/24 | Isolated attack lab |

**Systems:**
| System | IP | Template | Purpose |
|--------|-------|----------|---------|
| Kali Linux | 10.50.0.100 | Kali | Attack platform |
| Metasploitable | 10.50.0.10 | Metasploitable | Vulnerable Linux |
| DVWA | 10.50.0.20 | DVWA Container | Vulnerable web app |
| Windows Target | 10.50.0.30 | Windows 10 (unpatched) | Vulnerable Windows |

**Configuration:**
- Vulnerability Level (easy/medium/hard)

---

## Step Details

### Step 0: Scenario Selection

**UI**: Card grid (2x2)

Each card shows:
- Icon (network diagram)
- Scenario name
- 1-line description
- Preview: "X VMs, Y networks"

Click to select and advance.

### Step 1: Zone Configuration

**UI**: Editable zone cards

For each zone from preset:
- Checkbox to enable/disable
- Zone name (editable)
- Subnet (read-only, auto-assigned)
- System count indicator

Disabled zones won't be created. All their systems are excluded.

### Step 2: System Selection

**UI**: Grouped by zone

For each enabled zone:
- Zone header with subnet
- System chips (toggleable)
  - Icon based on OS type
  - System name
  - Click to toggle on/off

Pre-selected based on preset. Users can deselect systems they don't want.

### Step 3: Configuration Options

**UI**: Form fields

**Universal Fields:**
- Range Name (required)
- Range Description (optional)

**AD-Specific Fields** (shown if DC present):
- Domain Name (default: lab.local)
- Admin Password (auto-generated, show/hide toggle)
- Number of Domain Users (dropdown)

**Security Fields:**
- Vulnerability Level (none/some/many)
  - Affects system configurations
  - v1: Cosmetic only; actual vuln configs in future

### Step 4: Review & Deploy

**UI**: Expandable summary

**Sections:**
1. **Range Info**: Name, description
2. **Networks**: List with subnets
3. **Systems**: Grouped by network, showing IP assignments
4. **Configuration**: Domain settings, security level

**Resource Summary:**
- Total VMs: X
- Total CPU cores: Y
- Total RAM: Z GB
- Estimated disk: W GB

**Actions:**
- "Back" to make changes
- "Deploy Range" to create and start

---

## Technical Design

### Component Structure

```
frontend/src/components/wizard/
├── GuidedBuilderWizard.tsx     # Modal container, step navigation
├── WizardContext.tsx           # State management (React Context)
├── steps/
│   ├── ScenarioSelection.tsx   # Step 0
│   ├── ZoneConfiguration.tsx   # Step 1
│   ├── SystemSelection.tsx     # Step 2
│   ├── ConfigurationOptions.tsx # Step 3
│   └── ReviewAndDeploy.tsx     # Step 4
└── presets/
    ├── index.ts                # Export all presets
    ├── types.ts                # TypeScript interfaces
    ├── adEnterpriseLab.ts
    ├── segmentedNetwork.ts
    ├── incidentResponse.ts
    └── pentestTarget.ts
```

### State Interface

```typescript
interface WizardState {
  currentStep: number;
  scenario: ScenarioPreset | null;
  zones: ZoneState[];
  config: ConfigState;
  rangeName: string;
  rangeDescription: string;
}

interface ZoneState {
  id: string;
  name: string;
  subnet: string;
  enabled: boolean;
  systems: SystemState[];
}

interface SystemState {
  id: string;
  name: string;
  ip: string;
  templateName: string;
  osType: 'windows' | 'linux';
  enabled: boolean;
}

interface ConfigState {
  domainName: string;
  adminPassword: string;
  userCount: number;
  vulnerabilityLevel: 'none' | 'some' | 'many';
}
```

### Preset Interface

```typescript
interface ScenarioPreset {
  id: string;
  name: string;
  description: string;
  icon: string;
  zones: PresetZone[];
  config: Partial<ConfigState>;
}

interface PresetZone {
  id: string;
  name: string;
  subnet: string;
  systems: PresetSystem[];
}

interface PresetSystem {
  id: string;
  name: string;
  ipOffset: number;  // e.g., 10 for .10, 50 for .50
  templateName: string;  // Must match existing template
  osType: 'windows' | 'linux';
  role?: string;  // 'domain-controller', 'workstation', etc.
}
```

### API Integration

The wizard uses existing APIs - no backend changes needed.

**Deployment Sequence:**
1. `POST /ranges` - Create range with name, description
2. For each enabled zone:
   - `POST /networks` - Create network with subnet, gateway
3. For each enabled system:
   - `POST /vms` - Create VM with IP, template, network
4. `POST /ranges/{id}/deploy` - Start deployment
5. Navigate to `/ranges/{id}` with deployment progress

### Template Mapping

Presets reference templates by `templateName`. On wizard load:

1. Fetch all templates: `GET /templates`
2. Build lookup map: `name → id`
3. When deploying, resolve each system's `templateName` to `template_id`
4. If template not found, show warning and skip system

**Fallback**: Some templates may not exist. Wizard shows warning but continues with available systems.

---

## Scope

### v1 (This Implementation)

- 4 scenario presets (hardcoded in frontend)
- 5-step wizard flow
- Auto-assigned subnets and IPs
- Basic configuration (domain, password, users, vuln level)
- Sequential API calls for creation
- Auto-deploy after creation
- Navigate to RangeDetail on completion

### Stretch Goals (Future)

- Custom zone addition
- Custom system addition from template picker
- Editable subnet assignments
- Save custom presets (Issue #18 integration)
- Network topology preview diagram
- Progress indicator during multi-VM deployment

### Dependencies

- Existing VM templates in database
- VyOS router support (already implemented)
- Template naming conventions for mapping

### Limitations

- Vulnerability level is cosmetic in v1
- IR Lab artifacts require manual staging
- Presets are frontend-only, not persisted

---

## UI/UX Notes

- Modal overlay (same pattern as other wizards)
- Progress stepper at top showing 5 steps
- Back/Next navigation buttons
- Keyboard shortcuts: Enter to advance, Escape to close
- Loading state during deployment
- Toast notifications for errors

---

## Estimated Effort

- **Files**: 10-12 new frontend files
- **Lines**: ~1500 TypeScript
- **Backend Changes**: None
- **Dependencies**: None (uses existing Lucide icons, Tailwind)
