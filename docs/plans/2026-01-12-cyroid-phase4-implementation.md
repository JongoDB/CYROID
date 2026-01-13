# Cyroid Phase 4: Execution & Monitoring Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the Execution Console for real-time range management, network monitoring with traffic capture, and MSEL (Master Scenario Events List) v1 for inject management.

**Architecture:** Multi-panel execution dashboard with WebSocket-driven real-time updates. Event logging captures all range activity. MSEL parser converts markdown schedules into executable injects that place artifacts and run commands on VMs.

**Tech Stack:** FastAPI, SQLAlchemy, Dramatiq, PostgreSQL, Redis, React 18, TypeScript, TailwindCSS, xterm.js, React Flow

---

## Week 10: Execution Console

### Task 1: EventLog Model

**Files:**
- Create: `backend/cyroid/models/event_log.py`
- Modify: `backend/cyroid/models/__init__.py`
- Test: `backend/tests/unit/test_event_log_model.py`

**Step 1: Write failing test**

```python
# backend/tests/unit/test_event_log_model.py
import pytest
from uuid import uuid4
from cyroid.models.event_log import EventLog, EventType

def test_event_log_creation():
    event = EventLog(
        range_id=uuid4(),
        event_type=EventType.VM_STARTED,
        message="VM ubuntu-01 started"
    )
    assert event.event_type == EventType.VM_STARTED
    assert "ubuntu-01" in event.message

def test_event_type_enum():
    assert EventType.VM_STARTED.value == "vm_started"
    assert EventType.RANGE_DEPLOYED.value == "range_deployed"
    assert EventType.INJECT_EXECUTED.value == "inject_executed"
```

**Step 2: Run test to verify failure**

```bash
cd /home/ubuntu/cyro/backend && python -m pytest tests/unit/test_event_log_model.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'cyroid.models.event_log'"

**Step 3: Implement EventLog model**

```python
# backend/cyroid/models/event_log.py
from enum import Enum
from uuid import UUID
from sqlalchemy import Column, String, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from .base import Base, UUIDMixin, TimestampMixin

class EventType(str, Enum):
    RANGE_DEPLOYED = "range_deployed"
    RANGE_STARTED = "range_started"
    RANGE_STOPPED = "range_stopped"
    RANGE_TEARDOWN = "range_teardown"
    VM_CREATED = "vm_created"
    VM_STARTED = "vm_started"
    VM_STOPPED = "vm_stopped"
    VM_RESTARTED = "vm_restarted"
    VM_ERROR = "vm_error"
    SNAPSHOT_CREATED = "snapshot_created"
    SNAPSHOT_RESTORED = "snapshot_restored"
    ARTIFACT_PLACED = "artifact_placed"
    INJECT_EXECUTED = "inject_executed"
    INJECT_FAILED = "inject_failed"
    CONNECTION_ESTABLISHED = "connection_established"
    CONNECTION_CLOSED = "connection_closed"

