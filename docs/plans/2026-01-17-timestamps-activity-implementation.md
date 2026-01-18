# Timestamps and Activity History Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add lifecycle timestamps to Range, user attribution to EventLog, and an Activity tab UI

**Architecture:** Extend existing models with nullable fields, update event logging to capture user context, create Activity tab component leveraging existing events API

**Tech Stack:** SQLAlchemy/Alembic (backend), React/TypeScript (frontend), existing EventLog infrastructure

---

## Task 1: Add Lifecycle Timestamps to Range Model

**Files:**
- Modify: `backend/cyroid/models/range.py:1-53`

**Step 1: Add timestamp imports and fields**

Add to imports at top:
```python
from datetime import datetime
from sqlalchemy import DateTime
```

Add after `error_message` field (line 28):
```python
    # Lifecycle timestamps
    deployed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    stopped_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

**Step 2: Verify import**

Run: `cd /Users/JonWFH/jondev/CYROID && docker-compose exec api python -c "from cyroid.models.range import Range; print('OK')"`

---

## Task 2: Add User ID to EventLog Model

**Files:**
- Modify: `backend/cyroid/models/event_log.py:1-58`

**Step 1: Add user_id field and relationship**

Add after `network_id` field (around line 50):
```python
    user_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
```

Add to relationships section (after line 57):
```python
    user = relationship("User")
```

**Step 2: Verify import**

Run: `cd /Users/JonWFH/jondev/CYROID && docker-compose exec api python -c "from cyroid.models.event_log import EventLog; print('OK')"`

---

## Task 3: Create Database Migration

**Files:**
- Create: `backend/alembic/versions/xxxx_add_lifecycle_timestamps_and_user_to_events.py`

**Step 1: Generate migration**

Run: `cd /Users/JonWFH/jondev/CYROID && docker-compose exec api alembic revision --autogenerate -m "add lifecycle timestamps and user to events"`

**Step 2: Review generated migration**

Check the generated file contains:
- Add `deployed_at`, `started_at`, `stopped_at` columns to `ranges` table
- Add `user_id` column to `event_logs` table
- Add foreign key constraint for `user_id`
- Add index on `user_id`

**Step 3: Apply migration**

Run: `cd /Users/JonWFH/jondev/CYROID && docker-compose exec api alembic upgrade head`

**Step 4: Verify columns exist**

Run: `docker-compose exec db psql -U cyroid -c "\d ranges" | grep -E "deployed_at|started_at|stopped_at"`
Run: `docker-compose exec db psql -U cyroid -c "\d event_logs" | grep user_id`

---

## Task 4: Update Range Schema

**Files:**
- Modify: `backend/cyroid/schemas/range.py:43-70`

**Step 1: Add timestamp fields to RangeResponse**

Add after `updated_at` field in `RangeResponse` class:
```python
    deployed_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
```

**Step 2: Update from_orm_with_counts method**

Add to the returned `cls()` call:
```python
            deployed_at=range_obj.deployed_at,
            started_at=range_obj.started_at,
            stopped_at=range_obj.stopped_at,
```

---

## Task 5: Update EventLog Schema

**Files:**
- Modify: `backend/cyroid/schemas/event_log.py:1-35`

**Step 1: Add UserBasic schema**

Add near top of file:
```python
class UserBasic(BaseModel):
    id: UUID
    username: str
    email: str

    class Config:
        from_attributes = True
```

**Step 2: Update EventLogCreate**

Add to `EventLogCreate` class:
```python
    user_id: Optional[UUID] = None
```

**Step 3: Update EventLogResponse**

Add to `EventLogResponse` class:
```python
    user_id: Optional[UUID] = None
    user: Optional[UserBasic] = None
```

---

## Task 6: Update Event Service

**Files:**
- Modify: `backend/cyroid/services/event_service.py:18-59`

**Step 1: Add user_id parameter**

Update `log_event` method signature:
```python
    def log_event(
        self,
        range_id: UUID,
        event_type: EventType,
        message: str,
        vm_id: Optional[UUID] = None,
        network_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,  # Add this
        extra_data: Optional[str] = None,
        broadcast: bool = True
    ) -> EventLog:
```

**Step 2: Pass user_id to EventLog creation**

Update the EventLog creation (around line 43):
```python
        event = EventLog(
            range_id=range_id,
            vm_id=vm_id,
            network_id=network_id,
            user_id=user_id,  # Add this
            event_type=event_type,
            message=message,
            extra_data=extra_data
        )
```

---

## Task 7: Update Ranges API - Set Timestamps and Pass User

**Files:**
- Modify: `backend/cyroid/api/ranges.py:299-400` (deploy)
- Modify: `backend/cyroid/api/ranges.py:769-820` (start)
- Modify: `backend/cyroid/api/ranges.py:823-870` (stop)

**Step 1: Update deploy_range - set deployed_at and pass user_id**

Add after successful deployment completes (after `range_obj.status = RangeStatus.RUNNING`):
```python
        from datetime import datetime, timezone
        range_obj.deployed_at = datetime.now(timezone.utc)
