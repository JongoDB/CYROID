# Range Blueprints Design

## Overview

Range Blueprints enable multiple instructors to deploy isolated instances of the same training environment simultaneously. A blueprint is a reusable configuration that spawns independent range instances with auto-allocated subnets.

## Design Goals

1. **Multi-instructor support**: Same blueprint, different instructors, simultaneous classes
2. **No subnet conflicts**: Automatic offset-based IP allocation
3. **Simple workflow**: Promote existing range to blueprint, one-click deploy
4. **Clear separation**: Blueprints (full environments) vs VM Templates (OS images)

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Subnet allocation | Offset-based (2nd octet) | Simple, predictable, debuggable |
| Template-instance link | Snapshot at deploy | Safe - template updates don't break running classes |
| Template creation | Promote existing range | Reuses existing builder, no new UI needed |
| Visibility | Public by default + ABAC tags | Flexible sharing with existing permission system |
| Instance controls | Full (reset, redeploy, clone) | Maximum instructor flexibility |
| UI placement | Separate "Blueprints" nav | Clear distinction from VM Templates |
| Naming | "Blueprints" | Avoids confusion with VM Templates |

---

## Data Model

### RangeBlueprint

```python
class RangeBlueprint(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "range_blueprints"

    name: Mapped[str] = mapped_column(String(100), index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    version: Mapped[int] = mapped_column(default=1)
    config: Mapped[dict] = mapped_column(JSON)  # networks, VMs, MSEL, router
    base_subnet_prefix: Mapped[str] = mapped_column(String(20))  # e.g., "10.100"
    next_offset: Mapped[int] = mapped_column(default=0)

    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_by_user = relationship("User")

    instances: Mapped[List["RangeInstance"]] = relationship(
        "RangeInstance", back_populates="blueprint", cascade="all, delete-orphan"
    )
    resource_tags: Mapped[List["ResourceTag"]] = relationship(...)  # ABAC visibility
```

### RangeInstance

```python
class RangeInstance(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "range_instances"

    name: Mapped[str] = mapped_column(String(100))  # "Texas Morning Class"
    blueprint_id: Mapped[UUID] = mapped_column(ForeignKey("range_blueprints.id"))
    blueprint_version: Mapped[int]  # Version at deploy time
    subnet_offset: Mapped[int]  # 0, 1, 2, ... auto-assigned

    instructor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    range_id: Mapped[UUID] = mapped_column(ForeignKey("ranges.id"))

    blueprint = relationship("RangeBlueprint", back_populates="instances")
    instructor = relationship("User")
    range = relationship("Range")
```

### Config JSON Structure

```json
{
  "networks": [
    {"name": "internal", "subnet": "10.100.0.0/24", "gateway": "10.100.0.1", "isolated": true}
  ],
  "vms": [
    {"name": "dc01", "ip": "10.100.0.10", "template_name": "Windows Server 2022", "network": "internal"}
  ],
  "router": {
    "enabled": true,
    "dhcp_enabled": false
  },
  "msel": {
    "content": "...",
    "format": "yaml"
  }
}
```

---

## Subnet Offset Mechanism

Blueprint defines base networks with a prefix (e.g., `10.100`):

```
Internal: 10.100.0.0/24
DMZ:      10.100.1.0/24
External: 10.100.2.0/24
```

When deploying instances, the second octet is offset:

| Instance | Offset | Internal | DMZ | External |
|----------|--------|----------|-----|----------|
| Texas | +0 | 10.100.0.0/24 | 10.100.1.0/24 | 10.100.2.0/24 |
| California | +1 | 10.101.0.0/24 | 10.101.1.0/24 | 10.101.2.0/24 |
| NYC | +2 | 10.102.0.0/24 | 10.102.1.0/24 | 10.102.2.0/24 |

**VM IPs follow the same pattern:**
- Blueprint: DC at `10.100.0.10` → Instance 2: `10.101.0.10`

**Offset allocation rules:**
- System tracks `next_offset` on blueprint
- New instance gets current `next_offset`, then increments
- Deleted instance offsets are NOT reused (avoids confusion)
- Max 155 instances per blueprint (10.100 → 10.255)

---

## API Endpoints

### Blueprints

```
POST   /api/v1/blueprints
       Body: { range_id, name, description, base_subnet_prefix }
       Creates blueprint from existing range

GET    /api/v1/blueprints
       List all blueprints (respects visibility tags)

GET    /api/v1/blueprints/{id}
       Get blueprint details including config

PUT    /api/v1/blueprints/{id}
       Update blueprint (increments version)
       Body: { name?, description?, config? }

DELETE /api/v1/blueprints/{id}
       Delete blueprint (fails if instances exist)
```

### Instances

```
POST   /api/v1/blueprints/{id}/deploy
       Body: { name, auto_deploy: bool }
       Deploy new instance, returns instance + range

GET    /api/v1/blueprints/{id}/instances
       List all instances of this blueprint

POST   /api/v1/instances/{id}/reset
       Reset instance to initial state (same version)

POST   /api/v1/instances/{id}/redeploy
       Delete and recreate from latest blueprint version

POST   /api/v1/instances/{id}/clone
       Create new instance with same config

DELETE /api/v1/instances/{id}
       Delete instance and its range
```

