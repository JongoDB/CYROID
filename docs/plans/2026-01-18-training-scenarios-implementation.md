# Training Scenarios Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement pre-built training scenarios that users can apply to ranges with one click, including role-based VM mapping.

**Architecture:** Scenarios are stored as YAML files in `data/seed-scenarios/`, seeded to a new `Scenario` database model on startup. Users select scenarios from a picker modal on the Range Detail page, map VMs to required roles, and the system generates an MSEL with injects targeting the mapped VMs.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, React, TypeScript, Tailwind CSS

---

## Task 1: Create Scenario Model

**Files:**
- Create: `backend/cyroid/models/scenario.py`
- Modify: `backend/cyroid/models/__init__.py:17-36`

**Step 1: Create the Scenario model file**

Create `backend/cyroid/models/scenario.py`:

```python
# backend/cyroid/models/scenario.py
from typing import Optional, List
from sqlalchemy import String, Integer, Text, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from cyroid.models.base import Base, TimestampMixin, UUIDMixin


class Scenario(Base, UUIDMixin, TimestampMixin):
    """Pre-built training scenario with event sequences."""
    __tablename__ = "scenarios"

    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # red-team, blue-team, insider-threat
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False)  # beginner, intermediate, advanced
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False)
    required_roles: Mapped[List[str]] = mapped_column(JSON, default=list)  # ["domain-controller", "workstation"]
    events: Mapped[List[dict]] = mapped_column(JSON, default=list)  # Event definitions

    # Seed identification
    is_seed: Mapped[bool] = mapped_column(Boolean, default=True)
    seed_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, unique=True)
```

**Step 2: Add Scenario to models __init__.py**

Add import and export in `backend/cyroid/models/__init__.py`:

```python
from cyroid.models.scenario import Scenario

# Add to __all__ list:
"Scenario",
```

**Step 3: Create database migration**

Run:
```bash
cd /Users/JonWFH/jondev/CYROID && docker compose exec api alembic revision --autogenerate -m "Add Scenario model"
```

**Step 4: Apply migration**

Run:
```bash
cd /Users/JonWFH/jondev/CYROID && docker compose exec api alembic upgrade head
```

**Step 5: Commit**

```bash
git add backend/cyroid/models/scenario.py backend/cyroid/models/__init__.py
git add backend/alembic/versions/
git commit -m "feat: add Scenario model for training scenarios

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 2: Create Scenario Schemas

**Files:**
- Create: `backend/cyroid/schemas/scenario.py`

**Step 1: Create the Pydantic schemas**

Create `backend/cyroid/schemas/scenario.py`:

```python
# backend/cyroid/schemas/scenario.py
from datetime import datetime
from typing import Optional, List, Any
from uuid import UUID
from pydantic import BaseModel, Field


class ScenarioEvent(BaseModel):
    """A single event within a scenario."""
    sequence: int
    delay_minutes: int
    title: str
    description: Optional[str] = None
    target_role: str
    actions: List[dict] = Field(default_factory=list)


class ScenarioBase(BaseModel):
    """Base scenario fields."""
    name: str = Field(..., min_length=1, max_length=100)
    description: str
    category: str = Field(..., pattern="^(red-team|blue-team|insider-threat)$")
    difficulty: str = Field(..., pattern="^(beginner|intermediate|advanced)$")
    duration_minutes: int = Field(..., ge=1)
    event_count: int = Field(..., ge=1)
    required_roles: List[str]


class ScenarioListResponse(ScenarioBase):
    """Scenario response for list endpoint (no events)."""
    id: UUID
    is_seed: bool = True
    seed_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ScenarioDetailResponse(ScenarioListResponse):
    """Full scenario response including events."""
    events: List[ScenarioEvent]


class ApplyScenarioRequest(BaseModel):
    """Request to apply a scenario to a range."""
    scenario_id: UUID
    role_mapping: dict  # {"domain-controller": "vm-uuid-1", "workstation": "vm-uuid-2"}


class ApplyScenarioResponse(BaseModel):
    """Response after applying a scenario."""
    msel_id: UUID
    inject_count: int
    status: str = "applied"
```

**Step 2: Commit**

```bash
git add backend/cyroid/schemas/scenario.py
git commit -m "feat: add Scenario Pydantic schemas

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 3: Create Scenario Seeder Service

**Files:**
- Create: `backend/cyroid/services/scenario_seeder.py`
- Create: `data/seed-scenarios/manifest.yaml`

**Step 1: Create the scenario seeder service**

Create `backend/cyroid/services/scenario_seeder.py`:

```python
# backend/cyroid/services/scenario_seeder.py
"""Scenario seeder service for built-in training scenarios."""

import logging
from pathlib import Path
from typing import List, Optional

import yaml
from sqlalchemy.orm import Session

from cyroid.models.scenario import Scenario

logger = logging.getLogger(__name__)

# Default path to seed scenarios directory
SEED_SCENARIOS_DIR = Path(__file__).parent.parent.parent.parent / "data" / "seed-scenarios"


def load_manifest(seed_dir: Path = SEED_SCENARIOS_DIR) -> dict:
    """Load the seed scenarios manifest."""
    manifest_path = seed_dir / "manifest.yaml"
    if not manifest_path.exists():
        logger.warning(f"Seed scenarios manifest not found at {manifest_path}")
        return {"version": 0, "scenarios": []}

    with open(manifest_path) as f:
        return yaml.safe_load(f)


def seed_scenario(db: Session, scenario_data: dict) -> Optional[Scenario]:
    """Seed or update a single scenario."""
    seed_id = scenario_data.get("seed_id")
    if not seed_id:
        logger.warning("Scenario missing seed_id, skipping")
        return None

    # Check if already exists
    existing = db.query(Scenario).filter(Scenario.seed_id == seed_id).first()

    events = scenario_data.get("events", [])
    event_count = len(events)

    if existing:
        # Update existing seed scenario
        logger.info(f"Updating seed scenario: {seed_id}")
        existing.name = scenario_data.get("name", existing.name)
        existing.description = scenario_data.get("description", existing.description)
        existing.category = scenario_data.get("category", existing.category)
        existing.difficulty = scenario_data.get("difficulty", existing.difficulty)
        existing.duration_minutes = scenario_data.get("duration_minutes", existing.duration_minutes)
        existing.event_count = event_count
        existing.required_roles = scenario_data.get("required_roles", [])
        existing.events = events
        db.flush()
        return existing
    else:
        # Create new seed scenario
        logger.info(f"Creating seed scenario: {seed_id}")
        scenario = Scenario(
            name=scenario_data.get("name", seed_id),
            description=scenario_data.get("description", ""),
            category=scenario_data.get("category", "red-team"),
            difficulty=scenario_data.get("difficulty", "intermediate"),
            duration_minutes=scenario_data.get("duration_minutes", 60),
            event_count=event_count,
            required_roles=scenario_data.get("required_roles", []),
            events=events,
            is_seed=True,
            seed_id=seed_id,
        )
        db.add(scenario)
        db.flush()
        return scenario


def seed_all_scenarios(db: Session, seed_dir: Path = SEED_SCENARIOS_DIR) -> List[Scenario]:
    """Seed all scenarios from the manifest."""
    manifest = load_manifest(seed_dir)
    seeded = []

    for entry in manifest.get("scenarios", []):
        seed_id = entry.get("seed_id")
        file_name = entry.get("file")

        if not seed_id or not file_name:
            continue

        file_path = seed_dir / file_name
        if not file_path.exists():
            logger.warning(f"Scenario file not found: {file_path}")
            continue

        with open(file_path) as f:
            scenario_data = yaml.safe_load(f)

        if scenario_data:
            scenario = seed_scenario(db, scenario_data)
            if scenario:
                seeded.append(scenario)

    db.commit()
    logger.info(f"Seeded {len(seeded)} scenarios")
    return seeded
```

