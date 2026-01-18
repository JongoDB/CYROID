# Range Wizard v2 - Design Document

> **Issue**: #34 - Guided Range Builder v2
> **Date**: 2026-01-18
> **Status**: Approved

## Overview

Complete redesign of the Guided Range Builder into a full-page "Range Wizard" that enables dynamic environment building with network topology visualization, user management, and vulnerability configuration.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Name | Range Wizard | Clear, action-oriented naming |
| Layout | Full-page at `/ranges/new` | More space for complex configuration |
| Steps | All 6 steps | Complete workflow in one place |
| Network Viz | React Flow interactive canvas | Industry-standard, drag-and-drop |
| VM Generation | Semi-automatic with override | Balance automation with control |
| Vulnerabilities | Preset profiles + custom toggle | Flexibility for all skill levels |
| User Management | Hybrid auto-generation | Generate from segments, allow edits |
| Review | Visual topology + collapsible tables | Clear overview without overwhelm |

## Architecture

### Overall Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│  Range Wizard                                            [X] Cancel  │
├────────────┬─────────────────────────────────────────────────────────┤
│            │                                                         │
│  Steps     │              Main Content Area                          │
│            │                                                         │
│  ● Env     │   (Changes based on selected step)                      │
│  ○ Services│                                                         │
│  ○ Networks│                                                         │
│  ○ Users   │                                                         │
│  ○ Vulns   │                                                         │
│  ○ Review  │                                                         │
│            │                                                         │
│            ├─────────────────────────────────────────────────────────┤
│            │  [← Previous]                    [Next Step →]          │
└────────────┴─────────────────────────────────────────────────────────┘
```

### State Management (Zustand)

```typescript
interface WizardState {
  currentStep: number;

  // Step 1: Environment
  environment: {
    type: 'enterprise' | 'industrial' | 'cloud' | 'custom';
    name: string;
    description: string;
  };

  // Step 2: Services
  services: {
    selected: string[];  // service IDs
    customServices: ServiceConfig[];
  };

  // Step 3: Networks
  networks: {
    segments: NetworkSegment[];
    connections: Connection[];
    vms: VMPlacement[];
  };

  // Step 4: Users
  users: {
    groups: UserGroup[];
    individuals: User[];
    accessRules: AccessRule[];
  };

  // Step 5: Vulnerabilities
  vulnerabilities: {
    preset: 'none' | 'beginner' | 'intermediate' | 'advanced' | 'custom';
    perVm: Record<string, string[]>;
    narrative?: string;
  };

  // Step 6: Review
  rangeName: string;
  saveAsBlueprint: boolean;

  // Actions
  setStep: (step: number) => void;
  updateEnvironment: (env: Partial<Environment>) => void;
  // ... other actions
}
```

---

## Step 1: Environment Type

**Purpose**: Select the base environment template that determines default network topology and services.

**Layout**:
```
┌─────────────────────────────────────────────────────────────────┐
│  What type of environment are you building?                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────┐ │
│  │  🏢         │  │  🏭         │  │  ☁️          │  │  ⚙️     │ │
│  │ Enterprise  │  │ Industrial  │  │   Cloud     │  │ Custom  │ │
│  │             │  │   (OT/ICS)  │  │             │  │         │ │
│  │ ○ Selected  │  │ ○           │  │ ○           │  │ ○       │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────┘ │
│                                                                  │
│  Enterprise Environment:                                         │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Typical corporate network with DMZ, internal segments,      ││
│  │ Active Directory, and standard business services.           ││
│  │                                                              ││
│  │ Default topology: Firewall → DMZ → Corporate → Servers      ││
│  │ Suggested services: AD, DNS, Web, Email, File Server        ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Behavior**:
- Card selection (radio-style, one active)
- Selection updates description panel
- Pre-populates Steps 2-3 with sensible defaults
- "Custom" starts with blank canvas

---

## Step 2: Services & Systems