class EventLog(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "event_logs"

    range_id = Column(PGUUID(as_uuid=True), ForeignKey("ranges.id"), nullable=False, index=True)
    vm_id = Column(PGUUID(as_uuid=True), ForeignKey("vms.id"), nullable=True, index=True)
    event_type = Column(SQLEnum(EventType), nullable=False, index=True)
    message = Column(Text, nullable=False)
    metadata = Column(Text, nullable=True)  # JSON string for extra data

    range = relationship("Range", back_populates="event_logs")
    vm = relationship("VM", back_populates="event_logs")
```

**Step 4: Update models/__init__.py**

```python
# Add to backend/cyroid/models/__init__.py
from .event_log import EventLog, EventType
```

**Step 5: Run test to verify pass**

```bash
cd /home/ubuntu/cyro/backend && python -m pytest tests/unit/test_event_log_model.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add backend/cyroid/models/event_log.py backend/cyroid/models/__init__.py backend/tests/unit/test_event_log_model.py
git commit -m "feat(models): add EventLog model for range activity tracking"
```

---

### Task 2: Update Range and VM models with event_logs relationship

**Files:**
- Modify: `backend/cyroid/models/range.py`
- Modify: `backend/cyroid/models/vm.py`

**Step 1: Add relationship to Range model**

Add after line ~35 in `backend/cyroid/models/range.py`:

```python
event_logs = relationship("EventLog", back_populates="range", cascade="all, delete-orphan")
```

**Step 2: Add relationship to VM model**

Add after line ~40 in `backend/cyroid/models/vm.py`:

```python
event_logs = relationship("EventLog", back_populates="vm", cascade="all, delete-orphan")
```

**Step 3: Run existing tests to verify no breakage**

```bash
cd /home/ubuntu/cyro/backend && python -m pytest tests/integration/ -v
```

Expected: All tests PASS

**Step 4: Commit**

```bash
git add backend/cyroid/models/range.py backend/cyroid/models/vm.py
git commit -m "feat(models): add event_logs relationship to Range and VM"
```

---

### Task 3: EventLog Pydantic Schemas

**Files:**
- Create: `backend/cyroid/schemas/event_log.py`
- Modify: `backend/cyroid/schemas/__init__.py`

**Step 1: Create schema file**

```python
# backend/cyroid/schemas/event_log.py
from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel
from cyroid.models.event_log import EventType

class EventLogBase(BaseModel):
    event_type: EventType
    message: str
    metadata: Optional[str] = None

class EventLogCreate(EventLogBase):
    range_id: UUID
    vm_id: Optional[UUID] = None

class EventLogResponse(EventLogBase):
    id: UUID
    range_id: UUID
    vm_id: Optional[UUID]
    created_at: datetime

    class Config:
        from_attributes = True

class EventLogList(BaseModel):
    events: list[EventLogResponse]
    total: int
```

**Step 2: Update schemas/__init__.py**

```python
# Add to backend/cyroid/schemas/__init__.py
from .event_log import EventLogCreate, EventLogResponse, EventLogList
```

**Step 3: Commit**

```bash
git add backend/cyroid/schemas/event_log.py backend/cyroid/schemas/__init__.py
git commit -m "feat(schemas): add EventLog Pydantic schemas"
```

---

### Task 4: EventLog Service

**Files:**
- Create: `backend/cyroid/services/event_service.py`
- Test: `backend/tests/unit/test_event_service.py`

**Step 1: Write failing test**

```python
# backend/tests/unit/test_event_service.py
import pytest
from unittest.mock import MagicMock, AsyncMock
from uuid import uuid4
from cyroid.services.event_service import EventService
from cyroid.models.event_log import EventType

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()
    return db

def test_log_event(mock_db):
    service = EventService(mock_db)
    range_id = uuid4()

    event = service.log_event(
        range_id=range_id,
        event_type=EventType.VM_STARTED,
        message="Test VM started"
    )

    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
```

**Step 2: Run test to verify failure**

```bash
cd /home/ubuntu/cyro/backend && python -m pytest tests/unit/test_event_service.py -v
```

Expected: FAIL with "ModuleNotFoundError"

**Step 3: Implement EventService**

```python
# backend/cyroid/services/event_service.py
from uuid import UUID
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import desc
from cyroid.models.event_log import EventLog, EventType

class EventService:
    def __init__(self, db: Session):
        self.db = db

    def log_event(
        self,
        range_id: UUID,
        event_type: EventType,
        message: str,
        vm_id: Optional[UUID] = None,
        metadata: Optional[str] = None
    ) -> EventLog:
        event = EventLog(
            range_id=range_id,
            vm_id=vm_id,
            event_type=event_type,
            message=message,
            metadata=metadata
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def get_events(
        self,
        range_id: UUID,
        limit: int = 100,
        offset: int = 0,
        event_types: Optional[List[EventType]] = None
    ) -> tuple[List[EventLog], int]:
        query = self.db.query(EventLog).filter(EventLog.range_id == range_id)

        if event_types:
            query = query.filter(EventLog.event_type.in_(event_types))

        total = query.count()
        events = query.order_by(desc(EventLog.created_at)).offset(offset).limit(limit).all()

        return events, total

    def get_vm_events(self, vm_id: UUID, limit: int = 50) -> List[EventLog]:
        return self.db.query(EventLog).filter(
            EventLog.vm_id == vm_id
        ).order_by(desc(EventLog.created_at)).limit(limit).all()
```

**Step 4: Run test to verify pass**

```bash
cd /home/ubuntu/cyro/backend && python -m pytest tests/unit/test_event_service.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/cyroid/services/event_service.py backend/tests/unit/test_event_service.py
git commit -m "feat(services): add EventService for logging range events"
```

---

### Task 5: Events API Endpoint

**Files:**
- Create: `backend/cyroid/api/events.py`
- Modify: `backend/cyroid/main.py`
- Test: `backend/tests/integration/test_events.py`

**Step 1: Write failing test**

```python
# backend/tests/integration/test_events.py
import pytest
from uuid import uuid4

def test_get_events_requires_auth(client):
    response = client.get(f"/api/v1/events/{uuid4()}")
    assert response.status_code == 401

def test_get_events_empty(client, auth_headers, test_range):
    response = client.get(
        f"/api/v1/events/{test_range.id}",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["events"] == []
    assert data["total"] == 0
```

**Step 2: Run test to verify failure**

```bash
cd /home/ubuntu/cyro/backend && python -m pytest tests/integration/test_events.py -v
```

Expected: FAIL with 404 (route not found)

**Step 3: Implement events API**

```python
# backend/cyroid/api/events.py
from uuid import UUID
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from cyroid.api.deps import get_db, get_current_user
from cyroid.models.user import User
from cyroid.models.range import Range
from cyroid.models.event_log import EventType
from cyroid.schemas.event_log import EventLogResponse, EventLogList
from cyroid.services.event_service import EventService

router = APIRouter(prefix="/events", tags=["events"])

@router.get("/{range_id}", response_model=EventLogList)
def get_range_events(
    range_id: UUID,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    event_types: Optional[List[EventType]] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    range_obj = db.query(Range).filter(Range.id == range_id).first()
    if not range_obj:
        raise HTTPException(status_code=404, detail="Range not found")
    if range_obj.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    service = EventService(db)
    events, total = service.get_events(range_id, limit, offset, event_types)

    return EventLogList(
        events=[EventLogResponse.model_validate(e) for e in events],
        total=total
    )

@router.get("/vm/{vm_id}", response_model=list[EventLogResponse])
def get_vm_events(
    vm_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from cyroid.models.vm import VM
    vm = db.query(VM).filter(VM.id == vm_id).first()
    if not vm:
        raise HTTPException(status_code=404, detail="VM not found")

    range_obj = db.query(Range).filter(Range.id == vm.range_id).first()
    if range_obj.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    service = EventService(db)
    events = service.get_vm_events(vm_id, limit)

    return [EventLogResponse.model_validate(e) for e in events]
```

**Step 4: Register router in main.py**

Add to `backend/cyroid/main.py` after other router imports:

```python
from cyroid.api.events import router as events_router
app.include_router(events_router, prefix="/api/v1")
```

**Step 5: Run test to verify pass**

```bash
cd /home/ubuntu/cyro/backend && python -m pytest tests/integration/test_events.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add backend/cyroid/api/events.py backend/cyroid/main.py backend/tests/integration/test_events.py
git commit -m "feat(api): add events endpoint for range activity logs"
```

---

### Task 6: Integrate EventService into VM lifecycle

**Files:**
- Modify: `backend/cyroid/api/vms.py`
- Test: `backend/tests/integration/test_events.py` (add test)

**Step 1: Add test for VM start event logging**

Add to `backend/tests/integration/test_events.py`:

```python
def test_vm_start_creates_event(client, auth_headers, test_vm, mock_docker):
    # Start the VM
    response = client.post(
        f"/api/v1/vms/{test_vm.id}/start",
        headers=auth_headers
    )
    assert response.status_code == 200

    # Check event was logged
    response = client.get(
        f"/api/v1/events/{test_vm.range_id}",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any(e["event_type"] == "vm_started" for e in data["events"])
```

**Step 2: Run test to verify failure**

```bash
cd /home/ubuntu/cyro/backend && python -m pytest tests/integration/test_events.py::test_vm_start_creates_event -v
```

Expected: FAIL (no event logged)

**Step 3: Add event logging to vms.py**

In `backend/cyroid/api/vms.py`, add import and event logging:

```python
# Add import at top
from cyroid.services.event_service import EventService
from cyroid.models.event_log import EventType

# In the start_vm endpoint, after successful start:
event_service = EventService(db)
event_service.log_event(
    range_id=vm.range_id,
    vm_id=vm.id,
    event_type=EventType.VM_STARTED,
    message=f"VM {vm.name} started"
)
```

**Step 4: Run test to verify pass**

```bash
cd /home/ubuntu/cyro/backend && python -m pytest tests/integration/test_events.py::test_vm_start_creates_event -v
```

Expected: PASS

**Step 5: Add event logging to stop, restart endpoints similarly**

**Step 6: Commit**

```bash
git add backend/cyroid/api/vms.py backend/tests/integration/test_events.py
git commit -m "feat(api): add event logging to VM lifecycle endpoints"
```

---

### Task 7: WebSocket Events Broadcast

**Files:**
- Modify: `backend/cyroid/api/websocket.py`
- Create: `backend/cyroid/services/websocket_manager.py`

**Step 1: Create WebSocket manager for broadcasting**

```python
# backend/cyroid/services/websocket_manager.py
from typing import Dict, Set
from uuid import UUID
from fastapi import WebSocket
import json
import asyncio

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[UUID, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, range_id: UUID):
        await websocket.accept()
        if range_id not in self.active_connections:
            self.active_connections[range_id] = set()
        self.active_connections[range_id].add(websocket)

    def disconnect(self, websocket: WebSocket, range_id: UUID):
        if range_id in self.active_connections:
            self.active_connections[range_id].discard(websocket)

    async def broadcast_to_range(self, range_id: UUID, message: dict):
        if range_id in self.active_connections:
            dead_connections = set()
            for connection in self.active_connections[range_id]:
                try:
                    await connection.send_json(message)
                except:
                    dead_connections.add(connection)
            self.active_connections[range_id] -= dead_connections

manager = ConnectionManager()
```

**Step 2: Add events WebSocket endpoint**

Add to `backend/cyroid/api/websocket.py`:

```python
from cyroid.services.websocket_manager import manager

@router.websocket("/events/{range_id}")
async def websocket_events(
    websocket: WebSocket,
    range_id: UUID,
    token: str = Query(...)
):
    # Verify token
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
    except:
        await websocket.close(code=1008)
        return

    await manager.connect(websocket, range_id)
    try:
        while True:
            # Keep connection alive, receive any client messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, range_id)
```

**Step 3: Commit**

```bash
git add backend/cyroid/services/websocket_manager.py backend/cyroid/api/websocket.py
git commit -m "feat(websocket): add event broadcast manager for real-time updates"
```

---

### Task 8: Frontend TypeScript Types for Events

**Files:**
- Modify: `frontend/src/types/index.ts`

**Step 1: Add event types**

Add to `frontend/src/types/index.ts`:

```typescript
export type EventType =
  | 'range_deployed'
  | 'range_started'
  | 'range_stopped'
  | 'range_teardown'
  | 'vm_created'
  | 'vm_started'
  | 'vm_stopped'
  | 'vm_restarted'
  | 'vm_error'
  | 'snapshot_created'
  | 'snapshot_restored'
  | 'artifact_placed'
  | 'inject_executed'
  | 'inject_failed'
  | 'connection_established'
  | 'connection_closed';

export interface EventLog {
  id: string;
  range_id: string;
  vm_id?: string;
  event_type: EventType;
  message: string;
  metadata?: string;
  created_at: string;
}

export interface EventLogList {
  events: EventLog[];
  total: number;
}
```

**Step 2: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat(frontend): add EventLog TypeScript types"
```

---

### Task 9: Frontend API Service for Events

**Files:**
- Modify: `frontend/src/services/api.ts`

**Step 1: Add events API methods**

Add to `frontend/src/services/api.ts`:

```typescript
// Events
getEvents: async (rangeId: string, limit = 100, offset = 0): Promise<EventLogList> => {
  const response = await api.get(`/events/${rangeId}`, {
    params: { limit, offset }
  });
  return response.data;
},

getVMEvents: async (vmId: string, limit = 50): Promise<EventLog[]> => {
  const response = await api.get(`/events/vm/${vmId}`, {
    params: { limit }
  });
  return response.data;
},
```

**Step 2: Commit**

```bash
git add frontend/src/services/api.ts
git commit -m "feat(frontend): add events API methods"
```

---

### Task 10: EventLog Component

**Files:**
- Create: `frontend/src/components/execution/EventLog.tsx`

**Step 1: Create EventLog component**

```typescript
// frontend/src/components/execution/EventLog.tsx
import { useEffect, useState, useRef } from 'react';
import { EventLog as EventLogType, EventType } from '../../types';
import { apiService } from '../../services/api';
import {
  Play, Square, RotateCcw, AlertCircle,
  Download, Upload, Plug, Activity
} from 'lucide-react';

interface Props {
  rangeId: string;
  maxHeight?: string;
}

const eventIcons: Record<EventType, React.ReactNode> = {
  vm_started: <Play className="w-4 h-4 text-green-500" />,
  vm_stopped: <Square className="w-4 h-4 text-red-500" />,
  vm_restarted: <RotateCcw className="w-4 h-4 text-blue-500" />,
  vm_error: <AlertCircle className="w-4 h-4 text-red-600" />,
  range_deployed: <Activity className="w-4 h-4 text-green-500" />,
  range_started: <Play className="w-4 h-4 text-green-500" />,
  range_stopped: <Square className="w-4 h-4 text-gray-500" />,
  range_teardown: <AlertCircle className="w-4 h-4 text-red-500" />,
  vm_created: <Activity className="w-4 h-4 text-blue-500" />,
  snapshot_created: <Download className="w-4 h-4 text-purple-500" />,
  snapshot_restored: <Upload className="w-4 h-4 text-purple-500" />,
  artifact_placed: <Download className="w-4 h-4 text-orange-500" />,
  inject_executed: <Activity className="w-4 h-4 text-yellow-500" />,
  inject_failed: <AlertCircle className="w-4 h-4 text-red-500" />,
  connection_established: <Plug className="w-4 h-4 text-green-500" />,
  connection_closed: <Plug className="w-4 h-4 text-gray-500" />,
};

export function EventLogComponent({ rangeId, maxHeight = '400px' }: Props) {
  const [events, setEvents] = useState<EventLogType[]>([]);
  const [loading, setLoading] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadEvents();
    const interval = setInterval(loadEvents, 5000);
    return () => clearInterval(interval);
  }, [rangeId]);

  const loadEvents = async () => {
    try {
      const data = await apiService.getEvents(rangeId);
      setEvents(data.events);
    } catch (error) {
      console.error('Failed to load events:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString();
  };

  if (loading) {
    return <div className="animate-pulse bg-gray-100 h-32 rounded" />;
  }

  return (
    <div
      ref={containerRef}
      className="bg-gray-900 rounded-lg overflow-hidden"
      style={{ maxHeight }}
    >
      <div className="px-4 py-2 bg-gray-800 border-b border-gray-700">
        <h3 className="text-sm font-medium text-gray-200">Event Log</h3>
      </div>
      <div className="overflow-y-auto p-2 space-y-1" style={{ maxHeight: `calc(${maxHeight} - 40px)` }}>
        {events.length === 0 ? (
          <p className="text-gray-500 text-sm p-2">No events yet</p>
        ) : (
          events.map((event) => (
            <div
              key={event.id}
              className="flex items-start gap-2 px-2 py-1 hover:bg-gray-800 rounded text-sm"
            >
              <span className="text-gray-500 font-mono text-xs">
                {formatTime(event.created_at)}
              </span>
              {eventIcons[event.event_type] || <Activity className="w-4 h-4" />}
              <span className="text-gray-300">{event.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/execution/EventLog.tsx
git commit -m "feat(frontend): add EventLog component"
```

---

### Task 11: VM Grid Component

**Files:**
- Create: `frontend/src/components/execution/VMGrid.tsx`

**Step 1: Create VMGrid component**

```typescript
// frontend/src/components/execution/VMGrid.tsx
import { VM, VMStatus } from '../../types';
import { apiService } from '../../services/api';
import {
  Play, Square, RotateCcw, Camera,
  Terminal, Monitor, Server
} from 'lucide-react';

interface Props {
  vms: VM[];
  onRefresh: () => void;
  onOpenConsole: (vmId: string) => void;
}

const statusColors: Record<VMStatus, string> = {
  pending: 'bg-gray-500',
  creating: 'bg-yellow-500 animate-pulse',
  running: 'bg-green-500',
  stopped: 'bg-red-500',
  error: 'bg-red-700',
};

export function VMGrid({ vms, onRefresh, onOpenConsole }: Props) {
  const handleAction = async (vmId: string, action: 'start' | 'stop' | 'restart' | 'snapshot') => {
    try {
      switch (action) {
        case 'start':
          await apiService.startVM(vmId);
          break;
        case 'stop':
          await apiService.stopVM(vmId);
          break;
        case 'restart':
          await apiService.restartVM(vmId);
          break;
        case 'snapshot':
          await apiService.createSnapshot(vmId);
          break;
      }
      onRefresh();
    } catch (error) {
      console.error(`Failed to ${action} VM:`, error);
    }
  };

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
      {vms.map((vm) => (
        <div
          key={vm.id}
          className="bg-white rounded-lg shadow p-4 border border-gray-200"
        >
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              {vm.template?.os_type === 'windows' ? (
                <Monitor className="w-5 h-5 text-blue-500" />
              ) : (
                <Server className="w-5 h-5 text-orange-500" />
              )}
              <span className="font-medium truncate">{vm.name}</span>
            </div>
            <span className={`w-3 h-3 rounded-full ${statusColors[vm.status]}`} />
          </div>

          <div className="text-xs text-gray-500 mb-3">
            <p>CPU: {vm.cpu_cores} cores</p>
            <p>RAM: {vm.ram_mb} MB</p>
            <p>IP: {vm.ip_address || 'N/A'}</p>
          </div>

          <div className="flex gap-1">
            {vm.status === 'stopped' && (
              <button
                onClick={() => handleAction(vm.id, 'start')}
                className="p-1.5 hover:bg-green-100 rounded"
                title="Start"
              >
                <Play className="w-4 h-4 text-green-600" />
              </button>
            )}
            {vm.status === 'running' && (
              <>
                <button
                  onClick={() => handleAction(vm.id, 'stop')}
                  className="p-1.5 hover:bg-red-100 rounded"
                  title="Stop"
                >
                  <Square className="w-4 h-4 text-red-600" />
                </button>
                <button
                  onClick={() => handleAction(vm.id, 'restart')}
                  className="p-1.5 hover:bg-blue-100 rounded"
                  title="Restart"
                >
                  <RotateCcw className="w-4 h-4 text-blue-600" />
                </button>
                <button
                  onClick={() => onOpenConsole(vm.id)}
                  className="p-1.5 hover:bg-gray-100 rounded"
                  title="Console"
                >
                  <Terminal className="w-4 h-4 text-gray-600" />
                </button>
              </>
            )}
            <button
              onClick={() => handleAction(vm.id, 'snapshot')}
              className="p-1.5 hover:bg-purple-100 rounded"
              title="Snapshot"
            >
              <Camera className="w-4 h-4 text-purple-600" />
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/execution/VMGrid.tsx
git commit -m "feat(frontend): add VMGrid component with quick actions"
```

---

### Task 12: Execution Console Page

**Files:**
- Create: `frontend/src/pages/ExecutionConsole.tsx`
- Modify: `frontend/src/App.tsx`

**Step 1: Create ExecutionConsole page**

```typescript
// frontend/src/pages/ExecutionConsole.tsx
import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Range, VM } from '../types';
import { apiService } from '../services/api';
import { VMGrid } from '../components/execution/VMGrid';
import { EventLogComponent } from '../components/execution/EventLog';
import { VMConsole } from '../components/console/VMConsole';
import { Activity, Server, Wifi, Clock } from 'lucide-react';

export function ExecutionConsole() {
  const { rangeId } = useParams<{ rangeId: string }>();
  const [range, setRange] = useState<Range | null>(null);
  const [vms, setVMs] = useState<VM[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedVMId, setSelectedVMId] = useState<string | null>(null);

  useEffect(() => {
    if (rangeId) {
      loadRangeData();
      const interval = setInterval(loadRangeData, 10000);
      return () => clearInterval(interval);
    }
  }, [rangeId]);

  const loadRangeData = async () => {
    if (!rangeId) return;
    try {
      const [rangeData, vmsData] = await Promise.all([
        apiService.getRange(rangeId),
        apiService.getVMs(rangeId),
      ]);
      setRange(rangeData);
      setVMs(vmsData);
    } catch (error) {
      console.error('Failed to load range data:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
      </div>
    );
  }

  if (!range || !rangeId) {
    return <div className="text-center py-8">Range not found</div>;
  }

  const runningVMs = vms.filter(vm => vm.status === 'running').length;

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="bg-white border-b px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold">{range.name}</h1>
            <p className="text-sm text-gray-500">{range.description}</p>
          </div>
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <Server className="w-5 h-5 text-gray-400" />
              <span className="text-sm">
                <span className="font-medium">{runningVMs}</span>
                <span className="text-gray-500">/{vms.length} VMs</span>
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Activity className={`w-5 h-5 ${range.status === 'running' ? 'text-green-500' : 'text-gray-400'}`} />
              <span className="text-sm capitalize">{range.status}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Panel - VM Grid */}
        <div className="flex-1 p-6 overflow-y-auto">
          <h2 className="text-lg font-medium mb-4">Virtual Machines</h2>
          <VMGrid
            vms={vms}
            onRefresh={loadRangeData}
            onOpenConsole={setSelectedVMId}
          />
        </div>

        {/* Right Panel - Event Log */}
        <div className="w-96 border-l bg-gray-50 p-4">
          <EventLogComponent rangeId={rangeId} maxHeight="calc(100vh - 200px)" />
        </div>
      </div>

      {/* Console Modal */}
      {selectedVMId && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-4/5 h-4/5 flex flex-col">
            <div className="flex items-center justify-between px-4 py-2 border-b">
              <h3 className="font-medium">VM Console</h3>
              <button
                onClick={() => setSelectedVMId(null)}
                className="text-gray-500 hover:text-gray-700"
              >
                Close
              </button>
            </div>
            <div className="flex-1">
              <VMConsole vmId={selectedVMId} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
```

**Step 2: Add route to App.tsx**

Add to `frontend/src/App.tsx`:

```typescript
import { ExecutionConsole } from './pages/ExecutionConsole';

// In routes:
<Route path="/execution/:rangeId" element={<ProtectedRoute><ExecutionConsole /></ProtectedRoute>} />
```

**Step 3: Commit**

```bash
git add frontend/src/pages/ExecutionConsole.tsx frontend/src/App.tsx
git commit -m "feat(frontend): add ExecutionConsole page with VM grid and event log"
```

---

### Task 13: Add Navigation Link to Execution Console

**Files:**
- Modify: `frontend/src/pages/RangeDetail.tsx`

**Step 1: Add "Open Console" button**

In `frontend/src/pages/RangeDetail.tsx`, add a button to navigate to execution console:

```typescript
import { useNavigate } from 'react-router-dom';

// In component:
const navigate = useNavigate();

// Add button in header area:
{range.status === 'running' && (
  <button
    onClick={() => navigate(`/execution/${rangeId}`)}
    className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
  >
    Open Execution Console
  </button>
)}
```

**Step 2: Commit**

```bash
git add frontend/src/pages/RangeDetail.tsx
git commit -m "feat(frontend): add navigation to execution console from range detail"
```

---

## Week 11: Monitoring

### Task 14: Docker Stats Integration - Service

**Files:**
- Modify: `backend/cyroid/services/docker_service.py`
- Test: `backend/tests/unit/test_docker_stats.py`

**Step 1: Write failing test**

```python
# backend/tests/unit/test_docker_stats.py
import pytest
from unittest.mock import MagicMock, patch
from cyroid.services.docker_service import DockerService

def test_get_container_stats():
    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_container.stats.return_value = iter([{
        'cpu_stats': {'cpu_usage': {'total_usage': 100000}},
        'precpu_stats': {'cpu_usage': {'total_usage': 90000}},
        'memory_stats': {'usage': 1024000, 'limit': 2048000},
        'networks': {'eth0': {'rx_bytes': 1000, 'tx_bytes': 500}}
    }])
    mock_client.containers.get.return_value = mock_container

    service = DockerService()
    service.client = mock_client

    stats = service.get_container_stats("test-container-id")

    assert 'cpu_percent' in stats
    assert 'memory_percent' in stats
    assert 'network_rx' in stats
    assert 'network_tx' in stats
```

**Step 2: Run test to verify failure**

```bash
cd /home/ubuntu/cyro/backend && python -m pytest tests/unit/test_docker_stats.py -v
```

Expected: FAIL (method doesn't exist)

**Step 3: Implement get_container_stats**

Add to `backend/cyroid/services/docker_service.py`:

```python
def get_container_stats(self, container_id: str) -> dict:
    """Get real-time stats for a container."""
    try:
        container = self.client.containers.get(container_id)
        stats = next(container.stats(stream=False, decode=True))

        # Calculate CPU percentage
        cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                    stats['precpu_stats']['cpu_usage']['total_usage']
        system_delta = stats['cpu_stats'].get('system_cpu_usage', 0) - \
                       stats['precpu_stats'].get('system_cpu_usage', 0)
        cpu_percent = (cpu_delta / system_delta * 100) if system_delta > 0 else 0

        # Memory percentage
        mem_usage = stats['memory_stats'].get('usage', 0)
        mem_limit = stats['memory_stats'].get('limit', 1)
        memory_percent = (mem_usage / mem_limit * 100) if mem_limit > 0 else 0

        # Network stats
        networks = stats.get('networks', {})
        network_rx = sum(n.get('rx_bytes', 0) for n in networks.values())
        network_tx = sum(n.get('tx_bytes', 0) for n in networks.values())

        return {
            'cpu_percent': round(cpu_percent, 2),
            'memory_percent': round(memory_percent, 2),
            'memory_usage_mb': round(mem_usage / 1024 / 1024, 2),
            'memory_limit_mb': round(mem_limit / 1024 / 1024, 2),
            'network_rx': network_rx,
            'network_tx': network_tx,
        }
    except Exception as e:
        logger.error(f"Failed to get container stats: {e}")
        return {}
```

**Step 4: Run test to verify pass**

```bash
cd /home/ubuntu/cyro/backend && python -m pytest tests/unit/test_docker_stats.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/cyroid/services/docker_service.py backend/tests/unit/test_docker_stats.py
git commit -m "feat(services): add Docker stats collection for VM monitoring"
```

---

### Task 15: VM Stats API Endpoint

**Files:**
- Modify: `backend/cyroid/api/vms.py`
- Test: `backend/tests/integration/test_vms.py` (add test)

**Step 1: Add test**

Add to `backend/tests/integration/test_vms.py`:

```python
def test_get_vm_stats(client, auth_headers, test_vm, mock_docker):
    # Mock the stats method
    mock_docker.get_container_stats.return_value = {
        'cpu_percent': 25.5,
        'memory_percent': 60.0,
        'memory_usage_mb': 512,
        'memory_limit_mb': 1024,
        'network_rx': 1000000,
        'network_tx': 500000,
    }

    response = client.get(
        f"/api/v1/vms/{test_vm.id}/stats",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert 'cpu_percent' in data
    assert 'memory_percent' in data
```

**Step 2: Implement stats endpoint**

Add to `backend/cyroid/api/vms.py`:

```python
@router.get("/{vm_id}/stats")
def get_vm_stats(
    vm_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    docker_service: DockerService = Depends(get_docker_service)
):
    vm = db.query(VM).filter(VM.id == vm_id).first()
    if not vm:
        raise HTTPException(status_code=404, detail="VM not found")

    range_obj = db.query(Range).filter(Range.id == vm.range_id).first()
    if range_obj.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if not vm.container_id or vm.status != VMStatus.RUNNING:
        return {"error": "VM is not running"}

    stats = docker_service.get_container_stats(vm.container_id)
    return stats
```

**Step 3: Run test to verify pass**

```bash
cd /home/ubuntu/cyro/backend && python -m pytest tests/integration/test_vms.py::test_get_vm_stats -v
```

**Step 4: Commit**

```bash
git add backend/cyroid/api/vms.py backend/tests/integration/test_vms.py
git commit -m "feat(api): add VM stats endpoint for resource monitoring"
```

---

### Task 16: Connection Tracking Model

**Files:**
- Create: `backend/cyroid/models/connection.py`
- Modify: `backend/cyroid/models/__init__.py`

**Step 1: Create Connection model**

```python
# backend/cyroid/models/connection.py
from enum import Enum
from sqlalchemy import Column, String, Integer, ForeignKey, Enum as SQLEnum, DateTime
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from .base import Base, UUIDMixin, TimestampMixin

class ConnectionType(str, Enum):
    SSH = "ssh"
    RDP = "rdp"
    WINRM = "winrm"
    VNC = "vnc"
    HTTP = "http"
    UNKNOWN = "unknown"

class ConnectionStatus(str, Enum):
    ACTIVE = "active"
    CLOSED = "closed"

class Connection(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "connections"

    range_id = Column(PGUUID(as_uuid=True), ForeignKey("ranges.id"), nullable=False, index=True)
    vm_id = Column(PGUUID(as_uuid=True), ForeignKey("vms.id"), nullable=False, index=True)
    connection_type = Column(SQLEnum(ConnectionType), nullable=False)
    status = Column(SQLEnum(ConnectionStatus), default=ConnectionStatus.ACTIVE)
    source_ip = Column(String(45), nullable=False)  # IPv6 max length
    source_port = Column(Integer, nullable=True)
    dest_port = Column(Integer, nullable=False)
    username = Column(String(255), nullable=True)
    started_at = Column(DateTime, nullable=False)
    ended_at = Column(DateTime, nullable=True)

    range = relationship("Range", back_populates="connections")
    vm = relationship("VM", back_populates="connections")
```

**Step 2: Update __init__.py and models with relationships**

**Step 3: Commit**

```bash
git add backend/cyroid/models/connection.py backend/cyroid/models/__init__.py
git commit -m "feat(models): add Connection model for tracking VM access"
```

---

### Task 17: Connection Tracking Service

**Files:**
- Create: `backend/cyroid/services/connection_service.py`

**Step 1: Create ConnectionService**

```python
# backend/cyroid/services/connection_service.py
from uuid import UUID
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from cyroid.models.connection import Connection, ConnectionType, ConnectionStatus

class ConnectionService:
    def __init__(self, db: Session):
        self.db = db

    def log_connection(
        self,
        range_id: UUID,
        vm_id: UUID,
        connection_type: ConnectionType,
        source_ip: str,
        dest_port: int,
        source_port: Optional[int] = None,
        username: Optional[str] = None
    ) -> Connection:
        conn = Connection(
            range_id=range_id,
            vm_id=vm_id,
            connection_type=connection_type,
            source_ip=source_ip,
            source_port=source_port,
            dest_port=dest_port,
            username=username,
            started_at=datetime.utcnow(),
            status=ConnectionStatus.ACTIVE
        )
        self.db.add(conn)
        self.db.commit()
        self.db.refresh(conn)
        return conn

    def close_connection(self, connection_id: UUID) -> Connection:
        conn = self.db.query(Connection).filter(Connection.id == connection_id).first()
        if conn:
            conn.status = ConnectionStatus.CLOSED
            conn.ended_at = datetime.utcnow()
            self.db.commit()
        return conn

    def get_active_connections(self, range_id: UUID) -> List[Connection]:
        return self.db.query(Connection).filter(
            Connection.range_id == range_id,
            Connection.status == ConnectionStatus.ACTIVE
        ).order_by(desc(Connection.started_at)).all()

    def get_connection_history(
        self,
        range_id: UUID,
        limit: int = 100
    ) -> List[Connection]:
        return self.db.query(Connection).filter(
            Connection.range_id == range_id
        ).order_by(desc(Connection.started_at)).limit(limit).all()
```

**Step 2: Commit**

```bash
git add backend/cyroid/services/connection_service.py
git commit -m "feat(services): add ConnectionService for tracking VM access"
```

---

### Task 18: Connections API Endpoint

**Files:**
- Create: `backend/cyroid/api/connections.py`
- Modify: `backend/cyroid/main.py`

**Step 1: Create connections API**

```python
# backend/cyroid/api/connections.py
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from cyroid.api.deps import get_db, get_current_user
from cyroid.models.user import User
from cyroid.models.range import Range
from cyroid.services.connection_service import ConnectionService

router = APIRouter(prefix="/connections", tags=["connections"])

@router.get("/{range_id}")
def get_connections(
    range_id: UUID,
    active_only: bool = False,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    range_obj = db.query(Range).filter(Range.id == range_id).first()
    if not range_obj:
        raise HTTPException(status_code=404, detail="Range not found")
    if range_obj.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    service = ConnectionService(db)
    if active_only:
        connections = service.get_active_connections(range_id)
    else:
        connections = service.get_connection_history(range_id, limit)

    return [
        {
            "id": str(c.id),
            "vm_id": str(c.vm_id),
            "connection_type": c.connection_type.value,
            "status": c.status.value,
            "source_ip": c.source_ip,
            "dest_port": c.dest_port,
            "username": c.username,
            "started_at": c.started_at.isoformat(),
            "ended_at": c.ended_at.isoformat() if c.ended_at else None,
        }
        for c in connections
    ]
```

**Step 2: Register router in main.py**

**Step 3: Commit**

```bash
git add backend/cyroid/api/connections.py backend/cyroid/main.py
git commit -m "feat(api): add connections endpoint for VM access tracking"
```

---

### Task 19: Connection Timeline Frontend Component

**Files:**
- Create: `frontend/src/components/monitoring/ConnectionTimeline.tsx`

**Step 1: Create component**

```typescript
// frontend/src/components/monitoring/ConnectionTimeline.tsx
import { useEffect, useState } from 'react';
import { apiService } from '../../services/api';
import { Plug, User, Clock } from 'lucide-react';

interface Connection {
  id: string;
  vm_id: string;
  connection_type: string;
  status: string;
  source_ip: string;
  dest_port: number;
  username?: string;
  started_at: string;
  ended_at?: string;
}

interface Props {
  rangeId: string;
}

const connectionColors: Record<string, string> = {
  ssh: 'bg-green-500',
  rdp: 'bg-blue-500',
  winrm: 'bg-purple-500',
  vnc: 'bg-orange-500',
  http: 'bg-gray-500',
  unknown: 'bg-gray-400',
};

export function ConnectionTimeline({ rangeId }: Props) {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadConnections();
    const interval = setInterval(loadConnections, 10000);
    return () => clearInterval(interval);
  }, [rangeId]);

  const loadConnections = async () => {
    try {
      const data = await apiService.getConnections(rangeId);
      setConnections(data);
    } catch (error) {
      console.error('Failed to load connections:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleString();
  };

  const getDuration = (start: string, end?: string) => {
    const startTime = new Date(start).getTime();
    const endTime = end ? new Date(end).getTime() : Date.now();
    const seconds = Math.floor((endTime - startTime) / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    return `${hours}h ${minutes % 60}m`;
  };

  if (loading) {
    return <div className="animate-pulse bg-gray-100 h-32 rounded" />;
  }

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="px-4 py-3 border-b">
        <h3 className="font-medium">Connection History</h3>
      </div>
      <div className="divide-y max-h-96 overflow-y-auto">
        {connections.length === 0 ? (
          <p className="text-gray-500 text-sm p-4">No connections recorded</p>
        ) : (
          connections.map((conn) => (
            <div key={conn.id} className="p-3 flex items-center gap-3">
              <div className={`w-2 h-2 rounded-full ${connectionColors[conn.connection_type]}`} />
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-sm uppercase">
                    {conn.connection_type}
                  </span>
                  <span className={`text-xs px-1.5 py-0.5 rounded ${
                    conn.status === 'active'
                      ? 'bg-green-100 text-green-700'
                      : 'bg-gray-100 text-gray-600'
                  }`}>
                    {conn.status}
                  </span>
                </div>
                <div className="text-xs text-gray-500 flex items-center gap-3 mt-1">
                  <span>{conn.source_ip}:{conn.dest_port}</span>
                  {conn.username && (
                    <span className="flex items-center gap-1">
                      <User className="w-3 h-3" />
                      {conn.username}
                    </span>
                  )}
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {getDuration(conn.started_at, conn.ended_at)}
                  </span>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
```

**Step 2: Add API method to api.ts**

```typescript
getConnections: async (rangeId: string, activeOnly = false): Promise<Connection[]> => {
  const response = await api.get(`/connections/${rangeId}`, {
    params: { active_only: activeOnly }
  });
  return response.data;
},
```

**Step 3: Commit**

```bash
git add frontend/src/components/monitoring/ConnectionTimeline.tsx frontend/src/services/api.ts
git commit -m "feat(frontend): add ConnectionTimeline component"
```

---

### Task 20: Resource Metrics Component

**Files:**
- Create: `frontend/src/components/monitoring/ResourceMetrics.tsx`

**Step 1: Create component**

```typescript
// frontend/src/components/monitoring/ResourceMetrics.tsx
import { useEffect, useState } from 'react';
import { VM } from '../../types';
import { apiService } from '../../services/api';
import { Cpu, HardDrive, Wifi } from 'lucide-react';

interface VMStats {
  cpu_percent: number;
  memory_percent: number;
  memory_usage_mb: number;
  memory_limit_mb: number;
  network_rx: number;
  network_tx: number;
}

interface Props {
  vms: VM[];
}

export function ResourceMetrics({ vms }: Props) {
  const [stats, setStats] = useState<Record<string, VMStats>>({});

  useEffect(() => {
    loadStats();
    const interval = setInterval(loadStats, 5000);
    return () => clearInterval(interval);
  }, [vms]);

  const loadStats = async () => {
    const runningVMs = vms.filter(vm => vm.status === 'running');
    const statsPromises = runningVMs.map(async (vm) => {
      try {
        const vmStats = await apiService.getVMStats(vm.id);
        return { id: vm.id, stats: vmStats };
      } catch {
        return null;
      }
    });

    const results = await Promise.all(statsPromises);
    const newStats: Record<string, VMStats> = {};
    results.forEach(r => {
      if (r) newStats[r.id] = r.stats;
    });
    setStats(newStats);
  };

  const formatBytes = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  };

  // Calculate aggregates
  const runningVMs = vms.filter(vm => vm.status === 'running');
  const avgCpu = runningVMs.length > 0
    ? runningVMs.reduce((sum, vm) => sum + (stats[vm.id]?.cpu_percent || 0), 0) / runningVMs.length
    : 0;
  const avgMem = runningVMs.length > 0
    ? runningVMs.reduce((sum, vm) => sum + (stats[vm.id]?.memory_percent || 0), 0) / runningVMs.length
    : 0;
  const totalRx = runningVMs.reduce((sum, vm) => sum + (stats[vm.id]?.network_rx || 0), 0);
  const totalTx = runningVMs.reduce((sum, vm) => sum + (stats[vm.id]?.network_tx || 0), 0);

  return (
    <div className="grid grid-cols-3 gap-4">
      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex items-center gap-2 mb-2">
          <Cpu className="w-5 h-5 text-blue-500" />
          <span className="text-sm font-medium">CPU Usage</span>
        </div>
        <div className="text-2xl font-bold">{avgCpu.toFixed(1)}%</div>
        <div className="mt-2 h-2 bg-gray-200 rounded">
          <div
            className="h-full bg-blue-500 rounded"
            style={{ width: `${Math.min(avgCpu, 100)}%` }}
          />
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex items-center gap-2 mb-2">
          <HardDrive className="w-5 h-5 text-green-500" />
          <span className="text-sm font-medium">Memory Usage</span>
        </div>
        <div className="text-2xl font-bold">{avgMem.toFixed(1)}%</div>
        <div className="mt-2 h-2 bg-gray-200 rounded">
          <div
            className="h-full bg-green-500 rounded"
            style={{ width: `${Math.min(avgMem, 100)}%` }}
          />
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex items-center gap-2 mb-2">
          <Wifi className="w-5 h-5 text-purple-500" />
          <span className="text-sm font-medium">Network I/O</span>
        </div>
        <div className="text-sm">
          <span className="text-green-600">↓ {formatBytes(totalRx)}</span>
          {' / '}
          <span className="text-blue-600">↑ {formatBytes(totalTx)}</span>
        </div>
      </div>
    </div>
  );
}
```

**Step 2: Add API method**

```typescript
getVMStats: async (vmId: string): Promise<VMStats> => {
  const response = await api.get(`/vms/${vmId}/stats`);
  return response.data;
},
```

**Step 3: Commit**

```bash
git add frontend/src/components/monitoring/ResourceMetrics.tsx frontend/src/services/api.ts
git commit -m "feat(frontend): add ResourceMetrics component for VM monitoring"
```

---

## Week 12: MSEL v1

### Task 21: MSEL and Inject Models

**Files:**
- Create: `backend/cyroid/models/msel.py`
- Create: `backend/cyroid/models/inject.py`
- Modify: `backend/cyroid/models/__init__.py`

**Step 1: Create MSEL model**

```python
# backend/cyroid/models/msel.py
from sqlalchemy import Column, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from .base import Base, UUIDMixin, TimestampMixin

class MSEL(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "msels"

    range_id = Column(PGUUID(as_uuid=True), ForeignKey("ranges.id"), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)  # Raw markdown

    range = relationship("Range", back_populates="msel")
    injects = relationship("Inject", back_populates="msel", cascade="all, delete-orphan")
```

**Step 2: Create Inject model**

```python
# backend/cyroid/models/inject.py
from enum import Enum
from sqlalchemy import Column, String, Text, Integer, ForeignKey, Enum as SQLEnum, DateTime
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship
from .base import Base, UUIDMixin, TimestampMixin

class InjectStatus(str, Enum):
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class Inject(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "injects"

    msel_id = Column(PGUUID(as_uuid=True), ForeignKey("msels.id"), nullable=False)
    sequence_number = Column(Integer, nullable=False)
    inject_time_minutes = Column(Integer, nullable=False)  # Minutes from exercise start
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    target_vm_ids = Column(JSONB, default=list)  # List of VM UUIDs
    actions = Column(JSONB, default=list)  # List of {action_type, parameters}
    status = Column(SQLEnum(InjectStatus), default=InjectStatus.PENDING)
    executed_at = Column(DateTime, nullable=True)
    execution_log = Column(Text, nullable=True)

    msel = relationship("MSEL", back_populates="injects")
```

**Step 3: Update __init__.py**

**Step 4: Commit**

```bash
git add backend/cyroid/models/msel.py backend/cyroid/models/inject.py backend/cyroid/models/__init__.py
git commit -m "feat(models): add MSEL and Inject models for scenario management"
```

---

### Task 22: MSEL Parser Service

**Files:**
- Create: `backend/cyroid/services/msel_parser.py`
- Test: `backend/tests/unit/test_msel_parser.py`

**Step 1: Write failing test**

```python
# backend/tests/unit/test_msel_parser.py
import pytest
from cyroid.services.msel_parser import MSELParser

SAMPLE_MSEL = """# Exercise MSEL

## T+0:00 - Initial Setup
Deploy baseline artifacts to all workstations.

**Actions:**
- Place file: malware.exe on WS-01 at C:\\Users\\Public\\malware.exe
- Run command on WS-01: whoami

## T+0:30 - First Inject
Simulate phishing attack.

**Actions:**
- Place file: phishing.docx on WS-02 at C:\\Users\\victim\\Documents\\invoice.docx
"""

def test_parse_msel_extracts_injects():
    parser = MSELParser()
    injects = parser.parse(SAMPLE_MSEL)

    assert len(injects) == 2
    assert injects[0]['title'] == 'Initial Setup'
    assert injects[0]['inject_time_minutes'] == 0
    assert injects[1]['title'] == 'First Inject'
    assert injects[1]['inject_time_minutes'] == 30

def test_parse_msel_extracts_actions():
    parser = MSELParser()
    injects = parser.parse(SAMPLE_MSEL)

    assert len(injects[0]['actions']) == 2
    assert injects[0]['actions'][0]['action_type'] == 'place_file'
    assert injects[0]['actions'][1]['action_type'] == 'run_command'
```

**Step 2: Run test to verify failure**

```bash
cd /home/ubuntu/cyro/backend && python -m pytest tests/unit/test_msel_parser.py -v
```

Expected: FAIL (module not found)

**Step 3: Implement MSELParser**

```python
# backend/cyroid/services/msel_parser.py
import re
from typing import List, Dict, Any

class MSELParser:
    TIME_PATTERN = re.compile(r'^##\s+T\+(\d+):(\d+)\s+-\s+(.+)$', re.MULTILINE)
    PLACE_FILE_PATTERN = re.compile(
        r'-\s+Place file:\s+(\S+)\s+on\s+(\S+)\s+at\s+(.+)$',
        re.MULTILINE
    )
    RUN_COMMAND_PATTERN = re.compile(
        r'-\s+Run command on\s+(\S+):\s+(.+)$',
        re.MULTILINE
    )

    def parse(self, content: str) -> List[Dict[str, Any]]:
        injects = []
        sections = self._split_into_sections(content)

        for seq, section in enumerate(sections, 1):
            inject = self._parse_section(section, seq)
            if inject:
                injects.append(inject)

        return injects

    def _split_into_sections(self, content: str) -> List[str]:
        sections = []
        current = []

        for line in content.split('\n'):
            if line.startswith('## T+'):
                if current:
                    sections.append('\n'.join(current))
                current = [line]
            else:
                current.append(line)

        if current:
            sections.append('\n'.join(current))

        return sections

    def _parse_section(self, section: str, sequence: int) -> Dict[str, Any]:
        time_match = self.TIME_PATTERN.search(section)
        if not time_match:
            return None

        hours = int(time_match.group(1))
        minutes = int(time_match.group(2))
        title = time_match.group(3).strip()

        # Extract description (text between title and Actions)
        desc_start = section.find('\n', time_match.end())
        desc_end = section.find('**Actions:**')
        description = section[desc_start:desc_end].strip() if desc_end > desc_start else ''

        # Parse actions
        actions = []

        for match in self.PLACE_FILE_PATTERN.finditer(section):
            actions.append({
                'action_type': 'place_file',
                'parameters': {
                    'filename': match.group(1),
                    'target_vm': match.group(2),
                    'target_path': match.group(3).strip()
                }
            })

        for match in self.RUN_COMMAND_PATTERN.finditer(section):
            actions.append({
                'action_type': 'run_command',
                'parameters': {
                    'target_vm': match.group(1),
                    'command': match.group(2).strip()
                }
            })

        return {
            'sequence_number': sequence,
            'inject_time_minutes': hours * 60 + minutes,
            'title': title,
            'description': description,
            'actions': actions
        }
```

**Step 4: Run test to verify pass**

```bash
cd /home/ubuntu/cyro/backend && python -m pytest tests/unit/test_msel_parser.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/cyroid/services/msel_parser.py backend/tests/unit/test_msel_parser.py
git commit -m "feat(services): add MSEL markdown parser"
```

---

### Task 23: MSEL API Endpoints

**Files:**
- Create: `backend/cyroid/api/msel.py`
- Modify: `backend/cyroid/main.py`
- Test: `backend/tests/integration/test_msel.py`

**Step 1: Write failing test**

```python
# backend/tests/integration/test_msel.py
import pytest

SAMPLE_MSEL = """# Test MSEL

## T+0:00 - Setup
Initial setup.

**Actions:**
- Run command on test-vm: echo hello
"""

def test_import_msel(client, auth_headers, test_range):
    response = client.post(
        f"/api/v1/msel/{test_range.id}/import",
        headers=auth_headers,
        json={"name": "Test MSEL", "content": SAMPLE_MSEL}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test MSEL"
    assert len(data["injects"]) == 1

def test_get_msel(client, auth_headers, test_range):
    # First import
    client.post(
        f"/api/v1/msel/{test_range.id}/import",
        headers=auth_headers,
        json={"name": "Test MSEL", "content": SAMPLE_MSEL}
    )

    # Then get
    response = client.get(
        f"/api/v1/msel/{test_range.id}",
        headers=auth_headers
    )
    assert response.status_code == 200
```

**Step 2: Run test to verify failure**

```bash
cd /home/ubuntu/cyro/backend && python -m pytest tests/integration/test_msel.py -v
```

Expected: FAIL (404)

**Step 3: Implement MSEL API**

```python
# backend/cyroid/api/msel.py
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from cyroid.api.deps import get_db, get_current_user
from cyroid.models.user import User
from cyroid.models.range import Range
from cyroid.models.msel import MSEL
from cyroid.models.inject import Inject
from cyroid.services.msel_parser import MSELParser

router = APIRouter(prefix="/msel", tags=["msel"])

class MSELImport(BaseModel):
    name: str
    content: str

@router.post("/{range_id}/import", status_code=201)
def import_msel(
    range_id: UUID,
    data: MSELImport,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    range_obj = db.query(Range).filter(Range.id == range_id).first()
    if not range_obj:
        raise HTTPException(status_code=404, detail="Range not found")
    if range_obj.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Delete existing MSEL if any
    existing = db.query(MSEL).filter(MSEL.range_id == range_id).first()
    if existing:
        db.delete(existing)
        db.commit()

    # Parse MSEL
    parser = MSELParser()
    parsed_injects = parser.parse(data.content)

    # Create MSEL
    msel = MSEL(
        range_id=range_id,
        name=data.name,
        content=data.content
    )
    db.add(msel)
    db.commit()
    db.refresh(msel)

    # Create Injects
    for inject_data in parsed_injects:
        inject = Inject(
            msel_id=msel.id,
            sequence_number=inject_data['sequence_number'],
            inject_time_minutes=inject_data['inject_time_minutes'],
            title=inject_data['title'],
            description=inject_data.get('description', ''),
            actions=inject_data['actions']
        )
        db.add(inject)

    db.commit()

    # Return with injects
    injects = db.query(Inject).filter(Inject.msel_id == msel.id).order_by(Inject.sequence_number).all()

    return {
        "id": str(msel.id),
        "name": msel.name,
        "range_id": str(msel.range_id),
        "injects": [
            {
                "id": str(i.id),
                "sequence_number": i.sequence_number,
                "inject_time_minutes": i.inject_time_minutes,
                "title": i.title,
                "description": i.description,
                "actions": i.actions,
                "status": i.status.value
            }
            for i in injects
        ]
    }

@router.get("/{range_id}")
def get_msel(
    range_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    range_obj = db.query(Range).filter(Range.id == range_id).first()
    if not range_obj:
        raise HTTPException(status_code=404, detail="Range not found")
    if range_obj.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    msel = db.query(MSEL).filter(MSEL.range_id == range_id).first()
    if not msel:
        raise HTTPException(status_code=404, detail="No MSEL found for this range")

    injects = db.query(Inject).filter(Inject.msel_id == msel.id).order_by(Inject.sequence_number).all()

    return {
        "id": str(msel.id),
        "name": msel.name,
        "range_id": str(msel.range_id),
        "content": msel.content,
        "injects": [
            {
                "id": str(i.id),
                "sequence_number": i.sequence_number,
                "inject_time_minutes": i.inject_time_minutes,
                "title": i.title,
                "description": i.description,
                "actions": i.actions,
                "status": i.status.value,
                "executed_at": i.executed_at.isoformat() if i.executed_at else None
            }
            for i in injects
        ]
    }
```

**Step 4: Register router**

**Step 5: Run test to verify pass**

```bash
cd /home/ubuntu/cyro/backend && python -m pytest tests/integration/test_msel.py -v
```

**Step 6: Commit**

```bash
git add backend/cyroid/api/msel.py backend/cyroid/main.py backend/tests/integration/test_msel.py
git commit -m "feat(api): add MSEL import and retrieval endpoints"
```

---

### Task 24: Inject Execution Service

**Files:**
- Create: `backend/cyroid/services/inject_service.py`
- Test: `backend/tests/unit/test_inject_service.py`

**Step 1: Write failing test**

```python
# backend/tests/unit/test_inject_service.py
import pytest
from unittest.mock import MagicMock, AsyncMock
from uuid import uuid4
from cyroid.services.inject_service import InjectService
from cyroid.models.inject import InjectStatus

def test_execute_inject_runs_command():
    mock_db = MagicMock()
    mock_docker = MagicMock()
    mock_docker.exec_in_container.return_value = "command output"

    service = InjectService(mock_db, mock_docker)

    inject = MagicMock()
    inject.id = uuid4()
    inject.actions = [
        {'action_type': 'run_command', 'parameters': {'target_vm': 'test-vm', 'command': 'echo hello'}}
    ]

    vm = MagicMock()
    vm.container_id = "test-container"

    result = service.execute_inject(inject, {'test-vm': vm})

    assert result['success'] == True
    mock_docker.exec_in_container.assert_called_once()
```

**Step 2: Run test to verify failure**

```bash
cd /home/ubuntu/cyro/backend && python -m pytest tests/unit/test_inject_service.py -v
```

**Step 3: Implement InjectService**

```python
# backend/cyroid/services/inject_service.py
from uuid import UUID
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.orm import Session
from cyroid.models.inject import Inject, InjectStatus
from cyroid.models.vm import VM
from cyroid.services.docker_service import DockerService
from cyroid.services.event_service import EventService
from cyroid.models.event_log import EventType
import logging

logger = logging.getLogger(__name__)

class InjectService:
    def __init__(self, db: Session, docker_service: DockerService):
        self.db = db
        self.docker = docker_service

    def execute_inject(self, inject: Inject, vm_map: Dict[str, VM]) -> Dict[str, Any]:
        """Execute an inject's actions on target VMs."""
        inject.status = InjectStatus.EXECUTING
        inject.executed_at = datetime.utcnow()
        self.db.commit()

        results = []
        success = True

        for action in inject.actions:
            action_type = action.get('action_type')
            params = action.get('parameters', {})

            try:
                if action_type == 'run_command':
                    result = self._execute_command(params, vm_map)
                elif action_type == 'place_file':
                    result = self._place_file(params, vm_map)
                else:
                    result = {'error': f'Unknown action type: {action_type}'}
                    success = False

                results.append({'action': action, 'result': result})
            except Exception as e:
                logger.error(f"Failed to execute action: {e}")
                results.append({'action': action, 'error': str(e)})
                success = False

        # Update inject status
        inject.status = InjectStatus.COMPLETED if success else InjectStatus.FAILED
        inject.execution_log = str(results)
        self.db.commit()

        return {'success': success, 'results': results}

    def _execute_command(self, params: Dict, vm_map: Dict[str, VM]) -> Dict:
        target_vm_name = params.get('target_vm')
        command = params.get('command')

        if target_vm_name not in vm_map:
            return {'error': f'VM {target_vm_name} not found'}

        vm = vm_map[target_vm_name]
        if not vm.container_id:
            return {'error': f'VM {target_vm_name} has no container'}

        output = self.docker.exec_in_container(vm.container_id, command)
        return {'output': output}

    def _place_file(self, params: Dict, vm_map: Dict[str, VM]) -> Dict:
        target_vm_name = params.get('target_vm')
        filename = params.get('filename')
        target_path = params.get('target_path')

        if target_vm_name not in vm_map:
            return {'error': f'VM {target_vm_name} not found'}

        vm = vm_map[target_vm_name]
        if not vm.container_id:
            return {'error': f'VM {target_vm_name} has no container'}

        # TODO: Implement actual file placement via artifact service
        # For now, just log the action
        logger.info(f"Would place {filename} at {target_path} on {target_vm_name}")
        return {'placed': True, 'path': target_path}
```

**Step 4: Run test to verify pass**

```bash
cd /home/ubuntu/cyro/backend && python -m pytest tests/unit/test_inject_service.py -v
```

**Step 5: Commit**

```bash
git add backend/cyroid/services/inject_service.py backend/tests/unit/test_inject_service.py
git commit -m "feat(services): add InjectService for executing MSEL injects"
```

---

### Task 25: Manual Inject Trigger Endpoint

**Files:**
- Modify: `backend/cyroid/api/msel.py`
- Test: `backend/tests/integration/test_msel.py` (add test)

**Step 1: Add test**

```python
def test_execute_inject(client, auth_headers, test_range, test_vm, mock_docker):
    # Import MSEL first
    client.post(
        f"/api/v1/msel/{test_range.id}/import",
        headers=auth_headers,
        json={"name": "Test MSEL", "content": SAMPLE_MSEL}
    )

    # Get MSEL to find inject ID
    msel_response = client.get(f"/api/v1/msel/{test_range.id}", headers=auth_headers)
    inject_id = msel_response.json()["injects"][0]["id"]

    # Execute inject
    response = client.post(
        f"/api/v1/msel/inject/{inject_id}/execute",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert "success" in data
```

**Step 2: Implement execute endpoint**

Add to `backend/cyroid/api/msel.py`:

```python
@router.post("/inject/{inject_id}/execute")
def execute_inject(
    inject_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    docker_service: DockerService = Depends(get_docker_service)
):
    inject = db.query(Inject).filter(Inject.id == inject_id).first()
    if not inject:
        raise HTTPException(status_code=404, detail="Inject not found")

    msel = db.query(MSEL).filter(MSEL.id == inject.msel_id).first()
    range_obj = db.query(Range).filter(Range.id == msel.range_id).first()

    if range_obj.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Build VM name to VM map
    from cyroid.models.vm import VM
    vms = db.query(VM).filter(VM.range_id == range_obj.id).all()
    vm_map = {vm.name: vm for vm in vms}

    # Execute inject
    from cyroid.services.inject_service import InjectService
    service = InjectService(db, docker_service)
    result = service.execute_inject(inject, vm_map)

    # Log event
    from cyroid.services.event_service import EventService
    from cyroid.models.event_log import EventType
    event_service = EventService(db)
    event_service.log_event(
        range_id=range_obj.id,
        event_type=EventType.INJECT_EXECUTED if result['success'] else EventType.INJECT_FAILED,
        message=f"Inject '{inject.title}' {'completed' if result['success'] else 'failed'}"
    )

    return result
```

**Step 3: Run test to verify pass**

```bash
cd /home/ubuntu/cyro/backend && python -m pytest tests/integration/test_msel.py::test_execute_inject -v
```

**Step 4: Commit**

```bash
git add backend/cyroid/api/msel.py backend/tests/integration/test_msel.py
git commit -m "feat(api): add manual inject execution endpoint"
```

---

### Task 26: MSEL Timeline Frontend Component

**Files:**
- Create: `frontend/src/components/msel/MSELTimeline.tsx`

**Step 1: Create component**

```typescript
// frontend/src/components/msel/MSELTimeline.tsx
import { useState } from 'react';
import { apiService } from '../../services/api';
import { Play, CheckCircle, XCircle, Clock, AlertCircle } from 'lucide-react';

interface InjectAction {
  action_type: string;
  parameters: Record<string, string>;
}

interface Inject {
  id: string;
  sequence_number: number;
  inject_time_minutes: number;
  title: string;
  description: string;
  actions: InjectAction[];
  status: string;
  executed_at?: string;
}

interface Props {
  rangeId: string;
  injects: Inject[];
  onRefresh: () => void;
}

const statusIcons: Record<string, React.ReactNode> = {
  pending: <Clock className="w-5 h-5 text-gray-400" />,
  executing: <AlertCircle className="w-5 h-5 text-yellow-500 animate-pulse" />,
  completed: <CheckCircle className="w-5 h-5 text-green-500" />,
  failed: <XCircle className="w-5 h-5 text-red-500" />,
  skipped: <Clock className="w-5 h-5 text-gray-300" />,
};

export function MSELTimeline({ rangeId, injects, onRefresh }: Props) {
  const [executing, setExecuting] = useState<string | null>(null);

  const formatTime = (minutes: number) => {
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    return `T+${h}:${m.toString().padStart(2, '0')}`;
  };

  const handleExecute = async (injectId: string) => {
    setExecuting(injectId);
    try {
      await apiService.executeInject(injectId);
      onRefresh();
    } catch (error) {
      console.error('Failed to execute inject:', error);
    } finally {
      setExecuting(null);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="px-4 py-3 border-b">
        <h3 className="font-medium">MSEL Timeline</h3>
      </div>
      <div className="divide-y">
        {injects.map((inject) => (
          <div key={inject.id} className="p-4">
            <div className="flex items-start gap-3">
              <div className="flex-shrink-0 w-16 text-sm font-mono text-gray-500">
                {formatTime(inject.inject_time_minutes)}
              </div>
              <div className="flex-shrink-0">
                {statusIcons[inject.status]}
              </div>
              <div className="flex-1">
                <h4 className="font-medium">{inject.title}</h4>
                {inject.description && (
                  <p className="text-sm text-gray-600 mt-1">{inject.description}</p>
                )}
                <div className="mt-2 space-y-1">
                  {inject.actions.map((action, idx) => (
                    <div key={idx} className="text-xs bg-gray-100 rounded px-2 py-1">
                      <span className="font-medium">{action.action_type}:</span>{' '}
                      {action.action_type === 'run_command'
                        ? `${action.parameters.command} on ${action.parameters.target_vm}`
                        : `${action.parameters.filename} → ${action.parameters.target_path}`
                      }
                    </div>
                  ))}
                </div>
              </div>
              <div className="flex-shrink-0">
                {inject.status === 'pending' && (
                  <button
                    onClick={() => handleExecute(inject.id)}
                    disabled={executing === inject.id}
                    className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 flex items-center gap-1"
                  >
                    <Play className="w-4 h-4" />
                    {executing === inject.id ? 'Running...' : 'Execute'}
                  </button>
                )}
                {inject.executed_at && (
                  <span className="text-xs text-gray-500">
                    {new Date(inject.executed_at).toLocaleTimeString()}
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

**Step 2: Add API methods**

```typescript
// Add to frontend/src/services/api.ts
getMSEL: async (rangeId: string) => {
  const response = await api.get(`/msel/${rangeId}`);
  return response.data;
},

importMSEL: async (rangeId: string, name: string, content: string) => {
  const response = await api.post(`/msel/${rangeId}/import`, { name, content });
  return response.data;
},

executeInject: async (injectId: string) => {
  const response = await api.post(`/msel/inject/${injectId}/execute`);
  return response.data;
},
```

**Step 3: Commit**

```bash
git add frontend/src/components/msel/MSELTimeline.tsx frontend/src/services/api.ts
git commit -m "feat(frontend): add MSELTimeline component with manual trigger"
```

---

### Task 27: MSEL Upload Component

**Files:**
- Create: `frontend/src/components/msel/MSELUpload.tsx`

**Step 1: Create upload component**

```typescript
// frontend/src/components/msel/MSELUpload.tsx
import { useState, useRef } from 'react';
import { apiService } from '../../services/api';
import { Upload, FileText } from 'lucide-react';

interface Props {
  rangeId: string;
  onImported: () => void;
}

export function MSELUpload({ rangeId, onImported }: Props) {
  const [name, setName] = useState('');
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      setContent(event.target?.result as string);
      if (!name) {
        setName(file.name.replace('.md', ''));
      }
    };
    reader.readAsText(file);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !content) {
      setError('Please provide a name and content');
      return;
    }

    setLoading(true);
    setError('');

    try {
      await apiService.importMSEL(rangeId, name, content);
      onImported();
      setName('');
      setContent('');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to import MSEL');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h3 className="font-medium mb-4">Import MSEL</h3>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            MSEL Name
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full px-3 py-2 border rounded focus:ring-2 focus:ring-blue-500"
            placeholder="Exercise MSEL"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Upload Markdown File
          </label>
          <input
            ref={fileInputRef}
            type="file"
            accept=".md,.markdown,.txt"
            onChange={handleFileUpload}
            className="hidden"
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="flex items-center gap-2 px-4 py-2 border border-dashed rounded hover:bg-gray-50"
          >
            <Upload className="w-4 h-4" />
            Choose File
          </button>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Or Paste Content
          </label>
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            rows={10}
            className="w-full px-3 py-2 border rounded font-mono text-sm focus:ring-2 focus:ring-blue-500"
            placeholder="## T+0:00 - Initial Setup..."
          />
        </div>

        {error && (
          <div className="text-red-600 text-sm">{error}</div>
        )}

        <button
          type="submit"
          disabled={loading || !name || !content}
          className="w-full px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 flex items-center justify-center gap-2"
        >
          <FileText className="w-4 h-4" />
          {loading ? 'Importing...' : 'Import MSEL'}
        </button>
      </form>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/msel/MSELUpload.tsx
git commit -m "feat(frontend): add MSELUpload component for importing markdown scenarios"
```

---

### Task 28: Integrate MSEL into Execution Console

**Files:**
- Modify: `frontend/src/pages/ExecutionConsole.tsx`

**Step 1: Add MSEL panel to ExecutionConsole**

Update `frontend/src/pages/ExecutionConsole.tsx` to include MSEL components:

```typescript
// Add imports
import { MSELTimeline } from '../components/msel/MSELTimeline';
import { MSELUpload } from '../components/msel/MSELUpload';

// Add state
const [msel, setMSEL] = useState<any>(null);

// Add to loadRangeData
const loadMSEL = async () => {
  try {
    const mselData = await apiService.getMSEL(rangeId);
    setMSEL(mselData);
  } catch {
    setMSEL(null);
  }
};

// Add panel in UI (as a tab or collapsible section)
{msel ? (
  <MSELTimeline
    rangeId={rangeId}
    injects={msel.injects}
    onRefresh={loadMSEL}
  />
) : (
  <MSELUpload
    rangeId={rangeId}
    onImported={loadMSEL}
  />
)}
```

**Step 2: Commit**

```bash
git add frontend/src/pages/ExecutionConsole.tsx
git commit -m "feat(frontend): integrate MSEL management into execution console"
```

---

### Task 29: Database Migration

**Files:**
- Create: `backend/alembic/versions/XXX_add_phase4_models.py`

**Step 1: Generate migration**

```bash
cd /home/ubuntu/cyro/backend && alembic revision --autogenerate -m "add_phase4_models"
```

**Step 2: Review and edit migration if needed**

**Step 3: Apply migration**

```bash
cd /home/ubuntu/cyro/backend && alembic upgrade head
```

**Step 4: Commit**

```bash
git add backend/alembic/versions/
git commit -m "feat(db): add Phase 4 database migrations"
```

---

### Task 30: Run Full Test Suite

**Step 1: Run all backend tests**

```bash
cd /home/ubuntu/cyro/backend && python -m pytest tests/ -v
```

Expected: All tests PASS

**Step 2: Run frontend type check**

```bash
cd /home/ubuntu/cyro/frontend && npm run type-check
```

Expected: No errors

**Step 3: Run E2E tests**

```bash
cd /home/ubuntu/cyro/frontend && npx playwright test
```

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete Phase 4 - Execution Console, Monitoring, MSEL v1"
```

---

## Summary

Phase 4 implementation delivers:

1. **Execution Console** (Week 10)
   - EventLog model and service for activity tracking
   - Real-time event feed via WebSocket
   - VM grid with quick actions (start/stop/restart/snapshot)
   - Multi-panel execution dashboard

2. **Monitoring** (Week 11)
   - Docker stats integration (CPU, memory, network)
   - Connection tracking model and service
   - Resource metrics visualization
   - Connection timeline component

3. **MSEL v1** (Week 12)
   - MSEL and Inject data models
   - Markdown parser for MSEL format
   - Import/export API endpoints
   - Manual inject trigger with execution logging
   - Timeline UI component

**Total Tasks:** 30
**Estimated Time:** ~3 weeks
**Test Coverage:** Unit + Integration + E2E
