# Diagnostics Dashboard Design

**Issue:** [#4 - Enhanced Error Visibility & Intelligent Troubleshooting System](../../issues/4)
**Date:** 2026-01-17
**Status:** Approved
**Scope:** Phase 1 - Error Reporting Dashboard

## Overview

Add a Diagnostics tab to the RangeDetail page that displays component health status, error history, and on-demand container logs. This provides visibility into failures without requiring SSH or Docker CLI access.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  RangeDetail Page                                           │
│  ┌─────────┬──────────┬──────────────┐                     │
│  │ Builder │ Topology │ Diagnostics  │  ← New tab          │
│  └─────────┴──────────┴──────────────┘                     │
│                                                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Component Health        │ Error Timeline                ││
│  │ ─────────────────────   │ ────────────────────────────  ││
│  │ ✓ Range: running        │ 10:32 VM webserver failed     ││
│  │ ✓ Router: running       │ 10:31 Network created         ││
│  │ ✓ net-internal          │ 10:30 Router started          ││
│  │ ✗ vm-webserver (error)  │                    [View Logs]││
│  │   └─ "Exit code 1"      │                               ││
│  └─────────────────────────────────────────────────────────┘│
│                                                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Log Viewer: webserver                    [↻] [Copy] [X] ││
│  │ ───────────────────────────────────────────────────────  ││
│  │ 2024-01-17 10:32:01 Starting nginx...                   ││
│  │ 2024-01-17 10:32:02 Error: config syntax error line 42  ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

## Backend Changes

### Database Migration

Add `error_message` column to `vms` and `ranges` tables:

```python
# models/vm.py
error_message: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

# models/range.py
error_message: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
```

### New API Endpoint

```python
# GET /api/v1/vms/{vm_id}/logs
@router.get("/vms/{vm_id}/logs")
async def get_vm_logs(
    vm_id: UUID,
    tail: int = Query(100, ge=10, le=1000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Fetch last N lines of container logs."""
    vm = get_vm_or_404(db, vm_id)
    check_range_access(vm.range, current_user)

    if not vm.container_id:
        raise HTTPException(404, "VM has no container")

    docker = DockerService()
    logs = docker.get_container_logs(vm.container_id, tail=tail)

    return {
        "vm_id": vm_id,
        "container_id": vm.container_id,
        "lines": logs,
        "tail": tail
    }
```

### DockerService Addition

```python
def get_container_logs(self, container_id: str, tail: int = 100) -> list[str]:
    """Get last N lines of container logs."""
    try:
        container = self.client.containers.get(container_id)
        logs = container.logs(tail=tail, timestamps=True).decode('utf-8')
        return logs.strip().split('\n') if logs else []
    except NotFound:
        return ["Container not found"]
    except APIError as e:
        return [f"Error fetching logs: {e}"]
```

### Error Capture

Update error handlers in `api/vms.py` and `api/ranges.py` to populate `error_message`:

```python
except Exception as e:
    vm.status = VMStatus.ERROR
    vm.error_message = str(e)[:1000]
    db.commit()
    event_service.log_event(
        range_id=vm.range_id,
        vm_id=vm.id,
        event_type=EventType.VM_ERROR,
        message=str(e)
    )
```

## Frontend Components

```
frontend/src/components/diagnostics/
├── DiagnosticsTab.tsx      # Main tab container
├── ComponentHealth.tsx     # Status tree with health indicators
├── ErrorTimeline.tsx       # Chronological error list
└── LogViewer.tsx           # Container log display panel
```

### DiagnosticsTab.tsx

Main layout component:
- Two-column grid: ComponentHealth (left), ErrorTimeline (right)
- LogViewer appears below when a VM is selected
- Uses existing `useRealtimeRange` hook for live updates

### ComponentHealth.tsx

Status tree showing range health:
- Collapsible tree: Range → Router → Networks → VMs
- Color-coded status badges (green/yellow/red)
- Shows `error_message` inline for failed components
- Click VM row to load logs in LogViewer

### ErrorTimeline.tsx

Chronological error history:
- Fetches from `/api/v1/events?range_id=X&event_types=vm_error,deployment_failed,inject_failed`
- Displays timestamp, component name, message
- "View Logs" button for VM-related errors
- Filter dropdown by event type

### LogViewer.tsx

Container log display:
- Header: VM name, container ID (truncated), Refresh/Copy/Close buttons
- Monospace scrollable log output
- Auto-scroll to bottom on load
- Loading state while fetching

### Integration

Add "Diagnostics" tab to RangeDetail's tab system:
- Show error count badge when errors > 0
- Tab appears after existing tabs (Builder, Topology, Console)

## Data Flow

### Loading Diagnostics Tab

```
1. User clicks "Diagnostics" tab
   │
2. DiagnosticsTab mounts
   ├── Uses range data (already cached from RangeDetail)
   │   └── Includes: router, networks, vms with status/error_message
   │
   └── Fetches error events
       GET /api/v1/events?range_id=X&event_types=vm_error,deployment_failed,inject_failed
   │
3. ComponentHealth renders from range data
   │
4. ErrorTimeline renders from events data
```

### Viewing Logs

```
1. User clicks VM row or "View Logs" button
   │
2. LogViewer opens with loading state
   │
3. Fetches logs
   GET /api/v1/vms/{vm_id}/logs?tail=100
   │
4. Displays log lines with timestamps
   │
5. User can:
   ├── Refresh → re-fetch logs
   ├── Copy → copy to clipboard
   └── Close → hide LogViewer
```

### Real-time Updates

The existing `useRealtimeRange` hook provides:
- VM status changes via WebSocket
- Error events broadcast in real-time

DiagnosticsTab subscribes to these and updates automatically.

### Error Capture Flow

```
1. VM operation fails (start, create, etc.)
   │
2. Backend catches exception
   ├── Sets vm.status = "error"
   ├── Sets vm.error_message = str(exception)[:1000]
   ├── Logs EventType.VM_ERROR to event_logs
   └── Broadcasts via WebSocket
   │
3. Frontend receives event
   ├── Toast notification
   ├── Updates VM status in state
   └── Diagnostics tab shows new error
```

## Quick Actions (v1)

Available from the Diagnostics tab:
1. **Restart VM** - Restart a failed/stopped VM
2. **View Logs** - Fetch and display container logs
3. **Retry deployment** - Re-attempt VM creation if it failed during deployment

## Limitations

**Container logs only:** For QEMU and Windows VMs, container logs show hypervisor output, not guest OS logs. The UI will note: "For guest OS logs, use the console."

## Future Roadmap

### Phase 2 - Additional Quick Actions
- Force recreate VM (delete + create from template)
- Reset network (disconnect/reconnect all containers)
- Clear error state (reset status to stopped, clear error_message)
- Bulk restart all failed VMs

### Phase 3 - Intelligent Troubleshooting
- Pattern recognition for common errors:
  - "image not found" → suggest pulling image
  - "port already in use" → identify conflicting container
  - "no space left" → show disk usage, suggest cleanup
- Suggested remediation with one-click fixes
- Link to documentation for complex issues

### Phase 4 - Proactive Health Monitoring
- Pre-deployment validation (check images exist, network conflicts, resource availability)
- Host resource dashboard (CPU, memory, disk vs. range requirements)
- Real-time health alerts via WebSocket
- Container resource usage graphs

### Phase 5 - Advanced Diagnostics
- Full log streaming via WebSocket
- Log search/filtering
- Export debug bundle (logs, config, events as ZIP)
- Serial console capture for QEMU VMs

## Implementation Checklist

- [ ] Create migration for `error_message` on VM and Range models
- [ ] Add `get_container_logs()` to DockerService
- [ ] Add `GET /api/v1/vms/{vm_id}/logs` endpoint
- [ ] Update error handlers to populate `error_message`
- [ ] Create DiagnosticsTab component
- [ ] Create ComponentHealth component
- [ ] Create ErrorTimeline component
- [ ] Create LogViewer component
- [ ] Add Diagnostics tab to RangeDetail
- [ ] Add error count badge to tab
- [ ] Update TypeScript types for error_message fields
- [ ] Test with container, QEMU, and Windows VMs
