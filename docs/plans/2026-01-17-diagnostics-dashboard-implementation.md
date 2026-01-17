# Diagnostics Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a Diagnostics tab to RangeDetail showing component health, error timeline, and container logs.

**Architecture:** Backend adds `error_message` fields to VM/Range models and a logs endpoint. Frontend adds a tabbed interface with DiagnosticsTab containing ComponentHealth, ErrorTimeline, and LogViewer components.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, React, TypeScript, Tailwind CSS

---

## Task 1: Add error_message to VM and Range Models

**Files:**
- Modify: `backend/cyroid/models/vm.py:34` (after status field)
- Modify: `backend/cyroid/models/range.py:25` (after status field)

**Step 1: Add error_message field to VM model**

In `backend/cyroid/models/vm.py`, add after line 34 (status field):

```python
    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
```

**Step 2: Add error_message field to Range model**

In `backend/cyroid/models/range.py`, add after line 25 (status field):

```python
    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
```

**Step 3: Create database migration**

Run:
```bash
cd /Users/JonWFH/jondev/CYROID && docker-compose exec api alembic revision --autogenerate -m "Add error_message to VM and Range"
```

**Step 4: Apply migration**

Run:
```bash
docker-compose exec api alembic upgrade head
```

**Step 5: Commit**

```bash
git add backend/cyroid/models/vm.py backend/cyroid/models/range.py backend/alembic/versions/
git commit -m "feat(models): add error_message field to VM and Range models"
```

---

## Task 2: Add get_container_logs to DockerService

**Files:**
- Modify: `backend/cyroid/services/docker_service.py`

**Step 1: Add get_container_logs method**

Add after the `get_network` method (around line 131):

```python
    def get_container_logs(self, container_id: str, tail: int = 100) -> list[str]:
        """
        Get last N lines of container logs.

        Args:
            container_id: Docker container ID
            tail: Number of lines to retrieve

        Returns:
            List of log lines with timestamps
        """
        try:
            container = self.client.containers.get(container_id)
            logs = container.logs(tail=tail, timestamps=True).decode('utf-8')
            return logs.strip().split('\n') if logs.strip() else []
        except NotFound:
            return ["Container not found - it may have been removed"]
        except APIError as e:
            return [f"Error fetching logs: {e}"]
```

**Step 2: Verify it works manually**

Run Python in the container:
```bash
docker-compose exec api python -c "
from cyroid.services.docker_service import DockerService
docker = DockerService()
# Test with any running container
containers = docker.client.containers.list()
if containers:
    logs = docker.get_container_logs(containers[0].id, tail=5)
    print(logs)
else:
    print('No containers running')
"
```

**Step 3: Commit**

```bash
git add backend/cyroid/services/docker_service.py
git commit -m "feat(docker): add get_container_logs method"
```

---

## Task 3: Add VM Logs API Endpoint

**Files:**
- Modify: `backend/cyroid/api/vms.py`

**Step 1: Add the logs endpoint**

Add after the restart endpoint (around line 1030):

```python
@router.get("/{vm_id}/logs")
def get_vm_logs(
    vm_id: UUID,
    tail: int = Query(100, ge=10, le=1000, description="Number of log lines to retrieve"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Fetch container logs for a VM.

    Returns the last N lines of the container's stdout/stderr with timestamps.
    For QEMU/Windows VMs, this shows hypervisor output, not guest OS logs.
    """
    vm = db.query(VM).filter(VM.id == vm_id).first()
    if not vm:
        raise HTTPException(status_code=404, detail="VM not found")

    range_obj = db.query(Range).filter(Range.id == vm.range_id).first()
    if not range_obj:
        raise HTTPException(status_code=404, detail="Range not found")
    if range_obj.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if not vm.container_id:
        raise HTTPException(status_code=404, detail="VM has no container - it may not be deployed yet")

    docker = get_docker_service()
    lines = docker.get_container_logs(vm.container_id, tail=tail)

    return {
        "vm_id": str(vm_id),
        "hostname": vm.hostname,
        "container_id": vm.container_id[:12],
        "tail": tail,
        "lines": lines,
        "note": "For QEMU/Windows VMs, these are hypervisor logs. Use the console for guest OS access."
    }
```