**Purpose**: Select which services/systems to include. Auto-generates VM suggestions.

**Layout**:
```
┌─────────────────────────────────────────────────────────────────┐
│  Select Services & Systems                                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Recommended for Enterprise:        Your Selections:             │
│  ┌────────────────────────┐        ┌────────────────────────┐   │
│  │ ☑ Active Directory     │        │ AD Controller (Win2019)│   │
│  │ ☑ DNS Server           │   →    │ DNS Server (Ubuntu)    │   │
│  │ ☑ Web Server           │        │ Web Server (Ubuntu)    │   │
│  │ ☐ Email Server         │        │ Firewall (pfSense)     │   │
│  │ ☐ File Server          │        │                        │   │
│  │ ☑ Firewall/Router      │        │ [+ Add Custom VM]      │   │
│  │ ☐ Database Server      │        └────────────────────────┘   │
│  │ ☐ SIEM/Log Collector   │                                     │
│  └────────────────────────┘        Auto-generated: 4 VMs        │
│                                    Est. Resources: 8 CPU, 16GB  │
│  [+ Add Custom Service]                                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Behavior**:
- Checkbox list of services (pre-checked based on Step 1)
- Right panel shows auto-generated VMs
- Each VM can be clicked to override template/specs
- Resource estimation updates in real-time
- "Add Custom VM" opens template selector modal

---

## Step 3: Network Topology

**Purpose**: Visual network design with drag-and-drop using React Flow.

**Layout**:
```
┌─────────────────────────────────────────────────────────────────┐
│  Network Topology                                    [Auto-Layout]│
├─────────────────────────────────────────────────────────────────┤
│ Palette │                                                        │
│ ┌─────┐ │  ┌─────────────────────────────────────────────────┐  │
│ │ Net │ │  │                                                 │  │
│ │ ─── │ │  │    ┌─────────┐                                  │  │
│ └─────┘ │  │    │   WAN   │                                  │  │
│ ┌─────┐ │  │    └────┬────┘                                  │  │
│ │ VM  │ │  │         │                                       │  │
│ │ □   │ │  │    ┌────┴────┐                                  │  │
│ └─────┘ │  │    │ Firewall│                                  │  │
│ ┌─────┐ │  │    └────┬────┘                                  │  │
│ │Router│ │  │    ┌───┴───┬───────┐                           │  │
│ │ ◇   │ │  │    │       │       │                           │  │
│ └─────┘ │  │  ┌─┴──┐ ┌──┴──┐ ┌──┴──┐                        │  │
│         │  │  │DMZ │ │Corp │ │Mgmt │   <- Drag to reposition │  │
│         │  │  └─┬──┘ └──┬──┘ └──┬──┘                        │  │
│         │  │    │       │       │                           │  │
│         │  │  ┌─┴──┐ ┌──┴──┐ ┌──┴──┐                        │  │
│         │  │  │Web │ │ AD  │ │SIEM │   <- Click to configure│  │
│         │  │  └────┘ └─────┘ └─────┘                        │  │
│         │  └─────────────────────────────────────────────────┘  │
├─────────┼───────────────────────────────────────────────────────┤
│ Properties Panel (appears when node selected):                   │
│ ┌───────────────────────────────────────────────────────────────┐│
│ │ Network: DMZ          Subnet: [10.1.0.0/24]  DHCP: [✓]       ││
│ │ Gateway: [10.1.0.1]   VLAN: [100]            Isolated: [✓]   ││
│ └───────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

**React Flow Implementation**:
- Custom node types: `NetworkNode`, `VMNode`, `RouterNode`
- Edge type: `NetworkConnection` with bandwidth/latency labels
- Drag from palette to canvas to add elements
- Click node to show properties panel
- Drag between nodes to create connections
- Auto-layout button using dagre algorithm

