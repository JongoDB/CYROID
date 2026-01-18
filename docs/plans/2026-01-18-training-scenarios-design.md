# Training Scenarios Design

> **Issue:** #25 - Pre-built artifact/MSEL templates with dropdown selection for common scenario events

## Overview

Training Scenarios are pre-built MSEL packages that users can apply to their ranges with one click. Each scenario contains a sequence of inject events targeting specific VM roles, enabling realistic cyber training exercises without manual MSEL authoring.

## Goals

- Ship 4 complete, ready-to-use training scenarios
- Enable instructors to deploy scenarios to ranges in seconds
- Simplify VM targeting via role-based mapping
- Integrate with existing MSEL/Inject execution system

## Architecture

### Data Flow

1. Scenarios stored as YAML in `data/seed-scenarios/`
2. Seeded to database on startup (like VM Templates)
3. User on Range Detail clicks "Add Scenario"
4. Picks scenario → maps VMs to required roles
5. System generates MSEL + Injects targeting mapped VMs
6. Existing MSEL execution handles the rest

### New Components

- `Scenario` model (seed data, read-only)
- Scenario seeder service
- API endpoints for scenarios
- Frontend: Training Scenarios page, picker modal, VM mapping form

## Data Model

### Scenario Model

```python
class Scenario(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "scenarios"

    name: str                    # "Ransomware Attack"
    description: str             # Full description
    category: str                # "red-team", "blue-team", "insider-threat"
    difficulty: str              # "beginner", "intermediate", "advanced"
    duration_minutes: int        # Estimated scenario duration
    event_count: int             # Number of events
    required_roles: List[str]    # ["domain-controller", "workstation", "file-server"]
    events: dict                 # JSON blob of event definitions

    # Seed identification
    is_seed: bool = True
    seed_id: str                 # "ransomware-attack"
```

### Scenario YAML Structure

```yaml
seed_id: ransomware-attack
name: Ransomware Attack
description: |
  Simulates a ransomware attack starting from initial phishing payload
  through to file encryption and ransom note deployment.
category: red-team
difficulty: intermediate
duration_minutes: 60
required_roles:
  - domain-controller
  - workstation
  - file-server

events:
  - sequence: 1
    delay_minutes: 0
    title: "Initial Access - Phishing payload executed"
    description: "User executes malicious email attachment"
    target_role: workstation
    actions:
      - type: drop_file
        path: "C:\\Users\\Public\\invoice.exe"
        content_base64: "..."
      - type: create_scheduled_task
        name: "WindowsUpdate"
        command: "C:\\Users\\Public\\invoice.exe"
        trigger: "at_logon"

  - sequence: 2
    delay_minutes: 5
    title: "Persistence established"
    target_role: workstation
    actions:
      - type: registry_add
        path: "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run"
        name: "WindowsUpdate"
        value: "C:\\Users\\Public\\invoice.exe"
```

## API Endpoints

### List Scenarios

```
GET /api/v1/scenarios

Response: [
  {
    id: UUID,
    name: "Ransomware Attack",
    description: "...",
    category: "red-team",
    difficulty: "intermediate",
    duration_minutes: 60,
    event_count: 8,
    required_roles: ["domain-controller", "workstation", "file-server"]
  },
  ...
]
```

### Get Scenario Details

```
GET /api/v1/scenarios/{id}

Response: {
  id: UUID,
  name: "Ransomware Attack",
  description: "...",
  category: "red-team",
  difficulty: "intermediate",
  duration_minutes: 60,
  event_count: 8,
  required_roles: ["domain-controller", "workstation", "file-server"],
  events: [...]
}
```

### Apply Scenario to Range

```
POST /api/v1/ranges/{range_id}/scenario

Body: {
  scenario_id: UUID,
  role_mapping: {
    "domain-controller": "vm-uuid-1",
    "workstation": "vm-uuid-2",
    "file-server": "vm-uuid-3"
  }
}

Response: {
  msel_id: UUID,
  inject_count: 8,
  status: "applied"
}
```

**Apply logic:**
1. Validate all required roles are mapped
2. Create MSEL record for range (replaces existing if any)
3. Generate Inject records from scenario events
4. Substitute `target_role` with actual VM IDs from mapping
5. Return created MSEL ID

## UI Design

### Training Scenarios Page

New page at `/scenarios` showing scenario cards in a grid:

- Card displays: name, description preview, category icon, difficulty badge, duration, event count
- Filter by category (red-team, blue-team, insider-threat)
- Search by name
- Cards are view-only (no edit/delete - seed data)

### Range Detail Integration

- New "Add Scenario" button in Range Detail header
- Opens scenario picker modal

### Scenario Picker Modal