**Step 2: Test the endpoint**

Run:
```bash
# Get a VM ID from a deployed range, then:
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/vms/{vm_id}/logs?tail=20
```

**Step 3: Commit**

```bash
git add backend/cyroid/api/vms.py
git commit -m "feat(api): add GET /vms/{id}/logs endpoint for container logs"
```

---

## Task 4: Update Error Handlers to Populate error_message

**Files:**
- Modify: `backend/cyroid/api/vms.py` (start_vm, restart_vm error handlers)
- Modify: `backend/cyroid/api/ranges.py` (deploy error handlers)

**Step 1: Update start_vm error handler**

In `backend/cyroid/api/vms.py`, find the start_vm error handler (around line 569-580) and update:

```python
    except Exception as e:
        logger.error(f"Failed to start VM {vm_id}: {e}")
        vm.status = VMStatus.ERROR
        vm.error_message = str(e)[:1000]  # Add this line
        db.commit()

        # Log error event
        event_service.log_event(
            range_id=vm.range_id,
            vm_id=vm.id,
            event_type=EventType.VM_ERROR,
            message=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start VM: {str(e)}"
        )
```

**Step 2: Update restart_vm error handler**

In `backend/cyroid/api/vms.py`, find the restart_vm error handler (around line 1015-1030) and update similarly:

```python
    except Exception as e:
        logger.error(f"Failed to restart VM {vm_id}: {e}")
        vm.status = VMStatus.ERROR
        vm.error_message = str(e)[:1000]  # Add this line
        db.commit()

        # Log error event
        event_service.log_event(
            range_id=vm.range_id,
            vm_id=vm.id,
            event_type=EventType.VM_ERROR,
            message=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restart VM: {str(e)}"
        )
```

**Step 3: Update deploy error handler in ranges.py**

In `backend/cyroid/api/ranges.py`, find the deploy error handler (around line 600-610) and update:

```python
    except Exception as e:
        logger.error(f"Deployment failed for range {range_id}: {e}")
        range_obj.status = RangeStatus.ERROR
        range_obj.error_message = str(e)[:1000]  # Add this line
        db.commit()
        event_service.log_event(
            range_id=range_id,
            event_type=EventType.DEPLOYMENT_FAILED,
            message=f"Deployment failed: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Deployment failed: {str(e)}"
        )
```

**Step 4: Commit**

```bash
git add backend/cyroid/api/vms.py backend/cyroid/api/ranges.py
git commit -m "feat(api): populate error_message on VM and Range failures"
```

---

## Task 5: Update Pydantic Schemas and TypeScript Types

**Files:**
- Modify: `backend/cyroid/schemas/vm.py`
- Modify: `backend/cyroid/schemas/range.py`
- Modify: `frontend/src/types/index.ts`

**Step 1: Update VM schema**

In `backend/cyroid/schemas/vm.py`, add to VMResponse class:

```python
    error_message: Optional[str] = None
```

**Step 2: Update Range schema**

In `backend/cyroid/schemas/range.py`, add to RangeResponse/RangeDetail class:

```python
    error_message: Optional[str] = None
```

**Step 3: Update TypeScript VM type**

In `frontend/src/types/index.ts`, add to VM interface (after status field, around line 89):

```typescript
  error_message: string | null
```

**Step 4: Update TypeScript Range type**

In `frontend/src/types/index.ts`, add to Range interface (after status field, around line 40):

```typescript
  error_message: string | null
```

**Step 5: Add VMLogsResponse type**

In `frontend/src/types/index.ts`, add at the end:

```typescript
export interface VMLogsResponse {
  vm_id: string
  hostname: string
  container_id: string
  tail: number
  lines: string[]
  note: string
}
```

**Step 6: Commit**

```bash
git add backend/cyroid/schemas/ frontend/src/types/index.ts
git commit -m "feat(schemas): add error_message to VM and Range schemas"
```

---

## Task 6: Add API Client Method for Logs

**Files:**
- Modify: `frontend/src/services/api.ts`

**Step 1: Add getVmLogs method to vmsApi**

In `frontend/src/services/api.ts`, add to the vmsApi object:

```typescript
  getVmLogs: async (vmId: string, tail: number = 100) => {
    const response = await api.get<VMLogsResponse>(`/vms/${vmId}/logs`, {
      params: { tail }
    })
    return response.data
  },
```

**Step 2: Import VMLogsResponse**

Add to the imports at the top of `frontend/src/services/api.ts`:

```typescript
import type { ..., VMLogsResponse } from '../types'
```

**Step 3: Commit**

```bash
git add frontend/src/services/api.ts
git commit -m "feat(api): add getVmLogs client method"
```

---

## Task 7: Create LogViewer Component

**Files:**
- Create: `frontend/src/components/diagnostics/LogViewer.tsx`

**Step 1: Create the diagnostics directory**

```bash
mkdir -p frontend/src/components/diagnostics
```

**Step 2: Create LogViewer.tsx**

```typescript
// frontend/src/components/diagnostics/LogViewer.tsx
import { useState, useEffect, useRef } from 'react'
import { X, RefreshCw, Copy, Check, AlertCircle } from 'lucide-react'
import { vmsApi } from '../../services/api'
import type { VMLogsResponse } from '../../types'
import clsx from 'clsx'

interface LogViewerProps {
  vmId: string
  vmHostname: string
  onClose: () => void
}

export function LogViewer({ vmId, vmHostname, onClose }: LogViewerProps) {
  const [logs, setLogs] = useState<VMLogsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const logContainerRef = useRef<HTMLPreElement>(null)

  const fetchLogs = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await vmsApi.getVmLogs(vmId, 100)
      setLogs(data)
      // Auto-scroll to bottom
      setTimeout(() => {
        if (logContainerRef.current) {
          logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight
        }
      }, 100)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch logs')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchLogs()
  }, [vmId])

  const handleCopy = async () => {
    if (logs?.lines) {
      await navigator.clipboard.writeText(logs.lines.join('\n'))
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <div className="border border-gray-200 rounded-lg bg-gray-900 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-800 border-b border-gray-700">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-gray-200">
            Logs: {vmHostname}
          </span>
          {logs?.container_id && (
            <span className="text-xs text-gray-500">
              ({logs.container_id})
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={fetchLogs}
            disabled={loading}
            className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded disabled:opacity-50"
            title="Refresh"
          >
            <RefreshCw className={clsx("w-4 h-4", loading && "animate-spin")} />
          </button>
          <button
            onClick={handleCopy}
            disabled={!logs?.lines?.length}
            className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded disabled:opacity-50"
            title="Copy to clipboard"
          >
            {copied ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
          </button>
          <button
            onClick={onClose}
            className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded"
            title="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Log content */}
      <div className="relative">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-900/80 z-10">
            <RefreshCw className="w-6 h-6 text-gray-400 animate-spin" />
          </div>
        )}

        {error && (
          <div className="p-4 flex items-center gap-2 text-red-400">
            <AlertCircle className="w-4 h-4" />
            <span className="text-sm">{error}</span>
          </div>
        )}

        <pre
          ref={logContainerRef}
          className="p-4 text-xs font-mono text-gray-300 overflow-auto max-h-64 whitespace-pre-wrap"
        >
          {logs?.lines?.length ? (
            logs.lines.map((line, i) => (
              <div key={i} className="hover:bg-gray-800">
                {line}
              </div>
            ))
          ) : !loading && !error ? (
            <span className="text-gray-500">No logs available</span>
          ) : null}
        </pre>

        {/* Note about QEMU/Windows VMs */}
        {logs?.note && (
          <div className="px-4 py-2 bg-gray-800/50 border-t border-gray-700 text-xs text-gray-500">
            {logs.note}
          </div>
        )}
      </div>
    </div>
  )
}
```