```

Update all `event_service.log_event` calls to include `user_id=current_user.id`.

**Step 2: Update start_range - set started_at and log event with user**

After `range_obj.status = RangeStatus.RUNNING`:
```python
        from datetime import datetime, timezone
        range_obj.started_at = datetime.now(timezone.utc)
```

Add event logging:
```python
        event_service = EventService(db)
        event_service.log_event(
            range_id=range_id,
            event_type=EventType.RANGE_STARTED,
            message=f"Range '{range_obj.name}' started",
            user_id=current_user.id
        )
```

**Step 3: Update stop_range - set stopped_at and log event with user**

After `range_obj.status = RangeStatus.STOPPED`:
```python
        from datetime import datetime, timezone
        range_obj.stopped_at = datetime.now(timezone.utc)
```

Add event logging:
```python
        event_service = EventService(db)
        event_service.log_event(
            range_id=range_id,
            event_type=EventType.RANGE_STOPPED,
            message=f"Range '{range_obj.name}' stopped",
            user_id=current_user.id
        )
```

---

## Task 8: Update Events API to Include User

**Files:**
- Modify: `backend/cyroid/api/events.py` (or `ranges.py` where events endpoint is)

**Step 1: Eager load user relationship**

When querying events, add joinedload for user:
```python
from sqlalchemy.orm import joinedload
# In query:
.options(joinedload(EventLog.user))
```

---

## Task 9: Update Frontend Types

**Files:**
- Modify: `frontend/src/types/index.ts:36-50` (Range)
- Modify: `frontend/src/types/index.ts:178-187` (EventLog)

**Step 1: Add lifecycle timestamps to Range**

Add after `updated_at`:
```typescript
  deployed_at: string | null
  started_at: string | null
  stopped_at: string | null
```

**Step 2: Add UserBasic type**

Add before EventLog:
```typescript
export interface UserBasic {
  id: string
  username: string
  email: string
}
```

**Step 3: Add user fields to EventLog**

Add to EventLog interface:
```typescript
  user_id: string | null
  user: UserBasic | null
```

---

## Task 10: Create RelativeTime Component

**Files:**
- Create: `frontend/src/components/common/RelativeTime.tsx`

**Step 1: Create component**

```tsx
import { useMemo } from 'react'

interface Props {
  date: string | null
  prefix?: string
}

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSecs = Math.floor(diffMs / 1000)
  const diffMins = Math.floor(diffSecs / 60)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffSecs < 60) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString()
}

export function RelativeTime({ date, prefix }: Props) {
  const formatted = useMemo(() => {
    if (!date) return null
    return formatRelativeTime(date)
  }, [date])

  if (!formatted) return null

  const fullDate = new Date(date!).toLocaleString()

  return (
    <span title={fullDate} className="cursor-help">
      {prefix}{formatted}
    </span>
  )
}
```

---

## Task 11: Add Timestamps Display to RangeDetail Header

**Files:**
- Modify: `frontend/src/pages/RangeDetail.tsx`

**Step 1: Import RelativeTime**

Add import:
```typescript
import { RelativeTime } from '../components/common/RelativeTime'
```

**Step 2: Add timestamps below range name**

Find the header section with range name and add below it:
```tsx
{range && (
  <div className="text-sm text-gray-500 flex items-center gap-2">
    <RelativeTime date={range.created_at} prefix="Created " />
    {range.deployed_at && (
      <>
        <span>•</span>
        <RelativeTime date={range.deployed_at} prefix="Deployed " />
      </>
    )}
    {range.started_at && (
      <>
        <span>•</span>
        <RelativeTime date={range.started_at} prefix="Started " />
      </>
    )}
    {range.stopped_at && range.status === 'stopped' && (
      <>
        <span>•</span>
        <RelativeTime date={range.stopped_at} prefix="Stopped " />
      </>
    )}
  </div>
)}
```

---

## Task 12: Create ActivityTab Component

**Files:**
- Create: `frontend/src/components/range/ActivityTab.tsx`

**Step 1: Create component**

```tsx
import { useState, useEffect } from 'react'
import { rangesApi } from '../../services/api'
import type { EventLog } from '../../types'
import { RelativeTime } from '../common/RelativeTime'
import {
  Rocket, Play, Square, Server, Network, AlertCircle,
  Loader2, Activity
} from 'lucide-react'

interface Props {
  rangeId: string
}

const eventIcons: Record<string, typeof Activity> = {
  deployment_started: Rocket,
  deployment_completed: Rocket,
  range_started: Play,
  range_stopped: Square,
  vm_started: Server,
  vm_stopped: Server,
  vm_error: AlertCircle,
  network_created: Network,
}