**Node Data Structure**:
```typescript
interface NetworkNode {
  id: string;
  type: 'network';
  data: {
    name: string;
    subnet: string;
    gateway: string;
    dhcp: boolean;
    isolated: boolean;
    vlan?: number;
  };
  position: { x: number; y: number };
}

interface VMNode {
  id: string;
  type: 'vm';
  data: {
    hostname: string;
    templateId: string;
    ip: string;
    networkId: string;
    cpu: number;
    ramMb: number;
  };
  position: { x: number; y: number };
}
```

---

## Step 4: Users & Groups

**Purpose**: Configure user accounts and access permissions for the range.

**Layout**:
```
┌─────────────────────────────────────────────────────────────────┐
│  Users & Groups                                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Team Segments:                    Generated Users:              │
│  ┌────────────────────────┐       ┌────────────────────────────┐│
│  │ Red Team:    [2 ▾]     │       │ red-01    Red Team   Admin ││
│  │ Blue Team:   [4 ▾]     │  →    │ red-02    Red Team   Admin ││
│  │ White Cell:  [2 ▾]     │       │ blue-01   Blue Team  User  ││
│  │ Observers:   [0 ▾]     │       │ blue-02   Blue Team  User  ││
│  │                        │       │ blue-03   Blue Team  User  ││
│  │ [+ Add Custom Group]   │       │ blue-04   Blue Team  User  ││
│  └────────────────────────┘       │ white-01  White Cell Admin ││
│                                   │ white-02  White Cell Admin ││
│  Naming Pattern:                  │                            ││
│  [team]-[number]                  │ [+ Add Individual User]    ││
│  Example: blue-01, red-02         └────────────────────────────┘│
│                                                                  │
│  Access Rules:                                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Red Team  → Full access to all VMs                          ││
│  │ Blue Team → Access to defender workstations only            ││
│  │ White Cell → Full access + console override                 ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Behavior**:
- Dropdowns for team size (0-10 per segment)
- Auto-generates usernames based on pattern
- Click user row to edit individual details
- Access rules tied to network segments from Step 3
- Custom groups can be added with custom permissions

---

## Step 5: Vulnerabilities & Attack Surface

**Purpose**: Configure which vulnerabilities and misconfigurations to deploy on VMs.

**Layout**:
```
┌─────────────────────────────────────────────────────────────────┐
│  Vulnerability Configuration                                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Preset Profiles                           Custom Toggles        │
│  ┌────────────────────────┐               ┌────────────────────┐│
│  │ ○ None (Hardened)      │               │ Per-VM Settings    ││
│  │ ● Beginner (5 vulns)   │               │                    ││
│  │ ○ Intermediate (12)    │               │ web-server-01:     ││
│  │ ○ Advanced (20+)       │               │ ☑ SQL Injection    ││
│  │ ○ Custom               │               │ ☑ Weak SSH Keys    ││
│  └────────────────────────┘               │ ☐ Open Redis       ││
│                                           │ ☐ Default Creds    ││
│  Profile Description:                     │                    ││
│  "5 common vulnerabilities                │ db-server-01:      ││
│   suitable for introductory               │ ☑ Default MySQL pw ││
│   incident response training"             │ ☐ Remote Root      ││
│                                           └────────────────────┘│
│                                                                  │
│  Attack Narrative (Optional):                                    │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ "Attacker exploits SQL injection on web server, pivots to   ││
│  │  database server using harvested credentials..."            ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Behavior**:
- Radio selection for preset difficulty
- Per-VM checkboxes update based on preset, can override
- Vulnerability options filtered by VM type/services
- Attack narrative optional, integrates with MSEL

**Vulnerability Categories**:
- Network Services (open ports, weak protocols)
- Web Applications (SQLi, XSS, CSRF)
- Credentials (default passwords, weak keys)
- Misconfigurations (permissive ACLs, debug modes)

---

## Step 6: Review & Deploy

**Purpose**: Final validation and one-click deployment.