**Step 3: Commit**

```bash
git add frontend/src/components/diagnostics/LogViewer.tsx
git commit -m "feat(ui): add LogViewer component for container logs"
```

---

## Task 8: Create ComponentHealth Component

**Files:**
- Create: `frontend/src/components/diagnostics/ComponentHealth.tsx`

**Step 1: Create ComponentHealth.tsx**

```typescript
// frontend/src/components/diagnostics/ComponentHealth.tsx
import { useState } from 'react'
import { ChevronDown, ChevronRight, Server, Network as NetworkIcon, Router, Box, AlertCircle, CheckCircle, Clock, XCircle } from 'lucide-react'
import type { Range, Network, VM, RangeRouter } from '../../types'
import clsx from 'clsx'

interface ComponentHealthProps {
  range: Range
  networks: Network[]
  vms: VM[]
  onSelectVm: (vm: VM) => void
  selectedVmId: string | null
}

type HealthStatus = 'healthy' | 'warning' | 'error' | 'pending'

function getStatusIcon(status: string): { icon: typeof CheckCircle; color: string; health: HealthStatus } {
  switch (status) {
    case 'running':
      return { icon: CheckCircle, color: 'text-green-500', health: 'healthy' }
    case 'stopped':
      return { icon: Clock, color: 'text-gray-400', health: 'pending' }
    case 'error':
      return { icon: XCircle, color: 'text-red-500', health: 'error' }
    case 'creating':
    case 'deploying':
    case 'pending':
      return { icon: Clock, color: 'text-yellow-500', health: 'warning' }
    default:
      return { icon: AlertCircle, color: 'text-gray-400', health: 'pending' }
  }
}

function StatusBadge({ status }: { status: string }) {
  const { icon: Icon, color } = getStatusIcon(status)
  return (
    <div className="flex items-center gap-1.5">
      <Icon className={clsx("w-4 h-4", color)} />
      <span className="text-sm text-gray-600">{status}</span>
    </div>
  )
}

export function ComponentHealth({ range, networks, vms, onSelectVm, selectedVmId }: ComponentHealthProps) {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['range', 'networks', 'vms']))

  const toggleSection = (section: string) => {
    setExpandedSections(prev => {
      const next = new Set(prev)
      if (next.has(section)) {
        next.delete(section)
      } else {
        next.add(section)
      }
      return next
    })
  }

  const errorVms = vms.filter(vm => vm.status === 'error')
  const errorCount = errorVms.length + (range.status === 'error' ? 1 : 0) + (range.router?.status === 'error' ? 1 : 0)

  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
      <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-900">Component Health</h3>
        {errorCount > 0 && (
          <span className="px-2 py-0.5 text-xs font-medium bg-red-100 text-red-800 rounded-full">
            {errorCount} error{errorCount > 1 ? 's' : ''}
          </span>
        )}
      </div>

      <div className="divide-y divide-gray-100">
        {/* Range Status */}
        <div className="px-4 py-2">
          <button
            onClick={() => toggleSection('range')}
            className="flex items-center gap-2 w-full text-left"
          >
            {expandedSections.has('range') ? (
              <ChevronDown className="w-4 h-4 text-gray-400" />
            ) : (
              <ChevronRight className="w-4 h-4 text-gray-400" />
            )}
            <Box className="w-4 h-4 text-primary-500" />
            <span className="text-sm font-medium text-gray-700">Range</span>
            <StatusBadge status={range.status} />
          </button>
          {expandedSections.has('range') && range.error_message && (
            <div className="ml-10 mt-1 text-xs text-red-600 bg-red-50 px-2 py-1 rounded">
              {range.error_message}
            </div>
          )}
        </div>

        {/* Router Status */}
        {range.router && (
          <div className="px-4 py-2">
            <div className="flex items-center gap-2 ml-6">
              <Router className="w-4 h-4 text-blue-500" />
              <span className="text-sm text-gray-700">VyOS Router</span>
              <StatusBadge status={range.router.status} />
            </div>
            {range.router.error_message && (
              <div className="ml-10 mt-1 text-xs text-red-600 bg-red-50 px-2 py-1 rounded">
                {range.router.error_message}
              </div>
            )}
          </div>
        )}

        {/* Networks */}
        <div className="px-4 py-2">
          <button
            onClick={() => toggleSection('networks')}
            className="flex items-center gap-2 w-full text-left"
          >
            {expandedSections.has('networks') ? (
              <ChevronDown className="w-4 h-4 text-gray-400" />
            ) : (
              <ChevronRight className="w-4 h-4 text-gray-400" />
            )}
            <NetworkIcon className="w-4 h-4 text-green-500" />
            <span className="text-sm font-medium text-gray-700">Networks</span>
            <span className="text-xs text-gray-400">({networks.length})</span>
          </button>
          {expandedSections.has('networks') && (
            <div className="ml-10 mt-1 space-y-1">
              {networks.map(network => (
                <div key={network.id} className="flex items-center gap-2 text-sm text-gray-600">
                  <CheckCircle className="w-3 h-3 text-green-500" />
                  <span>{network.name}</span>
                  <span className="text-xs text-gray-400">({network.subnet})</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* VMs */}
        <div className="px-4 py-2">
          <button
            onClick={() => toggleSection('vms')}
            className="flex items-center gap-2 w-full text-left"
          >
            {expandedSections.has('vms') ? (
              <ChevronDown className="w-4 h-4 text-gray-400" />
            ) : (
              <ChevronRight className="w-4 h-4 text-gray-400" />
            )}
            <Server className="w-4 h-4 text-purple-500" />
            <span className="text-sm font-medium text-gray-700">VMs</span>
            <span className="text-xs text-gray-400">({vms.length})</span>
            {errorVms.length > 0 && (
              <span className="px-1.5 py-0.5 text-xs bg-red-100 text-red-700 rounded">
                {errorVms.length} error
              </span>
            )}
          </button>
          {expandedSections.has('vms') && (
            <div className="ml-10 mt-1 space-y-1">
              {vms.map(vm => (
                <button
                  key={vm.id}
                  onClick={() => onSelectVm(vm)}
                  className={clsx(
                    "flex items-center gap-2 text-sm w-full text-left px-2 py-1 rounded",
                    selectedVmId === vm.id ? "bg-primary-50" : "hover:bg-gray-50"
                  )}
                >
                  <StatusBadge status={vm.status} />
                  <span className={clsx(
                    "font-medium",
                    vm.status === 'error' ? 'text-red-700' : 'text-gray-700'
                  )}>
                    {vm.hostname}
                  </span>
                  <span className="text-xs text-gray-400">({vm.ip_address})</span>
                </button>
              ))}
              {vms.length === 0 && (
                <span className="text-xs text-gray-400">No VMs configured</span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/diagnostics/ComponentHealth.tsx
git commit -m "feat(ui): add ComponentHealth component for status tree"
```