**Step 2: Create the manifest file**

Create `data/seed-scenarios/manifest.yaml`:

```yaml
# Seed Scenarios Manifest
# Lists all training scenarios to be seeded on startup

version: 1
scenarios:
  - seed_id: ransomware-attack
    file: ransomware-attack.yaml
  - seed_id: apt-intrusion
    file: apt-intrusion.yaml
  - seed_id: insider-threat
    file: insider-threat.yaml
  - seed_id: incident-response-drill
    file: incident-response-drill.yaml
```

**Step 3: Commit**

```bash
git add backend/cyroid/services/scenario_seeder.py data/seed-scenarios/manifest.yaml
git commit -m "feat: add scenario seeder service

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 4: Create Scenario YAML Files

**Files:**
- Create: `data/seed-scenarios/ransomware-attack.yaml`
- Create: `data/seed-scenarios/apt-intrusion.yaml`
- Create: `data/seed-scenarios/insider-threat.yaml`
- Create: `data/seed-scenarios/incident-response-drill.yaml`

**Step 1: Create ransomware-attack.yaml**

Create `data/seed-scenarios/ransomware-attack.yaml`:

```yaml
seed_id: ransomware-attack
name: Ransomware Attack
description: |
  Simulates a ransomware attack starting from initial phishing payload
  through to file encryption and ransom note deployment. Covers initial
  access, persistence, discovery, credential access, lateral movement,
  and impact phases of the MITRE ATT&CK framework.
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
    description: "User executes malicious email attachment on workstation"
    target_role: workstation
    actions:
      - type: create_file
        path: "C:\\Users\\Public\\invoice.exe"
        content: "Simulated malicious payload"

  - sequence: 2
    delay_minutes: 5
    title: "Persistence - Scheduled task created"
    description: "Malware establishes persistence via scheduled task"
    target_role: workstation
    actions:
      - type: create_scheduled_task
        name: "WindowsUpdate"
        command: "C:\\Users\\Public\\invoice.exe"

  - sequence: 3
    delay_minutes: 10
    title: "Discovery - Network enumeration"
    description: "Attacker enumerates network shares and systems"
    target_role: workstation
    actions:
      - type: execute_command
        command: "net view /domain"

  - sequence: 4
    delay_minutes: 15
    title: "Credential Access - LSASS memory dump"
    description: "Attacker attempts to dump credentials from memory"
    target_role: workstation
    actions:
      - type: create_file
        path: "C:\\Windows\\Temp\\lsass.dmp"
        content: "Simulated credential dump"

  - sequence: 5
    delay_minutes: 20
    title: "Lateral Movement - Access file server"
    description: "Attacker moves laterally to file server using stolen credentials"
    target_role: file-server
    actions:
      - type: create_file
        path: "C:\\Windows\\Temp\\beacon.exe"
        content: "Simulated lateral movement beacon"

  - sequence: 6
    delay_minutes: 30
    title: "Defense Evasion - Disable shadow copies"
    description: "Attacker disables Volume Shadow Copy service"
    target_role: file-server
    actions:
      - type: execute_command
        command: "vssadmin delete shadows /all /quiet"

  - sequence: 7
    delay_minutes: 45
    title: "Impact - File encryption simulation"
    description: "Ransomware encrypts files (simulation renames files)"
    target_role: file-server
    actions:
      - type: create_file
        path: "C:\\Users\\Public\\Documents\\important_file.txt.encrypted"
        content: "FILE ENCRYPTED BY RANSOMWARE"

  - sequence: 8
    delay_minutes: 50
    title: "Impact - Ransom note deployment"
    description: "Ransomware drops ransom note on all systems"
    target_role: file-server
    actions:
      - type: create_file
        path: "C:\\Users\\Public\\Desktop\\README_DECRYPT.txt"
        content: |
          YOUR FILES HAVE BEEN ENCRYPTED!
          To decrypt your files, send 5 BTC to: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
          Contact: ransomware@example.com
```

**Step 2: Create apt-intrusion.yaml**

Create `data/seed-scenarios/apt-intrusion.yaml`:

```yaml
seed_id: apt-intrusion
name: APT Intrusion
description: |
  Simulates an Advanced Persistent Threat (APT) intrusion from initial
  spearphishing through to data exfiltration. Covers the full kill chain
  including C2 establishment, Active Directory reconnaissance, privilege
  escalation, and data staging.
category: red-team
difficulty: advanced
duration_minutes: 120
required_roles:
  - domain-controller
  - workstation
  - webserver

