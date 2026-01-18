# Comprehensive Timestamps and Activity History Design

## Overview

Add lifecycle timestamps to Range model and user attribution to events, with an Activity tab UI showing who did what and when.

## Design Goals

1. **Visibility**: Show when ranges were deployed, started, stopped
2. **Accountability**: Track which user triggered each event
3. **Simplicity**: Leverage existing EventLog system, minimal new infrastructure

---

## Data Model Changes

### Range Model Enhancement

Add optional lifecycle timestamps:

```python
# In range.py
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

- `deployed_at` - Set when deployment completes successfully
- `started_at` - Set when range starts (most recent start)
- `stopped_at` - Set when range stops (most recent stop)

### EventLog Enhancement

Add user tracking:

```python
# In event_log.py
user_id: Mapped[Optional[UUID]] = mapped_column(
    ForeignKey("users.id", ondelete="SET NULL"),
    nullable=True,
    index=True
)

user = relationship("User")
```

- Nullable for system-triggered events
- SET NULL on user deletion (preserve event history)

---

## API Changes

### Range Response Enhancement

Include lifecycle timestamps in existing Range schema:

```python
class RangeRead(BaseModel):
    # ... existing fields ...
    deployed_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
```

### EventLog Response Enhancement

Include user info in event responses:

```python
class EventLogRead(BaseModel):
    # ... existing fields ...
    user_id: Optional[UUID] = None
    user: Optional[UserBasic] = None  # {id, username, email}
```

No new endpoints needed - leverage existing `/api/v1/ranges/{id}/events`.

---

## UI Components

### Timestamps Display

Subtle info section below range header:

```
┌──────────────────────────────────────────────────────────────┐
│  Red Team Lab                                    [Running]   │
│  Created 2h ago • Deployed 1h 45m ago • Started 1h 30m ago  │
└──────────────────────────────────────────────────────────────┘
```

- Relative time (2h ago) with hover tooltip for exact timestamp
- Only shows timestamps that are set
- Muted text styling

### Activity Tab

New tab on RangeDetail alongside Overview, VMs, Networks, Diagnostics:

```
┌─────────────────────────────────────────────────────────────┐
│  Activity                                   [Filter ▾]      │
│                                                             │
│  Today                                                      │
│  ─────────────────────────────────────────────────────────  │
│  🟢 VM Started                              2:30 PM         │
│     dc01 started by jsmith                                  │
│                                                             │
│  🔵 Range Deployed                          2:15 PM         │
│     Deployment completed by jsmith (45s)                    │
│                                                             │
│  Yesterday                                                  │
│  ─────────────────────────────────────────────────────────  │
│  📝 Range Created                           4:00 PM         │
│     Created by jsmith                                       │
└─────────────────────────────────────────────────────────────┘
```

- Groups events by day
- Shows username (or email if no username, or "System" for automated)
- Color-coded icons by event type
- Optional filter dropdown

---

## Implementation Scope

### Backend

- `backend/cyroid/models/range.py` - Add lifecycle timestamp fields
- `backend/cyroid/models/event_log.py` - Add user_id field and relationship
- `backend/cyroid/schemas/range.py` - Include timestamps in response
- `backend/cyroid/schemas/event_log.py` - Include user info in response
- `backend/cyroid/services/event_service.py` - Accept user_id parameter
- `backend/cyroid/api/ranges.py` - Set timestamps on lifecycle changes, pass user to events
- New Alembic migration

### Frontend

- `frontend/src/types/index.ts` - Add fields to Range and EventLog types
- `frontend/src/pages/RangeDetail.tsx` - Timestamps display, Activity tab
- `frontend/src/components/range/ActivityTab.tsx` - New component
- `frontend/src/components/common/RelativeTime.tsx` - Reusable component

### Not in Scope (Future)

- Filtering events by user
- Audit log export
- VM/Network-level timestamps
- Batch operations tracking

---

## Related Issues

- #23 - Comprehensive timestamps and activity history (this design)
- #24 - Granular deployment status (completed, adds network_id to events)