---

## Task 9: Create ErrorTimeline Component

**Files:**
- Create: `frontend/src/components/diagnostics/ErrorTimeline.tsx`

**Step 1: Create ErrorTimeline.tsx**

```typescript
// frontend/src/components/diagnostics/ErrorTimeline.tsx
import { useState, useEffect } from 'react'
import { AlertTriangle, RefreshCw, FileText, Clock } from 'lucide-react'
import { eventsApi } from '../../services/api'
import type { EventLog, VM } from '../../types'
import clsx from 'clsx'

interface ErrorTimelineProps {
  rangeId: string
  vms: VM[]
  onViewLogs: (vm: VM) => void
}

const ERROR_EVENT_TYPES = ['vm_error', 'deployment_failed', 'inject_failed']

export function ErrorTimeline({ rangeId, vms, onViewLogs }: ErrorTimelineProps) {
  const [events, setEvents] = useState<EventLog[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<string>('all')

  const fetchEvents = async () => {
    setLoading(true)
    try {
      const data = await eventsApi.getRangeEvents(rangeId, 50, 0, ERROR_EVENT_TYPES)
      setEvents(data.events)
    } catch (err) {
      console.error('Failed to fetch events:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchEvents()
  }, [rangeId])

  const filteredEvents = filter === 'all'
    ? events
    : events.filter(e => e.event_type === filter)

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp)
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  }

  const getVmForEvent = (event: EventLog): VM | undefined => {
    if (event.vm_id) {
      return vms.find(vm => vm.id === event.vm_id)
    }
    return undefined
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
      <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-900">Error Timeline</h3>
        <div className="flex items-center gap-2">
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="text-xs border border-gray-300 rounded px-2 py-1"
          >
            <option value="all">All Errors</option>
            <option value="vm_error">VM Errors</option>
            <option value="deployment_failed">Deployment</option>
            <option value="inject_failed">Inject Failed</option>
          </select>
          <button
            onClick={fetchEvents}
            disabled={loading}
            className="p-1 text-gray-400 hover:text-gray-600 disabled:opacity-50"
            title="Refresh"
          >
            <RefreshCw className={clsx("w-4 h-4", loading && "animate-spin")} />
          </button>
        </div>
      </div>

      <div className="max-h-80 overflow-y-auto">
        {loading && events.length === 0 ? (
          <div className="p-4 text-center text-gray-500">
            <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2" />
            Loading events...
          </div>
        ) : filteredEvents.length === 0 ? (
          <div className="p-4 text-center text-gray-500">
            <AlertTriangle className="w-5 h-5 mx-auto mb-2 text-gray-400" />
            No error events found
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {filteredEvents.map(event => {
              const vm = getVmForEvent(event)
              return (
                <div key={event.id} className="px-4 py-3 hover:bg-gray-50">
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 mt-0.5">
                      <AlertTriangle className="w-4 h-4 text-red-500" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 text-xs text-gray-500 mb-1">
                        <Clock className="w-3 h-3" />
                        <span>{formatTime(event.created_at)}</span>
                        <span className="px-1.5 py-0.5 bg-red-100 text-red-700 rounded">
                          {event.event_type.replace('_', ' ')}
                        </span>
                      </div>
                      <p className="text-sm text-gray-700 break-words">
                        {event.message}
                      </p>
                      {vm && (
                        <button
                          onClick={() => onViewLogs(vm)}
                          className="mt-2 inline-flex items-center gap-1 text-xs text-primary-600 hover:text-primary-700"
                        >
                          <FileText className="w-3 h-3" />
                          View Logs ({vm.hostname})
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
```