events:
  - sequence: 1
    delay_minutes: 0
    title: "Initial Access - Spearphishing payload"
    description: "Targeted phishing email delivers malicious document"
    target_role: workstation
    actions:
      - type: create_file
        path: "C:\\Users\\Public\\Documents\\Q4_Report.docm"
        content: "Simulated malicious macro document"

  - sequence: 2
    delay_minutes: 5
    title: "Command and Control - Beacon established"
    description: "Malware establishes C2 communication channel"
    target_role: workstation
    actions:
      - type: create_file
        path: "C:\\Windows\\Temp\\svchost.exe"
        content: "Simulated C2 beacon"

  - sequence: 3
    delay_minutes: 15
    title: "Discovery - Local enumeration"
    description: "Attacker gathers local system information"
    target_role: workstation
    actions:
      - type: execute_command
        command: "systeminfo && whoami /all"

  - sequence: 4
    delay_minutes: 25
    title: "Discovery - AD enumeration"
    description: "Attacker performs Active Directory reconnaissance"
    target_role: workstation
    actions:
      - type: execute_command
        command: "net user /domain && net group /domain"

  - sequence: 5
    delay_minutes: 35
    title: "Credential Access - Kerberoasting"
    description: "Attacker requests service tickets for offline cracking"
    target_role: workstation
    actions:
      - type: create_file
        path: "C:\\Users\\Public\\krb5tgs.txt"
        content: "Simulated Kerberos tickets"

  - sequence: 6
    delay_minutes: 45
    title: "Credential Access - Credential harvesting"
    description: "Attacker harvests additional credentials"
    target_role: workstation
    actions:
      - type: create_file
        path: "C:\\Windows\\Temp\\creds.txt"
        content: "Simulated harvested credentials"

  - sequence: 7
    delay_minutes: 55
    title: "Lateral Movement - Pivot to webserver"
    description: "Attacker moves to webserver using stolen credentials"
    target_role: webserver
    actions:
      - type: create_file
        path: "/tmp/.backdoor"
        content: "Simulated backdoor"

  - sequence: 8
    delay_minutes: 70
    title: "Persistence - Webshell deployed"
    description: "Attacker deploys webshell for persistent access"
    target_role: webserver
    actions:
      - type: create_file
        path: "/var/www/html/uploads/.shell.php"
        content: "<?php /* Simulated webshell */ ?>"

  - sequence: 9
    delay_minutes: 85
    title: "Privilege Escalation - Domain admin access"
    description: "Attacker escalates to domain administrator"
    target_role: domain-controller
    actions:
      - type: create_file
        path: "C:\\Windows\\Temp\\admin_token.txt"
        content: "Simulated admin token"

  - sequence: 10
    delay_minutes: 95
    title: "Collection - Data staging"
    description: "Attacker stages sensitive data for exfiltration"
    target_role: domain-controller
    actions:
      - type: create_file
        path: "C:\\Windows\\Temp\\staged_data.zip"
        content: "Simulated staged data"

  - sequence: 11
    delay_minutes: 105
    title: "Exfiltration - Data exfiltration"
    description: "Attacker exfiltrates staged data via HTTPS"
    target_role: workstation
    actions:
      - type: execute_command
        command: "echo Simulating data exfiltration to C2"

  - sequence: 12
    delay_minutes: 115
    title: "Defense Evasion - Cover tracks"
    description: "Attacker clears logs and removes artifacts"
    target_role: domain-controller
    actions:
      - type: execute_command
        command: "wevtutil cl Security"
```

**Step 3: Create insider-threat.yaml**

Create `data/seed-scenarios/insider-threat.yaml`:

```yaml
seed_id: insider-threat
name: Insider Threat
description: |
  Simulates a malicious insider scenario where an employee with legitimate
  access exfiltrates sensitive data. Covers after-hours access, unauthorized
  data access, data staging, and exfiltration attempts.
category: insider-threat
difficulty: beginner
duration_minutes: 45
required_roles:
  - workstation
  - file-server

events:
  - sequence: 1
    delay_minutes: 0
    title: "Initial Access - After-hours login"
    description: "Employee logs in outside normal business hours"
    target_role: workstation
    actions:
      - type: create_file
        path: "C:\\Users\\Public\\login_timestamp.txt"
        content: "Login at 11:45 PM - Outside business hours"

  - sequence: 2
    delay_minutes: 10
    title: "Collection - Browse sensitive shares"
    description: "Employee accesses restricted file shares"
    target_role: file-server
    actions:
      - type: execute_command
        command: "dir \\\\file-server\\Confidential"

  - sequence: 3
    delay_minutes: 20
    title: "Collection - Copy sensitive files"
    description: "Employee copies sensitive files to staging folder"
    target_role: workstation
    actions:
      - type: create_file
        path: "C:\\Users\\Public\\staging\\customer_data.xlsx"
        content: "Simulated sensitive customer data"
      - type: create_file
        path: "C:\\Users\\Public\\staging\\financial_report.pdf"
        content: "Simulated financial report"

  - sequence: 4
    delay_minutes: 30
    title: "Collection - Create archive"
    description: "Employee creates archive of staged files"
    target_role: workstation
    actions:
      - type: create_file
        path: "C:\\Users\\Public\\backup.zip"
        content: "Simulated data archive"

  - sequence: 5
    delay_minutes: 35
    title: "Exfiltration - Email to personal address"
    description: "Employee attempts to email archive to personal account"
    target_role: workstation
    actions:
      - type: create_file
        path: "C:\\Users\\Public\\outbound_email.eml"
        content: |
          To: personal@gmail.com
          Subject: Backup files
          Attachment: backup.zip

  - sequence: 6
    delay_minutes: 40
    title: "Defense Evasion - Delete staging folder"
    description: "Employee deletes staging folder to cover tracks"
    target_role: workstation
    actions:
      - type: execute_command
        command: "rmdir /s /q C:\\Users\\Public\\staging"
```

**Step 4: Create incident-response-drill.yaml**

Create `data/seed-scenarios/incident-response-drill.yaml`:

```yaml
seed_id: incident-response-drill
name: Incident Response Drill
description: |
  Blue team exercise that plants indicators of compromise across systems.
  Participants must identify and document all planted artifacts within
  the time limit. Tests detection capabilities and IR procedures.
category: blue-team
difficulty: intermediate
duration_minutes: 30
required_roles:
  - domain-controller
  - workstation
  - webserver

events:
  - sequence: 1
    delay_minutes: 0
    title: "IOC - Malicious local admin account"
    description: "Backdoor admin account created on domain controller"
    target_role: domain-controller
    actions:
      - type: create_file
        path: "C:\\Windows\\Temp\\ioc_admin_account.txt"
        content: |
          PLANTED IOC: Local admin account
          Account: backdoor_admin
          Created: During attack simulation

  - sequence: 2
    delay_minutes: 0
    title: "IOC - Suspicious scheduled task"
    description: "Malicious scheduled task on workstation"
    target_role: workstation
    actions:
      - type: create_scheduled_task
        name: "SystemHealthCheck"
        command: "C:\\Windows\\Temp\\beacon.exe"

  - sequence: 3
    delay_minutes: 0
    title: "IOC - Webshell in webserver"
    description: "PHP webshell planted in web root"
    target_role: webserver
    actions:
      - type: create_file
        path: "/var/www/html/admin/.config.php"
        content: "<?php /* PLANTED WEBSHELL - Find me! */ ?>"

  - sequence: 4
    delay_minutes: 0
    title: "IOC - Modified hosts file"
    description: "DNS poisoning via hosts file modification"
    target_role: workstation
    actions:
      - type: create_file
        path: "C:\\Windows\\System32\\drivers\\etc\\hosts.bak"
        content: |
          # PLANTED IOC - Modified hosts file
          10.0.0.99 login.microsoft.com
          10.0.0.99 update.windows.com

  - sequence: 5
    delay_minutes: 0
    title: "IOC - Suspicious PowerShell history"
    description: "Malicious PowerShell commands in history"
    target_role: workstation
    actions:
      - type: create_file
        path: "C:\\Users\\Public\\powershell_history.txt"
        content: |
          Invoke-Mimikatz -DumpCreds
          Invoke-BloodHound -CollectionMethod All
          New-PSSession -ComputerName DC01

  - sequence: 6
    delay_minutes: 0
    title: "IOC - Backdoor Domain Admins member"
    description: "Unauthorized user in Domain Admins group"
    target_role: domain-controller
    actions:
      - type: create_file
        path: "C:\\Windows\\Temp\\ioc_domain_admin.txt"
        content: |
          PLANTED IOC: Unauthorized Domain Admin
          User: svc_backup (should not be admin)

  - sequence: 7
    delay_minutes: 0
    title: "IOC - Hidden file in System32"
    description: "Suspicious hidden executable in system directory"
    target_role: workstation
    actions:
      - type: create_file
        path: "C:\\Windows\\System32\\svchost32.exe"
        content: "PLANTED IOC - Suspicious executable"

  - sequence: 8
    delay_minutes: 0
    title: "IOC - Suspicious firewall rule"
    description: "Outbound firewall rule allowing suspicious traffic"
    target_role: workstation
    actions:
      - type: create_file
        path: "C:\\Windows\\Temp\\ioc_firewall.txt"
        content: |
          PLANTED IOC: Suspicious firewall rule
          Rule: Allow_C2_Traffic
          Port: 4444 (Outbound)

  - sequence: 9
    delay_minutes: 0
    title: "IOC - Registry Run key persistence"
    description: "Malicious autorun registry entry"
    target_role: workstation
    actions:
      - type: create_file
        path: "C:\\Windows\\Temp\\ioc_registry.txt"
        content: |
          PLANTED IOC: Registry Run key
          Path: HKCU\Software\Microsoft\Windows\CurrentVersion\Run
          Name: WindowsDefenderUpdate
          Value: C:\Windows\Temp\beacon.exe

  - sequence: 10
    delay_minutes: 0
    title: "IOC - Planted credentials file"
    description: "Credential dump file left on system"
    target_role: domain-controller
    actions:
      - type: create_file
        path: "C:\\Windows\\Temp\\ntds_dump.txt"
        content: |
          PLANTED IOC - NTDS.dit dump
          Administrator:500:aad3b435b51404eeaad3b435b51404ee:31d6cfe0d16ae931b73c59d7e0c089c0
          krbtgt:502:aad3b435b51404eeaad3b435b51404ee:b21c99fc068e3ab2ca789bccbef67de4