```
┌─────────────────────────────────────────────────────────────────┐
│  Add Training Scenario                                     [X]  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [Search...]                    [Filter: All Categories ▾]     │
│                                                                 │
│  ┌─────────────────────┐  ┌─────────────────────┐              │
│  │ 🔴 Ransomware       │  │ 🔴 APT Intrusion    │              │
│  │ Attack              │  │                     │              │
│  │                     │  │ Phishing → Backdoor │              │
│  │ Initial access →    │  │ → Lateral Movement  │              │
│  │ Encryption → Note   │  │ → Exfiltration      │              │
│  │                     │  │                     │              │
│  │ ⏱ 60 min · 8 events │  │ ⏱ 120 min · 12 evts │              │
│  │ ⚡ Intermediate     │  │ ⚡ Advanced          │              │
│  └─────────────────────┘  └─────────────────────┘              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### VM Mapping Modal

After selecting scenario:

```
┌─────────────────────────────────────────────────────────────────┐
│  Configure: Ransomware Attack                              [X]  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  This scenario requires 3 target systems.                       │
│  Map each role to a VM in your range:                          │
│                                                                 │
│  Domain Controller     [dc01 (Windows Server 2022) ▾]          │
│  Workstation           [ws01 (Windows 10)          ▾]          │
│  File Server           [fs01 (Windows Server 2022) ▾]          │
│                                                                 │
│                              [Cancel]  [Apply Scenario]         │
└─────────────────────────────────────────────────────────────────┘
```

## The Four Scenarios

### 1. Ransomware Attack

- **Category:** red-team
- **Difficulty:** intermediate
- **Duration:** 60 minutes
- **Events:** 8
- **Required roles:** domain-controller, workstation, file-server

**Event sequence:**
1. T+0: Phishing payload dropped on workstation
2. T+5: Payload executes, establishes persistence
3. T+10: Discovery - enumerate network shares
4. T+15: Credential dump from LSASS
5. T+20: Lateral movement to file server
6. T+30: Disable shadow copies
7. T+45: Encrypt files (simulation - renames only)
8. T+50: Drop ransom note

### 2. APT Intrusion

- **Category:** red-team
- **Difficulty:** advanced
- **Duration:** 120 minutes
- **Events:** 12
- **Required roles:** domain-controller, workstation, webserver

**Event sequence:**
1. T+0: Spearphishing payload on workstation
2. T+5: C2 beacon established
3. T+15: Local enumeration
4. T+25: AD enumeration (BloodHound-style)
5. T+35: Kerberoasting attempt
6. T+45: Credential harvesting
7. T+55: Lateral movement to webserver
8. T+70: Webshell deployed
9. T+85: Privilege escalation on DC
10. T+95: Data staging
11. T+105: Data exfiltration
12. T+115: Cover tracks

### 3. Insider Threat

- **Category:** insider-threat
- **Difficulty:** beginner
- **Duration:** 45 minutes
- **Events:** 6
- **Required roles:** workstation, file-server

**Event sequence:**
1. T+0: After-hours login on workstation
2. T+10: Browse to sensitive file shares
3. T+20: Copy sensitive files to staging folder
4. T+30: Create archive of staged files
5. T+35: Email archive to external address
6. T+40: Delete staging folder (cover tracks)

### 4. Incident Response Drill

- **Category:** blue-team
- **Difficulty:** intermediate
- **Duration:** 30 minutes (setup), then hunt
- **Events:** 10 (artifacts planted)
- **Required roles:** domain-controller, workstation, webserver

**Artifacts planted:**
1. Malicious local admin account on DC
2. Suspicious scheduled task on workstation
3. Webshell in webserver root
4. Modified hosts file on workstation
5. Suspicious PowerShell in event logs
6. Backdoor user in Domain Admins
7. Hidden file in System32
8. Suspicious outbound firewall rule
9. Modified registry Run key
10. Planted credentials file

## Naming Updates

As part of this feature:

| Current | New |
|---------|-----|
| Templates | VM Templates |
| Blueprints | Range Blueprints |
| Guided Builder | Range Wizard |
| (new) | Training Scenarios |

**Sidebar order:**
1. Dashboard
2. Image Cache
3. VM Templates
4. Range Blueprints
5. Training Scenarios
6. Ranges
7. Users
8. Artifacts

## Range Wizard Integration

Add optional final step to Range Wizard:

- Title: "Add Training Scenario? (Optional)"
- Shows same scenario card picker
- If selected, auto-maps VMs based on wizard-assigned roles
- User can skip to create range without scenario

## Out of Scope (Future)

- Walkthrough content in scenarios (for Student Lab page)
- Custom scenario creation UI
- Scenario customization/editing before apply
- Full artifact library management
- Event template builder (200+ event library)
- Scenario versioning

## Dependencies

- Existing MSEL/Inject models (no changes)
- Existing inject execution via Docker exec
- Seed template pattern (already proven with VM Templates)

## Success Criteria

1. User can browse 4 pre-built scenarios on Training Scenarios page
2. User can apply scenario to range with VM role mapping
3. Applied scenario creates MSEL with executable injects
4. Injects execute successfully on mapped VMs
5. All naming updates applied consistently