**Step 2: Add eventsApi.getRangeEvents to api.ts if not exists**

Check `frontend/src/services/api.ts` for eventsApi. If it doesn't have `getRangeEvents`, add:

```typescript
export const eventsApi = {
  getRangeEvents: async (rangeId: string, limit = 100, offset = 0, eventTypes?: string[]) => {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
    if (eventTypes?.length) {
      eventTypes.forEach(type => params.append('event_types', type))
    }
    const response = await api.get<EventLogList>(`/events/${rangeId}?${params}`)
    return response.data
  },
}
```

**Step 3: Commit**

```bash
git add frontend/src/components/diagnostics/ErrorTimeline.tsx frontend/src/services/api.ts
git commit -m "feat(ui): add ErrorTimeline component for error history"
```

---

## Task 10: Create DiagnosticsTab Component

**Files:**
- Create: `frontend/src/components/diagnostics/DiagnosticsTab.tsx`
- Create: `frontend/src/components/diagnostics/index.ts`

**Step 1: Create DiagnosticsTab.tsx**

```typescript
// frontend/src/components/diagnostics/DiagnosticsTab.tsx
import { useState } from 'react'
import type { Range, Network, VM } from '../../types'
import { ComponentHealth } from './ComponentHealth'
import { ErrorTimeline } from './ErrorTimeline'
import { LogViewer } from './LogViewer'

interface DiagnosticsTabProps {
  range: Range
  networks: Network[]
  vms: VM[]
}

export function DiagnosticsTab({ range, networks, vms }: DiagnosticsTabProps) {
  const [selectedVm, setSelectedVm] = useState<VM | null>(null)

  const handleSelectVm = (vm: VM) => {
    // Toggle selection if clicking the same VM
    if (selectedVm?.id === vm.id) {
      setSelectedVm(null)
    } else {
      setSelectedVm(vm)
    }
  }

  const handleViewLogs = (vm: VM) => {
    setSelectedVm(vm)
  }

  return (
    <div className="space-y-4">
      {/* Two-column layout for health and timeline */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ComponentHealth
          range={range}
          networks={networks}
          vms={vms}
          onSelectVm={handleSelectVm}
          selectedVmId={selectedVm?.id ?? null}
        />
        <ErrorTimeline
          rangeId={range.id}
          vms={vms}
          onViewLogs={handleViewLogs}
        />
      </div>

      {/* Log viewer - shown when VM is selected */}
      {selectedVm && (
        <LogViewer
          vmId={selectedVm.id}
          vmHostname={selectedVm.hostname}
          onClose={() => setSelectedVm(null)}
        />
      )}
    </div>
  )
}
```