```

**Step 5: Commit**

```bash
git add data/seed-scenarios/*.yaml
git commit -m "feat: add 4 training scenario YAML files

- Ransomware Attack (8 events, intermediate)
- APT Intrusion (12 events, advanced)
- Insider Threat (6 events, beginner)
- Incident Response Drill (10 events, intermediate)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 5: Integrate Scenario Seeding in main.py

**Files:**
- Modify: `backend/cyroid/main.py:36-49`
- Modify: `docker-compose.yml` (add volume mount)

**Step 1: Add scenario seeding to lifespan**

In `backend/cyroid/main.py`, update the lifespan function to also seed scenarios:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events for startup and shutdown."""
    # Startup
    from cyroid.services.event_broadcaster import get_connection_manager, get_broadcaster
    from cyroid.services.template_seeder import seed_all_templates
    from cyroid.services.scenario_seeder import seed_all_scenarios
    from cyroid.database import get_session_local

    # Seed built-in templates
    logger.info("Checking seed templates...")
    try:
        SessionLocal = get_session_local()
        db = SessionLocal()
        seeded = seed_all_templates(db)
        if seeded:
            logger.info(f"Seeded {len(seeded)} templates")
        db.close()
    except Exception as e:
        logger.warning(f"Template seeding skipped: {e}")

    # Seed built-in scenarios
    logger.info("Checking seed scenarios...")
    try:
        SessionLocal = get_session_local()
        db = SessionLocal()
        seeded = seed_all_scenarios(db)
        if seeded:
            logger.info(f"Seeded {len(seeded)} scenarios")
        db.close()
    except Exception as e:
        logger.warning(f"Scenario seeding skipped: {e}")

    logger.info("Starting real-time event services...")
    # ... rest of lifespan
```

**Step 2: Add volume mount in docker-compose.yml**

Add to the api service volumes:

```yaml
- ./data/seed-scenarios:/data/seed-scenarios:ro
```

**Step 3: Commit**

```bash
git add backend/cyroid/main.py docker-compose.yml
git commit -m "feat: integrate scenario seeding on startup

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 6: Create Scenarios API Router

**Files:**
- Create: `backend/cyroid/api/scenarios.py`
- Modify: `backend/cyroid/main.py` (add router)

**Step 1: Create the scenarios API router**

Create `backend/cyroid/api/scenarios.py`:

```python
# backend/cyroid/api/scenarios.py
"""Scenarios API endpoints for training scenarios."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from cyroid.api.deps import get_current_user, get_db
from cyroid.models.scenario import Scenario
from cyroid.models.user import User
from cyroid.schemas.scenario import ScenarioListResponse, ScenarioDetailResponse

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.get("", response_model=List[ScenarioListResponse])
def list_scenarios(
    category: str = None,
    difficulty: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all available training scenarios."""
    query = db.query(Scenario)

    if category:
        query = query.filter(Scenario.category == category)
    if difficulty:
        query = query.filter(Scenario.difficulty == difficulty)

    scenarios = query.order_by(Scenario.category, Scenario.difficulty).all()
    return scenarios


@router.get("/{scenario_id}", response_model=ScenarioDetailResponse)
def get_scenario(
    scenario_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a scenario with full event details."""
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return scenario
```

**Step 2: Register the router in main.py**

Add to `backend/cyroid/main.py`:

```python
from cyroid.api.scenarios import router as scenarios_router
# ...
app.include_router(scenarios_router, prefix="/api/v1")
```

Also add to openapi_tags:
```python
{"name": "scenarios", "description": "Training scenarios for cyber exercises"},
```

**Step 3: Commit**

```bash
git add backend/cyroid/api/scenarios.py backend/cyroid/main.py
git commit -m "feat: add scenarios API endpoints

- GET /scenarios - list with category/difficulty filters
- GET /scenarios/{id} - get scenario with events

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 7: Add Apply Scenario Endpoint to Ranges API

**Files:**
- Modify: `backend/cyroid/api/ranges.py`

**Step 1: Add the apply scenario endpoint**

Add to `backend/cyroid/api/ranges.py`:

```python
from cyroid.models.scenario import Scenario
from cyroid.schemas.scenario import ApplyScenarioRequest, ApplyScenarioResponse


@router.post("/{range_id}/scenario", response_model=ApplyScenarioResponse)
def apply_scenario(
    range_id: UUID,
    request: ApplyScenarioRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Apply a training scenario to a range, generating MSEL and injects."""
    # Get range
    range_obj = db.query(Range).filter(Range.id == range_id).first()
    if not range_obj:
        raise HTTPException(status_code=404, detail="Range not found")

    # Get scenario
    scenario = db.query(Scenario).filter(Scenario.id == request.scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    # Validate role mapping - all required roles must be mapped
    missing_roles = set(scenario.required_roles) - set(request.role_mapping.keys())
    if missing_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Missing role mappings: {', '.join(missing_roles)}"
        )

    # Validate VM IDs exist in this range
    vm_ids = set(request.role_mapping.values())
    existing_vms = db.query(VM).filter(
        VM.range_id == range_id,
        VM.id.in_([UUID(vid) for vid in vm_ids])
    ).all()
    existing_vm_ids = {str(vm.id) for vm in existing_vms}
    invalid_vms = vm_ids - existing_vm_ids
    if invalid_vms:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid VM IDs: {', '.join(invalid_vms)}"
        )

    # Delete existing MSEL if any
    existing_msel = db.query(MSEL).filter(MSEL.range_id == range_id).first()
    if existing_msel:
        db.delete(existing_msel)
        db.flush()

    # Create MSEL content from scenario
    msel_content = f"# {scenario.name}\n\n{scenario.description}\n\n"
    msel_content += "## Events\n\n"
    for event in scenario.events:
        msel_content += f"### T+{event['delay_minutes']}min: {event['title']}\n"
        msel_content += f"{event.get('description', '')}\n\n"

    # Create MSEL
    msel = MSEL(
        range_id=range_id,
        name=f"Scenario: {scenario.name}",
        content=msel_content,
    )
    db.add(msel)
    db.flush()

    # Create Injects from scenario events
    inject_count = 0
    for event in scenario.events:
        # Map target_role to actual VM ID
        target_role = event.get("target_role", "")
        target_vm_id = request.role_mapping.get(target_role)

        inject = Inject(
            msel_id=msel.id,
            sequence_number=event["sequence"],
            inject_time_minutes=event["delay_minutes"],
            title=event["title"],
            description=event.get("description"),
            target_vm_ids=[target_vm_id] if target_vm_id else [],
            actions=event.get("actions", []),
            status=InjectStatus.PENDING,
        )
        db.add(inject)
        inject_count += 1

    db.commit()

    return ApplyScenarioResponse(
        msel_id=msel.id,
        inject_count=inject_count,
        status="applied"
    )
```

**Step 2: Add necessary imports at top of ranges.py**

```python
from cyroid.models.scenario import Scenario
from cyroid.models.msel import MSEL
from cyroid.models.inject import Inject, InjectStatus
from cyroid.schemas.scenario import ApplyScenarioRequest, ApplyScenarioResponse
```

**Step 3: Commit**

```bash
git add backend/cyroid/api/ranges.py
git commit -m "feat: add apply scenario endpoint to ranges API

POST /ranges/{id}/scenario - applies scenario with VM role mapping

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 8: Update Frontend Types

**Files:**
- Modify: `frontend/src/types/index.ts`

**Step 1: Add Scenario types**

Add to `frontend/src/types/index.ts`:

```typescript
// Training Scenarios
export interface ScenarioEvent {
  sequence: number
  delay_minutes: number
  title: string
  description?: string
  target_role: string
  actions: Array<{
    type: string
    [key: string]: any
  }>
}

export interface Scenario {
  id: string
  name: string
  description: string
  category: 'red-team' | 'blue-team' | 'insider-threat'
  difficulty: 'beginner' | 'intermediate' | 'advanced'
  duration_minutes: number
  event_count: number
  required_roles: string[]
  is_seed: boolean
  seed_id?: string
  created_at: string
  updated_at: string
}

export interface ScenarioDetail extends Scenario {
  events: ScenarioEvent[]
}

export interface ApplyScenarioRequest {
  scenario_id: string
  role_mapping: Record<string, string>  // role -> VM ID
}

export interface ApplyScenarioResponse {
  msel_id: string
  inject_count: number
  status: string
}
```

**Step 2: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat: add Scenario types to frontend

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 9: Add Scenarios API to Frontend

**Files:**
- Modify: `frontend/src/services/api.ts`

**Step 1: Add scenarios API functions**

Add to `frontend/src/services/api.ts`:

```typescript
import type { Scenario, ScenarioDetail, ApplyScenarioRequest, ApplyScenarioResponse } from '../types'

// Scenarios API
export const scenariosApi = {
  list: (category?: string, difficulty?: string) => {
    const params = new URLSearchParams()
    if (category) params.append('category', category)
    if (difficulty) params.append('difficulty', difficulty)
    const query = params.toString()
    return api.get<Scenario[]>(`/scenarios${query ? `?${query}` : ''}`)
  },
  get: (id: string) => api.get<ScenarioDetail>(`/scenarios/${id}`),
}

// Add to rangesApi object:
export const rangesApi = {
  // ... existing methods ...
  applyScenario: (rangeId: string, data: ApplyScenarioRequest) =>
    api.post<ApplyScenarioResponse>(`/ranges/${rangeId}/scenario`, data),
}
```

**Step 2: Commit**

```bash
git add frontend/src/services/api.ts
git commit -m "feat: add scenarios API to frontend service

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 10: Create Training Scenarios Page

**Files:**
- Create: `frontend/src/pages/TrainingScenarios.tsx`

**Step 1: Create the Training Scenarios page component**

Create `frontend/src/pages/TrainingScenarios.tsx`:

```tsx
// frontend/src/pages/TrainingScenarios.tsx
import { useEffect, useState } from 'react'
import { scenariosApi } from '../services/api'
import type { Scenario } from '../types'
import { Loader2, Target, Shield, UserX, Clock, Zap, AlertTriangle } from 'lucide-react'
import clsx from 'clsx'

const categoryConfig = {
  'red-team': {
    label: 'Red Team',
    icon: Target,
    color: 'text-red-600',
    bgColor: 'bg-red-100',
  },
  'blue-team': {
    label: 'Blue Team',
    icon: Shield,
    color: 'text-blue-600',
    bgColor: 'bg-blue-100',
  },
  'insider-threat': {
    label: 'Insider Threat',
    icon: UserX,
    color: 'text-yellow-600',
    bgColor: 'bg-yellow-100',
  },
}

const difficultyConfig = {
  beginner: { label: 'Beginner', color: 'bg-green-100 text-green-800' },
  intermediate: { label: 'Intermediate', color: 'bg-yellow-100 text-yellow-800' },
  advanced: { label: 'Advanced', color: 'bg-red-100 text-red-800' },
}

export default function TrainingScenarios() {
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [loading, setLoading] = useState(true)
  const [categoryFilter, setCategoryFilter] = useState<string>('')
  const [searchQuery, setSearchQuery] = useState('')

  const fetchScenarios = async () => {
    try {
      const response = await scenariosApi.list(categoryFilter || undefined)
      setScenarios(response.data)
    } catch (err) {
      console.error('Failed to fetch scenarios:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchScenarios()
  }, [categoryFilter])

  const filteredScenarios = scenarios.filter((s) =>
    s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    s.description.toLowerCase().includes(searchQuery.toLowerCase())
  )

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    )
  }

  return (
    <div>
      <div className="sm:flex sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Training Scenarios</h1>
          <p className="mt-2 text-sm text-gray-700">
            Pre-built cyber training scenarios ready to deploy to your ranges
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="mt-6 flex flex-col sm:flex-row gap-4">
        <input
          type="text"
          placeholder="Search scenarios..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="flex-1 rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
        />
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
        >
          <option value="">All Categories</option>
          <option value="red-team">Red Team</option>
          <option value="blue-team">Blue Team</option>
          <option value="insider-threat">Insider Threat</option>
        </select>
      </div>

      {filteredScenarios.length === 0 ? (
        <div className="mt-8 text-center">
          <AlertTriangle className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900">No scenarios found</h3>
          <p className="mt-1 text-sm text-gray-500">
            {searchQuery || categoryFilter
              ? 'Try adjusting your filters.'
              : 'Training scenarios will appear here once seeded.'}
          </p>
        </div>
      ) : (
        <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {filteredScenarios.map((scenario) => {
            const catConfig = categoryConfig[scenario.category]
            const diffConfig = difficultyConfig[scenario.difficulty]
            const CategoryIcon = catConfig.icon

            return (
              <div
                key={scenario.id}
                className="bg-white rounded-lg shadow overflow-hidden hover:shadow-md transition-shadow"
              >
                <div className="p-5">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center">
                      <div className={clsx("flex-shrink-0 rounded-md p-2", catConfig.bgColor)}>
                        <CategoryIcon className={clsx("h-6 w-6", catConfig.color)} />
                      </div>
                      <div className="ml-3">
                        <h3 className="text-sm font-medium text-gray-900">{scenario.name}</h3>
                        <span className={clsx("inline-block mt-1 text-xs px-2 py-0.5 rounded", diffConfig.color)}>
                          {diffConfig.label}
                        </span>
                      </div>
                    </div>
                  </div>

                  <p className="mt-3 text-sm text-gray-500 line-clamp-3">
                    {scenario.description}
                  </p>

                  <div className="mt-4 flex items-center text-xs text-gray-500 space-x-4">
                    <span className="flex items-center">
                      <Clock className="h-3.5 w-3.5 mr-1" />
                      {scenario.duration_minutes} min
                    </span>
                    <span className="flex items-center">
                      <Zap className="h-3.5 w-3.5 mr-1" />
                      {scenario.event_count} events
                    </span>
                  </div>

                  <div className="mt-3">
                    <p className="text-xs text-gray-400 mb-1">Required roles:</p>
                    <div className="flex flex-wrap gap-1">
                      {scenario.required_roles.map((role) => (
                        <span
                          key={role}
                          className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700"
                        >
                          {role}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="bg-gray-50 px-5 py-3">
                  <p className="text-xs text-gray-500">
                    Deploy this scenario from a Range's detail page
                  </p>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
```

**Step 2: Commit**

```bash
git add frontend/src/pages/TrainingScenarios.tsx
git commit -m "feat: add Training Scenarios page component

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 11: Update Sidebar and Routing

**Files:**
- Modify: `frontend/src/components/layout/Layout.tsx`
- Modify: `frontend/src/App.tsx`

**Step 1: Update sidebar navigation with renamed items and new page**

Update `frontend/src/components/layout/Layout.tsx`:

```tsx
import {
  LayoutDashboard,
  Server,
  Network,
  FileBox,
  LogOut,
  Menu,
  X,
  HardDrive,
  Users,
  Shield,
  Key,
  LayoutTemplate,
  Target  // Add for Training Scenarios
} from 'lucide-react'

const navigation: NavItem[] = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Image Cache', href: '/cache', icon: HardDrive },
  { name: 'VM Templates', href: '/templates', icon: Server },  // Renamed
  { name: 'Range Blueprints', href: '/blueprints', icon: LayoutTemplate },  // Renamed
  { name: 'Training Scenarios', href: '/scenarios', icon: Target },  // New
  { name: 'Ranges', href: '/ranges', icon: Network },
  { name: 'Users', href: '/users', icon: Users, adminOnly: true },
  { name: 'Artifacts', href: '/artifacts', icon: FileBox },
]
```

**Step 2: Add route in App.tsx**

Update `frontend/src/App.tsx`:

```tsx
import TrainingScenarios from './pages/TrainingScenarios'

// In the Routes:
<Route path="/scenarios" element={<TrainingScenarios />} />
```

**Step 3: Update page titles**

In `frontend/src/pages/Templates.tsx`, update the title:
```tsx
<h1 className="text-2xl font-bold text-gray-900">VM Templates</h1>
```

In `frontend/src/pages/Blueprints.tsx`, update the title:
```tsx
<h1 className="text-2xl font-bold text-gray-900">Range Blueprints</h1>
```

**Step 4: Commit**

```bash
git add frontend/src/components/layout/Layout.tsx frontend/src/App.tsx
git add frontend/src/pages/Templates.tsx frontend/src/pages/Blueprints.tsx
git commit -m "feat: add Training Scenarios to sidebar, rename Templates/Blueprints

- Templates → VM Templates
- Blueprints → Range Blueprints
- Add Training Scenarios nav item

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 12: Create Scenario Picker Modal Component

**Files:**
- Create: `frontend/src/components/scenarios/ScenarioPickerModal.tsx`
- Create: `frontend/src/components/scenarios/index.ts`

**Step 1: Create the ScenarioPickerModal component**

Create `frontend/src/components/scenarios/ScenarioPickerModal.tsx`:

```tsx
// frontend/src/components/scenarios/ScenarioPickerModal.tsx
import { useEffect, useState } from 'react'
import { scenariosApi } from '../../services/api'
import type { Scenario } from '../../types'
import { X, Loader2, Target, Shield, UserX, Clock, Zap, Search } from 'lucide-react'
import clsx from 'clsx'

interface ScenarioPickerModalProps {
  onSelect: (scenario: Scenario) => void
  onClose: () => void
}

const categoryConfig = {
  'red-team': {
    label: 'Red Team',
    icon: Target,
    color: 'text-red-600',
    bgColor: 'bg-red-100',
    borderColor: 'border-red-200',
  },
  'blue-team': {
    label: 'Blue Team',
    icon: Shield,
    color: 'text-blue-600',
    bgColor: 'bg-blue-100',
    borderColor: 'border-blue-200',
  },
  'insider-threat': {
    label: 'Insider Threat',
    icon: UserX,
    color: 'text-yellow-600',
    bgColor: 'bg-yellow-100',
    borderColor: 'border-yellow-200',
  },
}

const difficultyConfig = {
  beginner: { label: 'Beginner', color: 'bg-green-100 text-green-800' },
  intermediate: { label: 'Intermediate', color: 'bg-yellow-100 text-yellow-800' },
  advanced: { label: 'Advanced', color: 'bg-red-100 text-red-800' },
}

export default function ScenarioPickerModal({ onSelect, onClose }: ScenarioPickerModalProps) {
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [categoryFilter, setCategoryFilter] = useState<string>('')

  useEffect(() => {
    const fetchScenarios = async () => {
      try {
        const response = await scenariosApi.list(categoryFilter || undefined)
        setScenarios(response.data)
      } catch (err) {
        console.error('Failed to fetch scenarios:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchScenarios()
  }, [categoryFilter])

  const filteredScenarios = scenarios.filter((s) =>
    s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    s.description.toLowerCase().includes(searchQuery.toLowerCase())
  )

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4">
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75" onClick={onClose} />

        <div className="relative bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[85vh] overflow-hidden">
          <div className="flex items-center justify-between p-4 border-b sticky top-0 bg-white z-10">
            <h3 className="text-lg font-medium text-gray-900">Add Training Scenario</h3>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-500">
              <X className="h-5 w-5" />
            </button>
          </div>

          <div className="p-4 border-b bg-gray-50">
            <div className="flex gap-3">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search scenarios..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                />
              </div>
              <select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
              >
                <option value="">All Categories</option>
                <option value="red-team">Red Team</option>
                <option value="blue-team">Blue Team</option>
                <option value="insider-threat">Insider Threat</option>
              </select>
            </div>
          </div>

          <div className="p-4 overflow-y-auto max-h-[calc(85vh-140px)]">
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
              </div>
            ) : filteredScenarios.length === 0 ? (
              <div className="text-center py-12">
                <p className="text-sm text-gray-500">No scenarios found</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {filteredScenarios.map((scenario) => {
                  const catConfig = categoryConfig[scenario.category]
                  const diffConfig = difficultyConfig[scenario.difficulty]
                  const CategoryIcon = catConfig.icon

                  return (
                    <button
                      key={scenario.id}
                      onClick={() => onSelect(scenario)}
                      className={clsx(
                        "text-left p-4 rounded-lg border-2 hover:border-primary-500 transition-colors",
                        catConfig.borderColor
                      )}
                    >
                      <div className="flex items-start">
                        <div className={clsx("flex-shrink-0 rounded-md p-2", catConfig.bgColor)}>
                          <CategoryIcon className={clsx("h-5 w-5", catConfig.color)} />
                        </div>
                        <div className="ml-3 flex-1">
                          <div className="flex items-center justify-between">
                            <h4 className="text-sm font-medium text-gray-900">{scenario.name}</h4>
                            <span className={clsx("text-xs px-2 py-0.5 rounded", diffConfig.color)}>
                              {diffConfig.label}
                            </span>
                          </div>
                          <p className="mt-1 text-xs text-gray-500 line-clamp-2">
                            {scenario.description}
                          </p>
                          <div className="mt-2 flex items-center text-xs text-gray-400 space-x-3">
                            <span className="flex items-center">
                              <Clock className="h-3 w-3 mr-1" />
                              {scenario.duration_minutes} min
                            </span>
                            <span className="flex items-center">
                              <Zap className="h-3 w-3 mr-1" />
                              {scenario.event_count} events
                            </span>
                          </div>
                        </div>
                      </div>
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
```

**Step 2: Create index.ts barrel export**

Create `frontend/src/components/scenarios/index.ts`:

```typescript
export { default as ScenarioPickerModal } from './ScenarioPickerModal'
```

**Step 3: Commit**

```bash
git add frontend/src/components/scenarios/
git commit -m "feat: add ScenarioPickerModal component

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 13: Create VM Mapping Modal Component

**Files:**
- Create: `frontend/src/components/scenarios/VMMappingModal.tsx`
- Modify: `frontend/src/components/scenarios/index.ts`

**Step 1: Create the VMMappingModal component**

Create `frontend/src/components/scenarios/VMMappingModal.tsx`:

```tsx
// frontend/src/components/scenarios/VMMappingModal.tsx
import { useState } from 'react'
import type { Scenario, VM } from '../../types'
import { X, Loader2, Server, ChevronDown } from 'lucide-react'

interface VMMappingModalProps {
  scenario: Scenario
  vms: VM[]
  onApply: (roleMapping: Record<string, string>) => Promise<void>
  onBack: () => void
  onClose: () => void
}

// Convert role slug to display name
function formatRoleName(role: string): string {
  return role
    .split('-')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

export default function VMMappingModal({
  scenario,
  vms,
  onApply,
  onBack,
  onClose,
}: VMMappingModalProps) {
  const [roleMapping, setRoleMapping] = useState<Record<string, string>>({})
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleVMSelect = (role: string, vmId: string) => {
    setRoleMapping((prev) => ({ ...prev, [role]: vmId }))
  }

  const allRolesMapped = scenario.required_roles.every((role) => roleMapping[role])

  const handleApply = async () => {
    if (!allRolesMapped) return

    setSubmitting(true)
    setError(null)
    try {
      await onApply(roleMapping)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to apply scenario')
      setSubmitting(false)
    }
  }

  // Check if a VM is already assigned to another role
  const getVMAssignment = (vmId: string): string | null => {
    for (const [role, id] of Object.entries(roleMapping)) {
      if (id === vmId) return role
    }
    return null
  }

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4">
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75" onClick={onClose} />

        <div className="relative bg-white rounded-lg shadow-xl max-w-lg w-full">
          <div className="flex items-center justify-between p-4 border-b">
            <h3 className="text-lg font-medium text-gray-900">
              Configure: {scenario.name}
            </h3>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-500">
              <X className="h-5 w-5" />
            </button>
          </div>

          <div className="p-4">
            <p className="text-sm text-gray-600 mb-4">
              This scenario requires {scenario.required_roles.length} target system
              {scenario.required_roles.length !== 1 ? 's' : ''}.
              Map each role to a VM in your range:
            </p>

            {error && (
              <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-md text-sm">
                {error}
              </div>
            )}

            <div className="space-y-3">
              {scenario.required_roles.map((role) => (
                <div key={role} className="flex items-center justify-between">
                  <label className="text-sm font-medium text-gray-700 w-1/3">
                    {formatRoleName(role)}
                  </label>
                  <div className="relative w-2/3">
                    <select
                      value={roleMapping[role] || ''}
                      onChange={(e) => handleVMSelect(role, e.target.value)}
                      className="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm appearance-none pr-8"
                    >
                      <option value="">Select a VM...</option>
                      {vms.map((vm) => {
                        const assignedTo = getVMAssignment(vm.id)
                        const isAssignedElsewhere = assignedTo && assignedTo !== role
                        return (
                          <option
                            key={vm.id}
                            value={vm.id}
                            disabled={isAssignedElsewhere}
                          >
                            {vm.hostname}
                            {isAssignedElsewhere && ` (→ ${formatRoleName(assignedTo)})`}
                          </option>
                        )
                      })}
                    </select>
                    <ChevronDown className="absolute right-2 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
                  </div>
                </div>
              ))}
            </div>

            {vms.length === 0 && (
              <div className="mt-4 p-3 bg-yellow-50 text-yellow-700 rounded-md text-sm">
                <Server className="inline h-4 w-4 mr-1" />
                No VMs in this range. Add VMs before applying a scenario.
              </div>
            )}
          </div>

          <div className="flex justify-between p-4 border-t bg-gray-50">
            <button
              type="button"
              onClick={onBack}
              className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
            >
              Back
            </button>
            <div className="flex space-x-3">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleApply}
                disabled={!allRolesMapped || submitting}
                className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 disabled:opacity-50"
              >
                {submitting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                Apply Scenario
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
```

**Step 2: Update index.ts**

```typescript
export { default as ScenarioPickerModal } from './ScenarioPickerModal'
export { default as VMMappingModal } from './VMMappingModal'
```

**Step 3: Commit**

```bash
git add frontend/src/components/scenarios/
git commit -m "feat: add VMMappingModal component

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 14: Integrate Scenario Modals in RangeDetail

**Files:**
- Modify: `frontend/src/pages/RangeDetail.tsx`

**Step 1: Import scenario components and API**

Add imports at top of `frontend/src/pages/RangeDetail.tsx`:

```tsx
import { ScenarioPickerModal, VMMappingModal } from '../components/scenarios'
import { rangesApi } from '../services/api'
import type { Scenario } from '../types'
```

**Step 2: Add state for scenario modals**

Add after other state declarations:

```tsx
// Scenario modal state
const [showScenarioPicker, setShowScenarioPicker] = useState(false)
const [selectedScenario, setSelectedScenario] = useState<Scenario | null>(null)
```

**Step 3: Add handler functions**

```tsx
const handleScenarioSelect = (scenario: Scenario) => {
  setShowScenarioPicker(false)
  setSelectedScenario(scenario)
}

const handleApplyScenario = async (roleMapping: Record<string, string>) => {
  if (!selectedScenario || !id) return

  const response = await rangesApi.applyScenario(id, {
    scenario_id: selectedScenario.id,
    role_mapping: roleMapping,
  })

  toast.success(`Scenario applied! ${response.data.inject_count} injects created.`)
  setSelectedScenario(null)
  // Refresh range data
  fetchRangeData()
}
```

**Step 4: Add "Add Scenario" button to header**

Find the header actions section (near Deploy/Start/Stop buttons) and add:

```tsx
{/* Add Scenario Button - show when range has VMs */}
{vms.length > 0 && (
  <button
    onClick={() => setShowScenarioPicker(true)}
    className="inline-flex items-center px-3 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
  >
    <Target className="h-4 w-4 mr-2" />
    Add Scenario
  </button>
)}
```

Add `Target` to the imports from lucide-react.

**Step 5: Add modal components at end of component (before closing div)**

```tsx
{/* Scenario Picker Modal */}
{showScenarioPicker && (
  <ScenarioPickerModal
    onSelect={handleScenarioSelect}
    onClose={() => setShowScenarioPicker(false)}
  />
)}

