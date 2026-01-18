# Granular Per-Resource Deployment Status Design

## Overview

Replace the current 4-step stepper deployment UI with a detailed per-resource view showing individual status for every network and VM during deployment.

## Design Goals

1. **Full visibility**: See every resource's status individually
2. **Real-time updates**: Poll for status changes during deployment
3. **Leverage existing infrastructure**: Use EventLog system, don't add new tables
4. **Simple v1**: Skip expandable timelines and retry/skip buttons for now

## Data Model

### EventLog Enhancement

Add `network_id` field to EventLog for network-specific events:

```python
# In event_log.py
network_id: Mapped[Optional[UUID]] = mapped_column(
    ForeignKey("networks.id", ondelete="SET NULL"),
    nullable=True,
    index=True
)
```

### New API Response Structure

```python
GET /api/v1/ranges/{id}/deployment-status

{
  "status": "deploying",
  "elapsed_seconds": 45,
  "summary": {
    "total": 8,
    "completed": 5,
    "in_progress": 2,
    "failed": 1
  },
  "router": {
    "status": "running",
    "duration_ms": 2100
  },
  "networks": [
    {
      "id": "uuid",
      "name": "internal",
      "subnet": "10.100.0.0/24",
      "status": "created",
      "duration_ms": 300
    }
  ],
  "vms": [
    {
      "id": "uuid",
      "hostname": "dc01",
      "ip": "10.100.0.10",
      "status": "starting",
      "status_detail": "Waiting for services..."
    }
  ]
}
```

---

## UI Components

### Component Hierarchy

```
DeploymentProgress (refactored)
├── Header (title, elapsed time, overall progress bar)
├── SummaryRow (total/completed/in-progress/failed counts)
├── ResourceSection "Router"
│   └── ResourceRow (single row for VyOS router)
├── ResourceSection "Networks"
│   └── ResourceRow × N (one per network)
├── ResourceSection "VMs"
│   └── ResourceRow × N (one per VM)
└── ExpandableLog (existing, keep as-is)
```

### ResourceRow Component

Each row displays:
- Status icon (○ pending, ⟳ in-progress, ✓ completed, ✗ failed)
- Resource name (hostname or network name)
- IP/subnet info
- Status text ("Creating...", "Running", "Failed: port conflict")
- Duration when completed

### Status Icons & Colors

| Status | Icon | Color |
|--------|------|-------|
| pending | ○ | Gray |
| creating/starting | ⟳ | Blue (animated) |
| running/created | ✓ | Green |
| failed | ✗ | Red |

### Visual Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  Deploying: Red Team Training Lab                              │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  5/8 resources        │
│  Elapsed: 00:45                                                 │
├─────────────────────────────────────────────────────────────────┤
│  ROUTER (1/1)                                                   │
│  ✓ gateway         VyOS 1.4              Running      2.1s     │
├─────────────────────────────────────────────────────────────────┤
│  NETWORKS (3/3)                                                 │
│  ✓ internet        172.16.0.0/24         Created      0.3s     │
│  ✓ dmz             172.16.1.0/24         Created      0.2s     │
│  ✓ internal        172.16.2.0/24         Created      0.2s     │
├─────────────────────────────────────────────────────────────────┤
│  VMs (1/4)                                                      │
│  ✓ kali            172.16.0.10           Running      45.2s    │
│  ⟳ dc01            172.16.2.10           Starting...   --      │
│  ○ fileserver      172.16.2.20           Pending       --      │
│  ○ ws01            172.16.2.30           Pending       --      │
├─────────────────────────────────────────────────────────────────┤
│  ▶ Deployment Log (12 events)                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Backend Implementation

### 1. Migration: Add network_id to event_logs

```python
# alembic revision
def upgrade():
    op.add_column('event_logs',
        sa.Column('network_id', UUID(), nullable=True))
    op.create_index('ix_event_logs_network_id', 'event_logs', ['network_id'])
    op.create_foreign_key(
        'fk_event_logs_network_id', 'event_logs', 'networks',
        ['network_id'], ['id'], ondelete='SET NULL')
```

### 2. New Endpoint: deployment-status

```python
@router.get("/{range_id}/deployment-status")
def get_deployment_status(range_id: UUID, db: Session):
    range_obj = db.query(Range).options(
        joinedload(Range.networks),
        joinedload(Range.vms)
    ).filter(Range.id == range_id).first()

    if not range_obj:
        raise HTTPException(404)

    # Get recent deployment events
    events = db.query(EventLog).filter(
        EventLog.range_id == range_id,
        EventLog.created_at > datetime.utcnow() - timedelta(hours=1)
    ).order_by(EventLog.created_at).all()

    return compute_resource_status(range_obj, events)
```

### 3. Status Computation Logic

