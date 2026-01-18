# Granular Deployment Status Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the 4-step stepper deployment UI with a per-resource view showing individual status for every network and VM.

**Architecture:** Add `network_id` to EventLog for network-specific events. Create new `/deployment-status` endpoint that aggregates events into per-resource status. Refactor frontend DeploymentProgress component to display individual resource rows.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, React, TypeScript, Tailwind CSS

---

## Task 1: Add network_id field to EventLog model

**Files:**
- Modify: `backend/cyroid/models/event_log.py:43-53`

**Step 1: Add the network_id field to EventLog model**

Add after line 47 (after vm_id field):

```python
network_id: Mapped[Optional[UUID]] = mapped_column(
    ForeignKey("networks.id", ondelete="SET NULL"), nullable=True, index=True
)
```

Also add the relationship after the vm relationship:

```python
network = relationship("Network", back_populates="event_logs")
```

**Step 2: Add back-reference in Network model**

In `backend/cyroid/models/network.py`, add:

```python
event_logs: Mapped[List["EventLog"]] = relationship("EventLog", back_populates="network")
```

**Step 3: Verify syntax by importing the model**

Run: `cd /Users/JonWFH/jondev/CYROID && docker-compose exec api python -c "from cyroid.models.event_log import EventLog; print('OK')"`

Expected: `OK`

**Step 4: Commit**

```bash
git add backend/cyroid/models/event_log.py backend/cyroid/models/network.py
git commit -m "feat(events): add network_id field to EventLog model"
```

---

## Task 2: Create Alembic migration for network_id

**Files:**
- Create: `backend/alembic/versions/xxxx_add_network_id_to_event_logs.py`

**Step 1: Generate the migration**

Run:
```bash
docker-compose exec api alembic revision --autogenerate -m "add_network_id_to_event_logs"
```

Expected: Creates a new migration file

**Step 2: Verify the migration content looks correct**

The migration should contain:
- `op.add_column('event_logs', sa.Column('network_id', ...))`
- `op.create_index('ix_event_logs_network_id', ...)`
- `op.create_foreign_key(...)`

**Step 3: Apply the migration**

Run: `docker-compose exec api alembic upgrade head`

Expected: Migration applies successfully

**Step 4: Commit**

```bash
git add backend/alembic/versions/
git commit -m "feat(events): add migration for network_id column"
```

---

## Task 3: Update EventService to accept network_id

**Files:**
- Modify: `backend/cyroid/services/event_service.py:18-56`

**Step 1: Add network_id parameter to log_event method**

Update the method signature (around line 18-26):

```python
def log_event(
    self,
    range_id: UUID,
    event_type: EventType,
    message: str,
    vm_id: Optional[UUID] = None,
    network_id: Optional[UUID] = None,  # NEW
    extra_data: Optional[str] = None,
    broadcast: bool = True
) -> EventLog:
```

**Step 2: Include network_id when creating EventLog**

Update the EventLog creation (around line 41-47):

```python
event = EventLog(
    range_id=range_id,
    vm_id=vm_id,
    network_id=network_id,  # NEW
    event_type=event_type,
    message=message,
    extra_data=extra_data
)
```

**Step 3: Include network_id in broadcast**

Update the broadcast call (around line 80-95) to include network_id:

```python
loop.create_task(broadcast_event(
    event_type=event.event_type.value,
    message=event.message,
    range_id=event.range_id,
    vm_id=event.vm_id,
    network_id=event.network_id,  # NEW
    data=data
))
```

And the sync version similarly.

**Step 4: Verify syntax**

Run: `docker-compose exec api python -c "from cyroid.services.event_service import EventService; print('OK')"`

Expected: `OK`

**Step 5: Commit**

```bash
git add backend/cyroid/services/event_service.py
git commit -m "feat(events): add network_id parameter to EventService.log_event"
```

---

## Task 4: Update EventLog schema for network_id