{/* VM Mapping Modal */}
{selectedScenario && (
  <VMMappingModal
    scenario={selectedScenario}
    vms={vms}
    onApply={handleApplyScenario}
    onBack={() => {
      setSelectedScenario(null)
      setShowScenarioPicker(true)
    }}
    onClose={() => setSelectedScenario(null)}
  />
)}
```

**Step 6: Commit**

```bash
git add frontend/src/pages/RangeDetail.tsx
git commit -m "feat: integrate scenario picker in RangeDetail

- Add Scenario button in header
- ScenarioPickerModal for selection
- VMMappingModal for role mapping

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 15: Rename Guided Builder to Range Wizard

**Files:**
- Modify: `frontend/src/components/wizard/GuidedBuilderWizard.tsx` (rename component)
- Modify: `frontend/src/pages/Ranges.tsx` (update button text and import)

**Step 1: Update component file**

In `frontend/src/components/wizard/GuidedBuilderWizard.tsx`, rename the component:

```tsx
// Change export name
export default function RangeWizard() {
  // ... component code
}
```

**Step 2: Update page title in wizard**

Find the title text in the wizard and change "Guided Builder" to "Range Wizard".

**Step 3: Update Ranges.tsx**

Update button text and import:

```tsx
// Change import if needed
import { GuidedBuilderWizard as RangeWizard } from '../components/wizard/GuidedBuilderWizard'

// Update button text
<button ...>
  <Wand2 className="h-4 w-4 mr-2" />
  Range Wizard
</button>
```