**Layout**:
```
┌─────────────────────────────────────────────────────────────────┐
│  Review & Deploy                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    NETWORK TOPOLOGY                          ││
│  │     [React Flow read-only view of complete topology]         ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ▼ Environment        ▼ Networks (3)      ▼ Users (8)           │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │ Type: Enterprise  │ DMZ: 10.1.0/24    │ 2 Red Team          │
│  │ Services: 4       │ Corp: 10.2.0/24   │ 4 Blue Team         │
│  │ Difficulty: Med   │ Mgmt: 10.0.0/24   │ 2 White Cell        │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│                                                                  │
│  ▼ VMs (6)            ▼ Vulnerabilities                         │
│  ┌──────────────┐    ┌──────────────┐                           │
│  │ web-srv-01      │ Preset: Intermediate                       │
│  │ db-srv-01       │ 12 vulnerabilities                         │
│  │ fw-01           │ Attack narrative: ✓                        │
│  │ ...             │                                            │
│  └──────────────┘    └──────────────┘                           │
│                                                                  │
│  Range Name: [Corporate Breach Exercise_____________]           │
│                                                                  │
│  ┌────────────────┐  ┌─────────────────────────────────┐        │
│  │ ← Back         │  │  Create & Deploy Range          │        │
│  └────────────────┘  └─────────────────────────────────┘        │
│                      ☐ Save as Blueprint for future use          │
└─────────────────────────────────────────────────────────────────┘
```

**On Deploy**:
1. Validate all required fields complete
2. Create Range record in database
3. Create Network records with subnets
4. Create VM records with configurations
5. If "Save as Blueprint" checked, create RangeBlueprint
6. Queue `deploy_range_task.send(range_id)` via Dramatiq
7. Redirect to `/ranges/{id}` with deployment status

---

## File Structure

```
frontend/src/
├── pages/
│   └── RangeWizard.tsx              # Main wizard page
├── components/
│   └── wizard/
│       ├── WizardLayout.tsx         # Sidebar + content layout
│       ├── WizardSidebar.tsx        # Step navigation
│       ├── steps/
│       │   ├── EnvironmentStep.tsx  # Step 1
│       │   ├── ServicesStep.tsx     # Step 2
│       │   ├── NetworkStep.tsx      # Step 3 (React Flow)
│       │   ├── UsersStep.tsx        # Step 4
│       │   ├── VulnsStep.tsx        # Step 5
│       │   └── ReviewStep.tsx       # Step 6
│       ├── nodes/
│       │   ├── NetworkNode.tsx      # React Flow network node
│       │   ├── VMNode.tsx           # React Flow VM node
│       │   └── RouterNode.tsx       # React Flow router node
│       └── panels/
│           ├── PropertiesPanel.tsx  # Node properties editor
│           └── PalettePanel.tsx     # Drag source palette
└── stores/
    └── wizardStore.ts               # Zustand state management
```

## Dependencies

**New packages to install**:
- `reactflow` - Network topology visualization
- `@dagrejs/dagre` - Auto-layout algorithm (optional)

---

## API Integration

**Existing endpoints used**:
- `GET /templates` - Load VM templates for selection
- `POST /ranges` - Create range (extended payload)
- `POST /ranges/{id}/networks` - Create networks
- `POST /ranges/{id}/vms` - Create VMs
- `POST /blueprints` - Save as blueprint (optional)

**Payload extension for POST /ranges**:
```typescript
interface CreateRangeFromWizard {
  name: string;
  description?: string;
  networks: NetworkConfig[];
  vms: VMConfig[];
  users?: UserConfig[];
  vulnerabilities?: VulnConfig;
  saveAsBlueprint?: boolean;
}
```

---

## Success Criteria

1. User can create a complete range in under 5 minutes
2. Network topology is visually clear and editable
3. Semi-automatic VM generation reduces manual work by 70%
4. Vulnerability presets enable training-ready ranges instantly
5. Review step catches configuration errors before deployment
6. Blueprint save enables range reuse across exercises