**Files:**
- Modify: `backend/cyroid/schemas/event_log.py`

**Step 1: Add network_id to EventLogCreate**

```python
class EventLogCreate(EventLogBase):
    range_id: UUID
    vm_id: Optional[UUID] = None
    network_id: Optional[UUID] = None  # NEW
```

**Step 2: Add network_id to EventLogResponse**

```python
class EventLogResponse(EventLogBase):
    id: UUID
    range_id: UUID
    vm_id: Optional[UUID]
    network_id: Optional[UUID]  # NEW
    created_at: datetime

    class Config:
        from_attributes = True
```

**Step 3: Verify syntax**

Run: `docker-compose exec api python -c "from cyroid.schemas.event_log import EventLogResponse; print('OK')"`

Expected: `OK`

**Step 4: Commit**

```bash
git add backend/cyroid/schemas/event_log.py
git commit -m "feat(events): add network_id to event log schemas"
```

---

## Task 5: Create deployment status schemas

**Files:**
- Create: `backend/cyroid/schemas/deployment_status.py`

**Step 1: Create the new schema file**

```python
# backend/cyroid/schemas/deployment_status.py
from typing import Optional, List
from pydantic import BaseModel


class ResourceStatus(BaseModel):
    id: Optional[str] = None
    name: str
    status: str  # pending, creating, starting, running, created, stopped, failed
    status_detail: Optional[str] = None
    duration_ms: Optional[int] = None


class NetworkStatus(ResourceStatus):
    subnet: str


class VMStatus(ResourceStatus):
    hostname: str
    ip: Optional[str] = None


class DeploymentSummary(BaseModel):
    total: int
    completed: int
    in_progress: int
    failed: int
    pending: int


class DeploymentStatusResponse(BaseModel):
    status: str
    elapsed_seconds: int
    started_at: Optional[str] = None
    summary: DeploymentSummary
    router: Optional[ResourceStatus] = None
    networks: List[NetworkStatus]
    vms: List[VMStatus]
```

**Step 2: Verify syntax**

Run: `docker-compose exec api python -c "from cyroid.schemas.deployment_status import DeploymentStatusResponse; print('OK')"`

Expected: `OK`

**Step 3: Commit**

```bash
git add backend/cyroid/schemas/deployment_status.py
git commit -m "feat(deployment): add deployment status schemas"
```

---

## Task 6: Add deployment-status endpoint

**Files:**
- Modify: `backend/cyroid/api/ranges.py`

**Step 1: Add imports at the top of the file**

```python
from cyroid.schemas.deployment_status import (
    DeploymentStatusResponse, DeploymentSummary, ResourceStatus, NetworkStatus, VMStatus
)
```

**Step 2: Create the status computation helper function**

Add before the router endpoints:

```python
def compute_deployment_status(range_obj, events: list) -> DeploymentStatusResponse:
    """Compute per-resource deployment status from events."""
    from datetime import timezone

    # Find deployment start time
    started_at = None
    for event in events:
        if event.event_type == EventType.DEPLOYMENT_STARTED:
            started_at = event.created_at
            break

    # Track timestamps for duration calculation
    resource_start_times = {}

    # Initialize router status
    router_status = ResourceStatus(name="gateway", status="pending")

    # Initialize network statuses
    network_statuses = {}
    for n in range_obj.networks:
        network_statuses[n.id] = NetworkStatus(
            id=str(n.id), name=n.name, subnet=n.subnet, status="pending"
        )

    # Initialize VM statuses
    vm_statuses = {}
    for v in range_obj.vms:
        vm_statuses[v.id] = VMStatus(
            id=str(v.id), name=v.hostname, hostname=v.hostname,
            ip=v.ip_address, status="pending"
        )

    # Process events chronologically
    for event in events:
        event_type = event.event_type

        # Router events
        if event_type == EventType.ROUTER_CREATING:
            router_status.status = "creating"
            router_status.status_detail = "Creating VyOS router..."
            resource_start_times["router"] = event.created_at
        elif event_type == EventType.ROUTER_CREATED:
            router_status.status = "running"
            router_status.status_detail = "Running"
            if "router" in resource_start_times:
                delta = event.created_at - resource_start_times["router"]
                router_status.duration_ms = int(delta.total_seconds() * 1000)

        # Network events
        elif event_type == EventType.NETWORK_CREATING:
            if event.network_id and event.network_id in network_statuses:
                network_statuses[event.network_id].status = "creating"
                network_statuses[event.network_id].status_detail = "Creating Docker network..."
                resource_start_times[f"network_{event.network_id}"] = event.created_at
        elif event_type == EventType.NETWORK_CREATED:
            if event.network_id and event.network_id in network_statuses:
                network_statuses[event.network_id].status = "created"
                network_statuses[event.network_id].status_detail = "Created"
                key = f"network_{event.network_id}"
                if key in resource_start_times:
                    delta = event.created_at - resource_start_times[key]
                    network_statuses[event.network_id].duration_ms = int(delta.total_seconds() * 1000)

        # VM events
        elif event_type == EventType.VM_CREATING:
            if event.vm_id and event.vm_id in vm_statuses:
                vm_statuses[event.vm_id].status = "creating"
                vm_statuses[event.vm_id].status_detail = "Creating container..."
                resource_start_times[f"vm_{event.vm_id}"] = event.created_at
        elif event_type == EventType.VM_STARTED:
            if event.vm_id and event.vm_id in vm_statuses:
                vm_statuses[event.vm_id].status = "running"
                vm_statuses[event.vm_id].status_detail = "Running"
                key = f"vm_{event.vm_id}"
                if key in resource_start_times:
                    delta = event.created_at - resource_start_times[key]
                    vm_statuses[event.vm_id].duration_ms = int(delta.total_seconds() * 1000)
        elif event_type == EventType.VM_ERROR:
            if event.vm_id and event.vm_id in vm_statuses:
                vm_statuses[event.vm_id].status = "failed"
                vm_statuses[event.vm_id].status_detail = event.message

        # Deployment failure
        elif event_type == EventType.DEPLOYMENT_FAILED:
            # Mark any in-progress resources as failed
            if router_status.status == "creating":
                router_status.status = "failed"
                router_status.status_detail = event.message

    # Build summary
    all_resources = [router_status] + list(network_statuses.values()) + list(vm_statuses.values())
    summary = DeploymentSummary(
        total=len(all_resources),
        completed=sum(1 for r in all_resources if r.status in ["running", "created"]),
        in_progress=sum(1 for r in all_resources if r.status in ["creating", "starting"]),
        failed=sum(1 for r in all_resources if r.status == "failed"),
        pending=sum(1 for r in all_resources if r.status == "pending")
    )

    # Calculate elapsed time
    elapsed_seconds = 0
    if started_at:
        from datetime import datetime
        now = datetime.now(timezone.utc) if started_at.tzinfo else datetime.utcnow()
        elapsed_seconds = int((now - started_at).total_seconds())

    return DeploymentStatusResponse(
        status=range_obj.status.value if hasattr(range_obj.status, 'value') else range_obj.status,
        elapsed_seconds=elapsed_seconds,
        started_at=started_at.isoformat() if started_at else None,
        summary=summary,
        router=router_status,
        networks=list(network_statuses.values()),
        vms=list(vm_statuses.values())
    )
```

**Step 3: Add the endpoint**

Add after the existing endpoints (before `async def deploy_range`):