**Step 4: Commit**

```bash
git add frontend/src/components/wizard/GuidedBuilderWizard.tsx frontend/src/pages/Ranges.tsx
git commit -m "refactor: rename Guided Builder to Range Wizard

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 16: Update Version and Changelog

**Files:**
- Modify: `backend/cyroid/config.py`
- Modify: `CHANGELOG.md`

**Step 1: Bump version to 0.8.0**

In `backend/cyroid/config.py`:

```python
app_version: str = "0.8.0"
```

**Step 2: Add changelog entry**

Add to `CHANGELOG.md`:

```markdown
## [0.8.0] - 2026-01-18

### Added

- **Training Scenarios** ([#25](../../issues/25)): Pre-built MSEL packages with one-click deployment.
  - 4 built-in scenarios: Ransomware Attack, APT Intrusion, Insider Threat, Incident Response Drill
  - New Training Scenarios page at `/scenarios` with category filters
  - "Add Scenario" button on Range Detail page
  - VM role mapping modal for targeting scenario events
  - Scenario seeder service with YAML-based definitions
  - API endpoints: GET /scenarios, GET /scenarios/{id}, POST /ranges/{id}/scenario

### Changed

- **Naming Updates**: Improved clarity across the application
  - Templates → VM Templates
  - Blueprints → Range Blueprints
  - Guided Builder → Range Wizard
  - New: Training Scenarios
```

**Step 3: Commit and tag**

```bash
git add backend/cyroid/config.py CHANGELOG.md
git commit -m "chore: bump version to 0.8.0 for Training Scenarios release

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

git tag -a v0.8.0 -m "v0.8.0 - Training Scenarios

Features:
- Training Scenarios with 4 pre-built MSEL packages
- Scenario picker and VM role mapping
- Naming updates: VM Templates, Range Blueprints, Range Wizard

Issue: #25"

git push origin master --tags
```

---

## Summary

This plan implements Training Scenarios in 16 tasks:

1. **Backend Model & Schema** (Tasks 1-2): Scenario SQLAlchemy model and Pydantic schemas
2. **Seeder & Data** (Tasks 3-4): Scenario seeder service and 4 YAML scenario files
3. **Integration** (Task 5): Connect seeder to application startup
4. **API** (Tasks 6-7): Scenarios endpoints and apply endpoint on ranges
5. **Frontend Types & API** (Tasks 8-9): TypeScript types and API client
6. **Training Scenarios Page** (Task 10): New page with card grid
7. **Navigation** (Task 11): Sidebar updates and renamed items
8. **Scenario Picker** (Task 12): Modal for selecting scenarios
9. **VM Mapping** (Task 13): Modal for mapping roles to VMs
10. **Range Integration** (Task 14): Add Scenario button on RangeDetail
11. **Rename Wizard** (Task 15): Guided Builder → Range Wizard
12. **Release** (Task 16): Version bump and changelog

Each task includes exact file paths, complete code, commands to run, and commit messages.
