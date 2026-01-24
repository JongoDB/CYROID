# Global Notifications Design

## Overview

Add real-time global notifications to CYROID, showing system events to all logged-in users anywhere in the app via toast notifications and a notification bell with history.

## Requirements

- All system events visible to all logged-in users
- Toast notifications for immediate awareness
- Bell icon in header with dropdown showing notification history
- Hybrid persistence: localStorage for last 50 notifications
- Severity levels (info/warning/error) with color-coding and filtering

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Header                               │
│  [Logo] [Nav...]                    [🔔 3] [User] [Logout]  │
│                                       │                      │
│                              ┌────────▼────────┐            │
│                              │ NotificationBell │            │
│                              │ - Unread count   │            │
│                              │ - Dropdown list  │            │
│                              │ - Filter by type │            │
│                              └─────────────────┘            │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    Toast Container (bottom-right)            │
│                              ┌──────────────────┐           │
│                              │ 🟢 Range deployed │           │
│                              │ 🔴 VM failed      │           │
│                              └──────────────────┘           │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

1. Backend broadcasts event via Redis pub/sub
2. WebSocket delivers to all connected clients (no range_id filter)
3. `useGlobalNotifications` hook receives event
4. Event mapped to severity (info/warning/error)
5. Toast shown immediately (auto-dismiss after 5s)
6. Notification added to store (Zustand + localStorage sync)
7. Bell icon updates unread count

### Severity Mapping

| Severity | Color | Event Types |
|----------|-------|-------------|
| 🟢 Info | Green | deployment_started, deployment_completed, vm_started, vm_created, network_created |
| 🟡 Warning | Yellow | deployment_step (in progress), vm_stopped, vm_restarting |
| 🔴 Error | Red | deployment_failed, vm_failed, any event containing "error" or "failed" |

## Backend Changes

**None required.** The existing infrastructure already supports global notifications:

- `/ws/events` endpoint accepts optional `range_id` parameter
- When `range_id` is omitted, clients receive all events from `EVENTS_CHANNEL`
- `broadcast_event()` already publishes to global channel

The frontend simply hasn't been using global subscriptions.

## Frontend Implementation

### New Files

```
frontend/src/
├── stores/
│   └── notificationStore.ts       # Zustand store + localStorage sync
├── hooks/
│   └── useGlobalNotifications.ts  # WebSocket hook for global events
├── components/
│   └── notifications/
│       ├── NotificationBell.tsx   # Header bell + dropdown
│       ├── NotificationItem.tsx   # Single notification row
│       ├── ToastContainer.tsx     # Toast display area
│       └── Toast.tsx              # Individual toast component
└── providers/
    └── NotificationProvider.tsx   # App-level wrapper
```

### Notification Store

```typescript
interface Notification {
  id: string
  event_type: string
  message: string
  severity: 'info' | 'warning' | 'error'
  timestamp: string
  read: boolean
  range_id?: string
  vm_id?: string
}

interface NotificationStore {
  notifications: Notification[]
  unreadCount: number
  filter: 'all' | 'info' | 'warning' | 'error'

  addNotification: (event: RealtimeEvent) => void
  markAsRead: (id: string) => void
  markAllAsRead: () => void
  clearAll: () => void
  setFilter: (filter: string) => void
}
```

**Behaviors:**
- Maximum 50 notifications stored (oldest removed when exceeded)
- Auto-sync to localStorage on every change
- Load from localStorage on app initialization
- Severity derived from event_type via mapping function

### Severity Mapping Function

```typescript
function getSeverity(eventType: string): 'info' | 'warning' | 'error' {
  if (eventType.includes('failed') || eventType.includes('error')) return 'error'
  if (eventType.includes('step') || eventType.includes('stopped')) return 'warning'
  return 'info'
}
```

### Hook: useGlobalNotifications

Wraps the existing WebSocket infrastructure for global events:
- Connects to `/ws/events` without a `range_id`
- On each event, calls `notificationStore.addNotification()`
- Triggers toast display via callback

### Component: NotificationBell

```
┌─────────────────────────────────┐
│ 🔔 3                            │  <- Bell icon + unread badge
├─────────────────────────────────┤
│ [All] [Info] [Warn] [Error]     │  <- Filter tabs
├─────────────────────────────────┤
│ 🔴 VM kali failed to start      │
│    2 minutes ago                │
├─────────────────────────────────┤
│ 🟢 Range "Lab 1" deployed       │
│    5 minutes ago                │
├─────────────────────────────────┤
│ [Mark all read]   [Clear all]   │
└─────────────────────────────────┘
```

### Component: ToastContainer

- Positioned fixed bottom-right
- Shows new notifications as toasts
- Auto-dismiss after 5 seconds
- Click to dismiss immediately
- Color-coded left border by severity
- Maximum 3 toasts visible at once (stack)

### Component: NotificationProvider

- Wraps app at top level in `App.tsx`
- Initializes global WebSocket connection once (on auth)
- Provides toast triggering logic to children

## Integration Points

1. **`App.tsx`** - Wrap root with `<NotificationProvider>`
2. **`Sidebar.tsx`** - Add `<NotificationBell />` in header area near user menu
3. **`App.tsx`** - Add `<ToastContainer />` at root level (outside router)

## Styling

- Use existing Tailwind classes consistent with codebase
- Severity colors:
  - Info: `bg-green-500`, `border-green-500`
  - Warning: `bg-yellow-500`, `border-yellow-500`
  - Error: `bg-red-500`, `border-red-500`
- Dropdown uses existing card/shadow patterns (`bg-gray-800`, `shadow-lg`, `rounded-lg`)
- Bell badge: `bg-red-500 text-white text-xs rounded-full`

## Scope

- **New files:** 6
- **Lines of code:** ~400-500 TypeScript/React
- **Backend changes:** None
- **Database changes:** None

## Future Enhancements (Not in Scope)

- Database persistence for cross-device notification sync
- User preferences for notification types
- Sound alerts for errors
- Desktop notifications via browser API
- User attribution ("Admin deployed range X")