```python
@router.get("/{range_id}/deployment-status", response_model=DeploymentStatusResponse)
async def get_deployment_status(
    range_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user)
):
    """Get detailed per-resource deployment status."""
    from datetime import datetime, timedelta
    from sqlalchemy.orm import joinedload

    range_obj = db.query(Range).options(
        joinedload(Range.networks),
        joinedload(Range.vms)
    ).filter(Range.id == range_id).first()

    if not range_obj:
        raise HTTPException(status_code=404, detail="Range not found")

    # Get deployment events from last hour
    events = db.query(EventLog).filter(
        EventLog.range_id == range_id,
        EventLog.created_at > datetime.utcnow() - timedelta(hours=1)
    ).order_by(EventLog.created_at).all()

    return compute_deployment_status(range_obj, events)
```

**Step 4: Verify the endpoint works**

Run: `docker-compose restart api && sleep 3 && curl -s http://localhost:8000/api/v1/ranges/ | head -c 100`

Expected: Returns JSON (doesn't crash)

**Step 5: Commit**

```bash
git add backend/cyroid/api/ranges.py
git commit -m "feat(deployment): add deployment-status endpoint"
```

---

## Task 7: Update network event logging with network_id

**Files:**
- Modify: `backend/cyroid/api/ranges.py` (deploy_range function)

**Step 1: Find the NETWORK_CREATING event log call and add network_id**

Around line 251-256, update:

```python
event_service.log_event(
    range_id=range_id,
    network_id=network.id,  # ADD THIS
    event_type=EventType.NETWORK_CREATING,
    message=f"Creating network '{network.name}' ({idx + 1}/{len(networks)})",
    extra_data=json.dumps({"subnet": network.subnet, "gateway": network.gateway})
)
```

**Step 2: Find the NETWORK_CREATED event log call and add network_id**

Around line 270-275, update:

```python
event_service.log_event(
    range_id=range_id,
    network_id=network.id,  # ADD THIS
    event_type=EventType.NETWORK_CREATED,
    message=f"Network '{network.name}' created ({idx + 1}/{len(networks)})"
)
```

**Step 3: Verify the code compiles**

Run: `docker-compose exec api python -c "from cyroid.api.ranges import router; print('OK')"`

Expected: `OK`

**Step 4: Commit**

```bash
git add backend/cyroid/api/ranges.py
git commit -m "feat(events): include network_id in network event logging"
```

---

## Task 8: Add frontend types for deployment status

**Files:**
- Modify: `frontend/src/types/index.ts`

**Step 1: Add the new types after EventLogList (around line 191)**

```typescript
// Deployment Status Types
export interface ResourceStatus {
  id?: string
  name: string
  status: 'pending' | 'creating' | 'starting' | 'running' | 'created' | 'stopped' | 'failed'
  statusDetail?: string
  durationMs?: number
}

export interface NetworkStatus extends ResourceStatus {
  subnet: string
}

export interface VMStatus extends ResourceStatus {
  hostname: string
  ip?: string
}

export interface DeploymentSummary {
  total: number
  completed: number
  inProgress: number
  failed: number
  pending: number
}

export interface DeploymentStatusResponse {
  status: string
  elapsedSeconds: number
  startedAt?: string
  summary: DeploymentSummary
  router?: ResourceStatus
  networks: NetworkStatus[]
  vms: VMStatus[]
}
```

**Step 2: Also add network_id to EventLog interface**

Update the EventLog interface (around line 178-186):

```typescript
export interface EventLog {
  id: string
  range_id: string
  vm_id: string | null
  network_id: string | null  // ADD THIS
  event_type: EventType
  message: string
  extra_data: string | null
  created_at: string
}
```

**Step 3: Verify TypeScript compiles**

Run: `cd /Users/JonWFH/jondev/CYROID/frontend && npm run build 2>&1 | head -20`

Expected: No type errors related to these changes

**Step 4: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat(types): add deployment status types"
```

---

## Task 9: Add deployment status API call

**Files:**
- Modify: `frontend/src/services/api.ts`

**Step 1: Add the import for DeploymentStatusResponse**

Update the imports from types (find the line with type imports):

```typescript
import { ..., DeploymentStatusResponse } from '../types'
```

**Step 2: Add the API method to rangesApi object**

Find `rangesApi` object and add:

```typescript
getDeploymentStatus: (rangeId: string) =>
  api.get<DeploymentStatusResponse>(`/ranges/${rangeId}/deployment-status`),
```

**Step 3: Verify TypeScript compiles**

Run: `cd /Users/JonWFH/jondev/CYROID/frontend && npm run build 2>&1 | head -20`

Expected: No errors

**Step 4: Commit**

```bash
git add frontend/src/services/api.ts
git commit -m "feat(api): add getDeploymentStatus API call"
```

---

## Task 10: Create StatusIcon component

**Files:**
- Create: `frontend/src/components/range/StatusIcon.tsx`

**Step 1: Create the component**

```typescript
// frontend/src/components/range/StatusIcon.tsx
import { CheckCircle, XCircle, Loader2, Circle } from 'lucide-react'
import clsx from 'clsx'

interface Props {
  status: string
  className?: string
}

export function StatusIcon({ status, className }: Props) {
  const baseClass = clsx('w-5 h-5', className)

  switch (status) {
    case 'running':
    case 'created':
      return <CheckCircle className={clsx(baseClass, 'text-green-500')} />
    case 'creating':
    case 'starting':
      return <Loader2 className={clsx(baseClass, 'text-blue-500 animate-spin')} />
    case 'failed':
      return <XCircle className={clsx(baseClass, 'text-red-500')} />
    case 'pending':
    default:
      return <Circle className={clsx(baseClass, 'text-gray-400')} />
  }
}
```

**Step 2: Verify TypeScript compiles**

Run: `cd /Users/JonWFH/jondev/CYROID/frontend && npm run build 2>&1 | head -20`

Expected: No errors

**Step 3: Commit**

```bash
git add frontend/src/components/range/StatusIcon.tsx
git commit -m "feat(ui): add StatusIcon component"
```

---

## Task 11: Create ResourceRow component

**Files:**
- Create: `frontend/src/components/range/ResourceRow.tsx`

**Step 1: Create the component**

```typescript
// frontend/src/components/range/ResourceRow.tsx
import { StatusIcon } from './StatusIcon'
import clsx from 'clsx'

interface Props {
  name: string
  detail?: string
  status: string
  statusDetail?: string
  durationMs?: number
}

export function ResourceRow({ name, detail, status, statusDetail, durationMs }: Props) {
  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}ms`
    return `${(ms / 1000).toFixed(1)}s`
  }

  const getStatusText = () => {
    if (statusDetail) return statusDetail
    switch (status) {
      case 'pending': return 'Pending'
      case 'creating': return 'Creating...'
      case 'starting': return 'Starting...'
      case 'running': return 'Running'
      case 'created': return 'Created'
      case 'failed': return 'Failed'
      default: return status
    }
  }

  return (
    <div className={clsx(
      'flex items-center py-2 px-4 border-b border-gray-700 last:border-b-0',
      status === 'failed' && 'bg-red-900/20'
    )}>
      <StatusIcon status={status} className="mr-3 flex-shrink-0" />
      <span className="w-32 font-medium text-white truncate">{name}</span>
      <span className="w-36 text-gray-400 text-sm truncate">{detail || '--'}</span>
      <span className={clsx(
        'flex-1 text-sm truncate',
        status === 'failed' ? 'text-red-400' :
        status === 'running' || status === 'created' ? 'text-green-400' :
        status === 'creating' || status === 'starting' ? 'text-blue-400' :
        'text-gray-400'
      )}>
        {getStatusText()}
      </span>
      <span className="w-16 text-right text-gray-500 text-sm">
        {durationMs ? formatDuration(durationMs) : '--'}
      </span>
    </div>
  )
}
```

**Step 2: Verify TypeScript compiles**

Run: `cd /Users/JonWFH/jondev/CYROID/frontend && npm run build 2>&1 | head -20`

Expected: No errors

**Step 3: Commit**

```bash
git add frontend/src/components/range/ResourceRow.tsx
git commit -m "feat(ui): add ResourceRow component"
```

---

## Task 12: Create ResourceSection component

**Files:**
- Create: `frontend/src/components/range/ResourceSection.tsx`

**Step 1: Create the component**

```typescript
// frontend/src/components/range/ResourceSection.tsx
import { ReactNode } from 'react'

interface Props {
  title: string
  completed: number
  total: number
  children: ReactNode
}

export function ResourceSection({ title, completed, total, children }: Props) {
  const isComplete = completed === total && total > 0
  const hasFailures = completed < total && total > 0

  return (
    <div className="border-b border-gray-700 last:border-b-0">
      <div className="flex items-center justify-between px-4 py-2 bg-gray-800">
        <span className="text-sm font-medium text-gray-300 uppercase tracking-wide">
          {title}
        </span>
        <span className={
          isComplete ? 'text-green-400 text-sm' :
          hasFailures ? 'text-yellow-400 text-sm' :
          'text-gray-400 text-sm'
        }>
          {completed}/{total}
        </span>
      </div>
      <div className="bg-gray-900">
        {children}
      </div>
    </div>
  )
}
```

**Step 2: Verify TypeScript compiles**

Run: `cd /Users/JonWFH/jondev/CYROID/frontend && npm run build 2>&1 | head -20`

Expected: No errors

**Step 3: Commit**

```bash
git add frontend/src/components/range/ResourceSection.tsx
git commit -m "feat(ui): add ResourceSection component"
```

---

## Task 13: Refactor DeploymentProgress component

**Files:**
- Modify: `frontend/src/components/range/DeploymentProgress.tsx`

**Step 1: Replace the entire file with the new implementation**

```typescript
// frontend/src/components/range/DeploymentProgress.tsx
import { useEffect, useState, useRef } from 'react'
import { Loader2, ChevronDown, ChevronUp } from 'lucide-react'
import { rangesApi, eventsApi } from '../../services/api'
import { DeploymentStatusResponse, EventLog, EventType } from '../../types'
import { ResourceSection } from './ResourceSection'
import { ResourceRow } from './ResourceRow'

interface Props {
  rangeId: string
  rangeStatus: string
  onDeploymentComplete?: () => void
}

const DEPLOYMENT_EVENT_TYPES: EventType[] = [
  'deployment_started',
  'deployment_step',
  'deployment_completed',
  'deployment_failed',
  'router_creating',
  'router_created',
  'network_creating',
  'network_created',
  'vm_creating',
  'vm_started',
]

export function DeploymentProgress({
  rangeId,
  rangeStatus,
  onDeploymentComplete
}: Props) {
  const [status, setStatus] = useState<DeploymentStatusResponse | null>(null)
  const [events, setEvents] = useState<EventLog[]>([])
  const [showLog, setShowLog] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const logEndRef = useRef<HTMLDivElement>(null)
  const prevEventsLengthRef = useRef(0)

  // Poll for deployment status
  useEffect(() => {
    if (rangeStatus !== 'deploying') return

    const loadStatus = async () => {
      try {
        const response = await rangesApi.getDeploymentStatus(rangeId)
        setStatus(response.data)

        // Check if deployment completed
        if (response.data.status === 'deployed') {
          onDeploymentComplete?.()
        }
      } catch (err) {
        console.error('Failed to load deployment status:', err)
        setError('Failed to load deployment status')
      }
    }

    loadStatus()
    const interval = setInterval(loadStatus, 1000)
    return () => clearInterval(interval)
  }, [rangeId, rangeStatus, onDeploymentComplete])

  // Poll for events (for the log)
  useEffect(() => {
    if (rangeStatus !== 'deploying') return

    const loadEvents = async () => {
      try {
        const response = await eventsApi.getEvents(rangeId, {
          limit: 100,
          event_types: DEPLOYMENT_EVENT_TYPES
        })
        setEvents(response.data.events.reverse())
      } catch (err) {
        console.error('Failed to load events:', err)
      }
    }

    loadEvents()
    const interval = setInterval(loadEvents, 1000)
    return () => clearInterval(interval)
  }, [rangeId, rangeStatus])

  // Auto-scroll log
  useEffect(() => {
    if (events.length > prevEventsLengthRef.current && showLog) {
      logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
    prevEventsLengthRef.current = events.length
  }, [events.length, showLog])

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString()
  }

  const formatElapsed = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }

  if (error) {
    return (
      <div className="bg-red-900/50 rounded-lg p-4 text-red-200">
        {error}
      </div>
    )
  }

  if (!status) {
    return (
      <div className="bg-gray-800 rounded-lg p-8 flex items-center justify-center">
        <Loader2 className="w-6 h-6 text-blue-500 animate-spin" />
      </div>
    )
  }

  const routerCompleted = status.router?.status === 'running' ? 1 : 0
  const networksCompleted = status.networks.filter(n => n.status === 'created').length
  const vmsCompleted = status.vms.filter(v => v.status === 'running').length

  return (
    <div className="bg-gray-800 rounded-lg shadow-lg border border-gray-700 overflow-hidden">
      {/* Header */}
      <div className="bg-blue-900/50 px-6 py-4 border-b border-gray-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Loader2 className="w-5 h-5 text-blue-400 animate-spin" />
            <h3 className="text-lg font-semibold text-white">Deploying Range...</h3>
          </div>
          <span className="text-gray-400 text-sm">
            Elapsed: {formatElapsed(status.elapsedSeconds)}
          </span>
        </div>

        {/* Progress bar */}
        <div className="mt-3">
          <div className="flex items-center justify-between text-sm text-gray-400 mb-1">
            <span>{status.summary.completed} of {status.summary.total} resources</span>
            <span>{Math.round((status.summary.completed / status.summary.total) * 100)}%</span>
          </div>
          <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 transition-all duration-300"
              style={{ width: `${(status.summary.completed / status.summary.total) * 100}%` }}
            />
          </div>
        </div>
      </div>

      {/* Resource Sections */}
      <div>
        {/* Router */}
        {status.router && (
          <ResourceSection title="Router" completed={routerCompleted} total={1}>
            <ResourceRow
              name={status.router.name}
              detail="VyOS 1.4"
              status={status.router.status}
              statusDetail={status.router.statusDetail}
              durationMs={status.router.durationMs}
            />
          </ResourceSection>
        )}

        {/* Networks */}
        <ResourceSection title="Networks" completed={networksCompleted} total={status.networks.length}>
          {status.networks.map(network => (
            <ResourceRow
              key={network.id}
              name={network.name}
              detail={network.subnet}
              status={network.status}
              statusDetail={network.statusDetail}
              durationMs={network.durationMs}
            />
          ))}
        </ResourceSection>

        {/* VMs */}
        <ResourceSection title="VMs" completed={vmsCompleted} total={status.vms.length}>
          {status.vms.map(vm => (
            <ResourceRow
              key={vm.id}
              name={vm.hostname}
              detail={vm.ip}
              status={vm.status}
              statusDetail={vm.statusDetail}
              durationMs={vm.durationMs}
            />
          ))}
        </ResourceSection>
      </div>

      {/* Expandable Log */}
      <div className="border-t border-gray-700">
        <button
          onClick={() => setShowLog(!showLog)}
          className="w-full px-4 py-3 flex items-center justify-between text-sm text-gray-400 hover:bg-gray-700/50"
        >
          <span>Deployment Log ({events.length} events)</span>
          {showLog ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>

        {showLog && (
          <div className="max-h-64 overflow-y-auto bg-gray-900 p-4">
            {events.length === 0 ? (
              <p className="text-gray-500 text-sm">Waiting for deployment events...</p>
            ) : (
              <div className="space-y-1 font-mono text-xs">
                {events.map((event) => (
                  <div key={event.id} className="flex items-start gap-2">
                    <span className="text-gray-500 whitespace-nowrap">
                      [{formatTime(event.created_at)}]
                    </span>
                    <span className={
                      event.event_type === 'deployment_failed' ? 'text-red-400' :
                      event.event_type === 'deployment_completed' ? 'text-green-400' :
                      event.event_type.includes('created') || event.event_type === 'vm_started' ? 'text-green-400' :
                      event.event_type.includes('creating') ? 'text-yellow-400' :
                      'text-gray-300'
                    }>
                      {event.message}
                    </span>
                  </div>
                ))}
                <div ref={logEndRef} />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
```

**Step 2: Update the Props in RangeDetail.tsx if needed**

The new component no longer needs `totalNetworks` and `totalVMs` props. Check if RangeDetail passes them and remove if so.

**Step 3: Verify TypeScript compiles**

Run: `cd /Users/JonWFH/jondev/CYROID/frontend && npm run build 2>&1 | head -30`

Expected: No errors (or only unrelated warnings)

**Step 4: Commit**

```bash
git add frontend/src/components/range/DeploymentProgress.tsx
git commit -m "feat(ui): refactor DeploymentProgress with per-resource status"
```

---

## Task 14: Update RangeDetail to use new DeploymentProgress

**Files:**
- Modify: `frontend/src/pages/RangeDetail.tsx`

**Step 1: Find where DeploymentProgress is used and update props**

Find the `<DeploymentProgress` component usage and update to:

```typescript
<DeploymentProgress
  rangeId={rangeId!}
  rangeStatus={range.status}
  onDeploymentComplete={() => loadRange()}
/>
```

Remove `totalNetworks` and `totalVMs` props if present.

**Step 2: Verify TypeScript compiles**

Run: `cd /Users/JonWFH/jondev/CYROID/frontend && npm run build 2>&1 | head -30`

Expected: Build succeeds

**Step 3: Commit**

```bash
git add frontend/src/pages/RangeDetail.tsx
git commit -m "feat(ui): update RangeDetail to use refactored DeploymentProgress"
```

---

## Task 15: Test the feature end-to-end

**Step 1: Rebuild and restart containers**

```bash
docker-compose build frontend && docker-compose up -d
```

**Step 2: Run backend tests to ensure no regressions**

```bash
docker-compose exec api pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: Tests pass (some may be skipped)

**Step 3: Manual test in browser**

1. Navigate to http://localhost:3000
2. Login
3. Create a new range with 1-2 networks and 1-2 VMs
4. Click Deploy
5. Verify you see individual resource rows for router, each network, and each VM
6. Verify status updates in real-time
7. Verify the log still works

**Step 4: Final commit with version bump**

Update `backend/cyroid/config.py`:
```python
app_version: str = "0.6.2"
```

Update `CHANGELOG.md` with new entry.

```bash
git add backend/cyroid/config.py CHANGELOG.md
git commit -m "chore: release v0.6.2 - granular deployment status"
git tag -a v0.6.2 -m "v0.6.2 - Granular Deployment Status"
git push origin master --tags
```

---

## Summary

| Task | Description |
|------|-------------|
| 1 | Add network_id to EventLog model |
| 2 | Create Alembic migration |
| 3 | Update EventService for network_id |
| 4 | Update EventLog schemas |
| 5 | Create deployment status schemas |
| 6 | Add deployment-status endpoint |
| 7 | Update network event logging |
| 8 | Add frontend types |
| 9 | Add API call |
| 10 | Create StatusIcon component |
| 11 | Create ResourceRow component |
| 12 | Create ResourceSection component |
| 13 | Refactor DeploymentProgress |
| 14 | Update RangeDetail |
| 15 | Test and release |