**Step 2: Create index.ts barrel export**

```typescript
// frontend/src/components/diagnostics/index.ts
export { DiagnosticsTab } from './DiagnosticsTab'
export { ComponentHealth } from './ComponentHealth'
export { ErrorTimeline } from './ErrorTimeline'
export { LogViewer } from './LogViewer'
```

**Step 3: Commit**

```bash
git add frontend/src/components/diagnostics/
git commit -m "feat(ui): add DiagnosticsTab container component"
```

---

## Task 11: Add Tabs to RangeDetail Page

**Files:**
- Modify: `frontend/src/pages/RangeDetail.tsx`

**Step 1: Add imports**

Add at the top of RangeDetail.tsx:

```typescript
import { DiagnosticsTab } from '../components/diagnostics'
import { Wrench } from 'lucide-react'  // Add Wrench to existing lucide imports
```

**Step 2: Add tab state**

Add after other useState declarations (around line 40):

```typescript
  // Tab state
  const [activeTab, setActiveTab] = useState<'builder' | 'diagnostics'>('builder')
```

**Step 3: Calculate error count for badge**

Add after the loading check (where range data is available):

```typescript
  // Calculate error count for diagnostics badge
  const errorCount = useMemo(() => {
    if (!range) return 0
    let count = 0
    if (range.status === 'error') count++
    if (range.router?.status === 'error') count++
    count += vms.filter(vm => vm.status === 'error').length
    return count
  }, [range, vms])
```

**Step 4: Add tab navigation UI**

Add after the header section (before the networks/VMs grid), around where the DeploymentProgress component is:

```typescript
      {/* Tab Navigation */}
      <div className="mb-6 border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('builder')}
            className={clsx(
              "py-2 px-1 border-b-2 font-medium text-sm",
              activeTab === 'builder'
                ? "border-primary-500 text-primary-600"
                : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
            )}
          >
            Builder
          </button>
          <button
            onClick={() => setActiveTab('diagnostics')}
            className={clsx(
              "py-2 px-1 border-b-2 font-medium text-sm flex items-center gap-2",
              activeTab === 'diagnostics'
                ? "border-primary-500 text-primary-600"
                : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
            )}
          >
            <Wrench className="w-4 h-4" />
            Diagnostics
            {errorCount > 0 && (
              <span className="px-1.5 py-0.5 text-xs font-medium bg-red-100 text-red-700 rounded-full">
                {errorCount}
              </span>
            )}
          </button>
        </nav>
      </div>
```

**Step 5: Wrap existing content in Builder tab conditional**

Wrap the existing networks/VMs grid in a conditional:

```typescript
      {activeTab === 'builder' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* ... existing networks and VMs sections ... */}
        </div>
      )}

      {activeTab === 'diagnostics' && range && (
        <DiagnosticsTab
          range={range}
          networks={networks}
          vms={vms}
        />
      )}
```

**Step 6: Commit**

```bash
git add frontend/src/pages/RangeDetail.tsx
git commit -m "feat(ui): add Diagnostics tab to RangeDetail page"
```

---

## Task 12: Final Integration and Testing

**Step 1: Run the full stack**

```bash
cd /Users/JonWFH/jondev/CYROID
docker-compose up -d
```

**Step 2: Test the flow**

1. Navigate to a range in the UI
2. Click the "Diagnostics" tab
3. Verify ComponentHealth shows range/router/networks/VMs
4. Verify ErrorTimeline loads (may be empty if no errors)
5. Click a VM to view logs
6. Verify logs load in LogViewer

**Step 3: Test error capture**

1. Create a VM with an invalid configuration (if possible)
2. Try to start it
3. Verify error appears in ErrorTimeline
4. Verify VM shows error_message in ComponentHealth

**Step 4: Run linting**

```bash
cd frontend && npm run lint
cd ../backend && ruff check .
```

**Step 5: Final commit**

```bash
git add -A
git commit -m "feat: complete diagnostics dashboard implementation (#4)"
```

**Step 6: Update version and tag**

Update `backend/cyroid/config.py`:
```python
app_version: str = "0.4.9"
```

Update CHANGELOG.md with the new version entry.

```bash
git add backend/cyroid/config.py CHANGELOG.md
git commit -m "chore: bump version to 0.4.9"
git tag v0.4.9
git push origin master --tags
```

**Step 7: Create GitHub release**

```bash
gh release create v0.4.9 --title "v0.4.9 - Diagnostics Dashboard" --notes "$(cat <<'EOF'
## Added

- **Diagnostics Dashboard** ([#4](../../issues/4)): New Diagnostics tab in RangeDetail showing:
  - Component Health tree with status indicators for range, router, networks, and VMs
  - Error Timeline with chronological error events and filtering
  - Container Log Viewer with refresh, copy, and auto-scroll
  - Error count badge on tab when issues exist

## Changed

- Added `error_message` field to VM and Range models for better error tracking
- Error handlers now capture and store error messages for display

## API

- New endpoint: `GET /api/v1/vms/{id}/logs?tail=100` - Fetch container logs
EOF
)"
```

**Step 8: Close the issue**

```bash
gh issue close 4 --comment "Implemented in v0.4.9. The Diagnostics Dashboard provides component health overview, error timeline, and container log viewing."
```

---

## Summary

This plan implements the Diagnostics Dashboard in 12 tasks:

1. **Models**: Add error_message to VM and Range
2. **Docker**: Add get_container_logs method
3. **API**: Add /vms/{id}/logs endpoint
4. **Error Handlers**: Populate error_message on failures
5. **Schemas**: Update Pydantic and TypeScript types
6. **API Client**: Add getVmLogs method
7. **LogViewer**: Container log display component
8. **ComponentHealth**: Status tree component
9. **ErrorTimeline**: Error history component
10. **DiagnosticsTab**: Container component
11. **RangeDetail**: Add tabs and integrate
12. **Testing**: Verify and release