```python
def compute_resource_status(range_obj, events):
    # Initialize all resources as pending
    router_status = {"status": "pending"}
    network_statuses = {n.id: {"id": str(n.id), "name": n.name, "subnet": n.subnet, "status": "pending"}
                        for n in range_obj.networks}
    vm_statuses = {v.id: {"id": str(v.id), "hostname": v.hostname, "ip": v.ip_address, "status": "pending"}
                   for v in range_obj.vms}

    # Process events chronologically to build current state
    for event in events:
        if event.event_type == EventType.ROUTER_CREATING:
            router_status = {"status": "creating"}
        elif event.event_type == EventType.ROUTER_CREATED:
            router_status = {"status": "running", "duration_ms": ...}
        elif event.event_type == EventType.NETWORK_CREATING:
            if event.network_id:
                network_statuses[event.network_id]["status"] = "creating"
        # ... etc for all event types

    # Compute summary
    all_resources = [router_status] + list(network_statuses.values()) + list(vm_statuses.values())
    summary = {
        "total": len(all_resources),
        "completed": sum(1 for r in all_resources if r["status"] in ["running", "created"]),
        "in_progress": sum(1 for r in all_resources if r["status"] in ["creating", "starting"]),
        "failed": sum(1 for r in all_resources if r["status"] == "failed")
    }

    return {
        "status": range_obj.status,
        "elapsed_seconds": ...,
        "summary": summary,
        "router": router_status,
        "networks": list(network_statuses.values()),
        "vms": list(vm_statuses.values())
    }
```

### 4. Update Event Logging

When logging network events, include network_id:

```python
event_service.log_event(
    range_id=range_id,
    network_id=network.id,  # NEW
    event_type=EventType.NETWORK_CREATING,
    message=f"Creating network '{network.name}'"
)
```

---

## Frontend Implementation

### New Types

```typescript
// types/index.ts
interface ResourceStatus {
  id: string
  name: string
  status: 'pending' | 'creating' | 'starting' | 'running' | 'created' | 'stopped' | 'failed'
  statusDetail?: string
  durationMs?: number
}

interface NetworkStatus extends ResourceStatus {
  subnet: string
}

interface VMStatus extends ResourceStatus {
  ip: string
  hostname: string
}

interface DeploymentStatusResponse {
  status: string
  elapsedSeconds: number
  summary: { total: number; completed: number; inProgress: number; failed: number }
  router: ResourceStatus | null
  networks: NetworkStatus[]
  vms: VMStatus[]
}
```

### New API Call

```typescript
// services/api.ts
getDeploymentStatus: (rangeId: string) =>
  api.get<DeploymentStatusResponse>(`/ranges/${rangeId}/deployment-status`)
```

### ResourceRow Component

```typescript
// components/range/ResourceRow.tsx
interface Props {
  name: string
  detail: string  // IP or subnet
  status: string
  statusDetail?: string
  durationMs?: number
}

function ResourceRow({ name, detail, status, statusDetail, durationMs }: Props) {
  return (
    <div className="flex items-center py-2 px-4 border-b border-gray-100">
      <StatusIcon status={status} />
      <span className="w-32 font-medium">{name}</span>
      <span className="w-40 text-gray-500 text-sm">{detail}</span>
      <span className="flex-1 text-sm">{statusDetail || status}</span>
      <span className="w-16 text-right text-gray-400 text-sm">
        {durationMs ? `${(durationMs / 1000).toFixed(1)}s` : '--'}
      </span>
    </div>
  )
}
```

---

## Error Handling

- Failed resources show red ✗ icon with error message inline
- No retry/skip buttons in v1
- User can view full logs via expandable log section

## Polling Strategy

- Poll every 1 second during deployment
- Stop polling when status is `deployed` or `failed`

---

## Scope

### v1 (This Implementation)

- Add `network_id` to EventLog
- New `/deployment-status` endpoint
- Refactored DeploymentProgress with per-resource rows
- ResourceRow component with status icons
- Summary counts

### Future Enhancements

- Expandable resource details with timeline
- Dependency visualization
- Retry/skip individual resources
- Stop operation granular tracking
- WebSocket push instead of polling

---

## Files to Modify

### Backend
- `backend/cyroid/models/event_log.py` - add network_id field
- `backend/cyroid/schemas/event_log.py` - add network_id to schema
- `backend/cyroid/services/event_service.py` - accept network_id parameter
- `backend/cyroid/api/ranges.py` - add deployment-status endpoint, update event logging
- `backend/alembic/versions/xxx_add_network_id_to_event_logs.py` - migration

### Frontend
- `frontend/src/types/index.ts` - add new types
- `frontend/src/services/api.ts` - add API call
- `frontend/src/components/range/DeploymentProgress.tsx` - refactor
- `frontend/src/components/range/ResourceRow.tsx` - new component
- `frontend/src/components/range/ResourceSection.tsx` - new component
- `frontend/src/components/range/StatusIcon.tsx` - new component

---

## Related Issues

- #24 - Granular per-resource deployment status (this design)
- #6 - Verbose deployment status (completed, this extends it)
- #10 - Real-time reactive feedback (related)