---

## Workflows

### Creating a Blueprint

1. User builds a range (manual or Guided Builder)
2. On RangeDetail page, clicks "Save as Blueprint"
3. Modal prompts:
   - Blueprint name (required)
   - Description (optional)
   - Base subnet prefix (default: extracted from range)
   - Visibility tags (optional)
4. System extracts range config → saves as Blueprint v1
5. Original range unchanged

### Deploying an Instance

1. User navigates to Blueprints page
2. Clicks "Deploy Instance" on a blueprint card
3. Modal prompts:
   - Instance name (required)
   - Auto-deploy checkbox (default: checked)
   - Shows: "Will use subnet 10.103.x.x"
4. System:
   - Assigns next offset
   - Creates Range with offset-adjusted IPs
   - Creates RangeInstance record
   - Optionally starts deployment

### Instance Actions

| Action | Behavior |
|--------|----------|
| **Open** | Navigate to Range detail page |
| **Start/Stop** | Standard range controls |
| **Reset** | Stop VMs, restore to initial state (same version) |
| **Redeploy** | Delete range, create fresh from latest blueprint |
| **Clone** | Create new instance with next offset |
| **Delete** | Delete range and instance record |

---

## UI Components

### Navigation

- Add "Blueprints" to sidebar between "Ranges" and "Templates"
- Icon: `LayoutTemplate` from Lucide

### Blueprints Page (`/blueprints`)

Card grid showing all blueprints:
- Name, description
- VM count, network count
- Active instance count
- Actions: Deploy, Edit, Delete

### Blueprint Detail Page (`/blueprints/{id}`)

- Header: name, version, created by
- Tabs: Overview | Instances
- Overview: read-only network/VM topology
- Instances: table with status, instructor, actions

### Save as Blueprint Modal

On RangeDetail page:
```
┌─────────────────────────────────────────────┐
│ Save as Blueprint                           │
├─────────────────────────────────────────────┤
│ Name:        [Red Team Training Lab      ]  │
│ Description: [Full attack chain scenario ]  │
│ Base Subnet: [10.100                     ]  │
│ Visibility:  [Public ▾] or [Add Tags]       │
│                                             │
│              [Cancel]  [Save Blueprint]     │
└─────────────────────────────────────────────┘
```

### Deploy Instance Modal

```
┌─────────────────────────────────────────────┐
│ Deploy Instance                             │
│ Blueprint: Red Team Training Lab v2         │
├─────────────────────────────────────────────┤
│ Instance Name: [Texas Morning Class      ]  │
│                                             │
│ ☑ Auto-deploy after creation                │
│                                             │
│ Subnet: 10.103.x.x (auto-assigned)          │
│                                             │
│              [Cancel]  [Deploy Instance]    │
└─────────────────────────────────────────────┘
```

### Instance Info Banner

On RangeDetail for blueprint instances:
```
ℹ️ This range is an instance of "Red Team Training Lab" (v2)
   [View Blueprint] [Redeploy from Latest (v3)]
```

### Reset vs Redeploy Clarity

**Reset Instance:**
- Button: Yellow/warning style
- Tooltip: "Stop all VMs and restore to initial state. Uses the same blueprint version (v2) from when this instance was deployed."
- Confirmation: "This will reset all VMs to their initial state. Student progress will be lost."

**Redeploy from Latest:**
- Button: Red/danger style
- Tooltip: "Delete this instance and create a fresh one from the latest blueprint version (v3)."
- Confirmation: "This will delete the current instance and deploy fresh from blueprint v3. All data will be lost."
- Only shown when instance version < blueprint version

---

## Scope

### v1 (This Implementation)

- Blueprint CRUD
- Instance deploy, reset, redeploy, clone, delete
- Offset-based subnet allocation
- Blueprints page with card grid
- Blueprint detail with instances tab
- "Save as Blueprint" on RangeDetail
- Instance info banner on RangeDetail
- Visibility tags integration

### Future Enhancements

- Blueprint versioning UI (view/restore old versions)
- Instance scheduling (auto-start before class, auto-stop after)
- Student assignment to instances
- Blueprint marketplace/sharing across organizations
- Bulk instance operations

---

## File Structure

```
backend/cyroid/
├── models/
│   ├── blueprint.py          # RangeBlueprint, RangeInstance models
├── schemas/
│   ├── blueprint.py          # Pydantic schemas
├── api/
│   ├── blueprints.py         # Blueprint endpoints
│   ├── instances.py          # Instance endpoints
├── services/
│   ├── blueprint_service.py  # Config extraction, offset calculation

frontend/src/
├── pages/
│   ├── Blueprints.tsx        # Blueprint list page
│   ├── BlueprintDetail.tsx   # Blueprint detail with instances
├── components/
│   ├── blueprints/
│   │   ├── BlueprintCard.tsx
│   │   ├── SaveBlueprintModal.tsx
│   │   ├── DeployInstanceModal.tsx
│   │   ├── InstancesTable.tsx
│   │   ├── InstanceInfoBanner.tsx
```

---

## Related Issues

- #19 - Guided Range Builder (completed - can save as blueprint)
- #18 - Range Templates (this issue - renamed to Blueprints)