const eventColors: Record<string, string> = {
  deployment_started: 'text-blue-500',
  deployment_completed: 'text-green-500',
  deployment_failed: 'text-red-500',
  range_started: 'text-green-500',
  range_stopped: 'text-gray-500',
  vm_started: 'text-green-500',
  vm_stopped: 'text-gray-500',
  vm_error: 'text-red-500',
  network_created: 'text-blue-500',
}

function groupEventsByDay(events: EventLog[]): Map<string, EventLog[]> {
  const groups = new Map<string, EventLog[]>()
  const today = new Date().toDateString()
  const yesterday = new Date(Date.now() - 86400000).toDateString()

  for (const event of events) {
    const date = new Date(event.created_at).toDateString()
    let label = date
    if (date === today) label = 'Today'
    else if (date === yesterday) label = 'Yesterday'

    if (!groups.has(label)) groups.set(label, [])
    groups.get(label)!.push(event)
  }
  return groups
}

export function ActivityTab({ rangeId }: Props) {
  const [events, setEvents] = useState<EventLog[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    rangesApi.getRangeEvents(rangeId, 100)
      .then(res => setEvents(res.data.events))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [rangeId])

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
      </div>
    )
  }

  const grouped = groupEventsByDay(events)

  return (
    <div className="p-6">
      <h2 className="text-lg font-semibold mb-4">Activity</h2>

      {events.length === 0 ? (
        <p className="text-gray-500">No activity recorded yet.</p>
      ) : (
        <div className="space-y-6">
          {Array.from(grouped.entries()).map(([day, dayEvents]) => (
            <div key={day}>
              <h3 className="text-sm font-medium text-gray-500 mb-2">{day}</h3>
              <div className="space-y-2">
                {dayEvents.map(event => {
                  const Icon = eventIcons[event.event_type] || Activity
                  const colorClass = eventColors[event.event_type] || 'text-gray-500'
                  const time = new Date(event.created_at).toLocaleTimeString([], {
                    hour: '2-digit',
                    minute: '2-digit'
                  })
                  const username = event.user?.username || event.user?.email || 'System'

                  return (
                    <div key={event.id} className="flex items-start gap-3 py-2">
                      <Icon className={`w-5 h-5 mt-0.5 ${colorClass}`} />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900">
                          {event.message}
                        </p>
                        <p className="text-xs text-gray-500">
                          by {username}
                        </p>
                      </div>
                      <span className="text-xs text-gray-400 whitespace-nowrap">
                        {time}
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
```

---

## Task 13: Add Activity Tab to RangeDetail

**Files:**
- Modify: `frontend/src/pages/RangeDetail.tsx`

**Step 1: Import ActivityTab**

Add import:
```typescript
import { ActivityTab } from '../components/range/ActivityTab'
```

**Step 2: Update tab state type**

Change:
```typescript
const [activeTab, setActiveTab] = useState<'builder' | 'diagnostics'>('builder')
```
To:
```typescript
const [activeTab, setActiveTab] = useState<'builder' | 'diagnostics' | 'activity'>('builder')
```

**Step 3: Add Activity tab button**

Find the tab buttons and add after Diagnostics:
```tsx
<button
  onClick={() => setActiveTab('activity')}
  className={clsx(
    'flex items-center gap-2 px-4 py-2 font-medium border-b-2',
    activeTab === 'activity'
      ? 'border-blue-500 text-blue-600'
      : 'border-transparent text-gray-500 hover:text-gray-700'
  )}
>
  <Activity className="w-4 h-4" />
  Activity
</button>
```

**Step 4: Add Activity tab content**

In the tab content section, add:
```tsx
{activeTab === 'activity' && range && (
  <ActivityTab rangeId={range.id} />
)}
```

---

## Task 14: Update CHANGELOG and Version

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `backend/cyroid/config.py:9`

**Step 1: Update version to 0.6.3**

In `config.py`:
```python
    app_version: str = "0.6.3"
```

**Step 2: Add changelog entry**

Add at top after `## [0.6.2]`:
```markdown
## [0.6.3] - 2026-01-17

### Added

- **Lifecycle Timestamps & Activity History** ([#23](../../issues/23)): Track when ranges are deployed, started, and stopped with user attribution.
  - Range model now includes `deployed_at`, `started_at`, `stopped_at` timestamps
  - EventLog now includes `user_id` to track who triggered events
  - Timestamps displayed in Range header with relative time (hover for exact)
  - New Activity tab on RangeDetail showing event history grouped by day
  - Events show username/email of who triggered them
```

---

## Task 15: Commit and Tag

**Step 1: Stage all changes**

```bash
git add -A
```

**Step 2: Commit**

```bash
git commit -m "feat: add lifecycle timestamps and activity history (#23)

- Add deployed_at, started_at, stopped_at to Range model
- Add user_id to EventLog for user attribution
- Display lifecycle timestamps in Range header
- New Activity tab showing events with user info
- Events grouped by day with relative timestamps

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

**Step 3: Create tag**

```bash
git tag v0.6.3
git push origin master --tags
```
