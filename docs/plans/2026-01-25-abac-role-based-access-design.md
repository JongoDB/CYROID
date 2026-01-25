# ABAC Role-Based Access Control Design

**Date**: 2026-01-25
**Status**: Planned
**Author**: Design session with Claude

---

## Overview

Implement full ABAC (Attribute-Based Access Control) with four distinct roles, role-based navigation gating, automatic student portal redirect, and a role perspective switcher for multi-role users.

---

## Role Definitions

| Role | Purpose | Navigation Access |
|------|---------|-------------------|
| **Administrator** | Full system control | All pages + Admin Settings |
| **Engineer** | Build & deploy ranges | All pages except Admin Settings |
| **Evaluator** | Score & review students | Dashboard, Training Scenarios (view), Content Library, Training Events (assigned), Ranges (assigned) |
| **Student** | Complete labs | Auto-redirects to Student Portal |

### Role Hierarchy (for default landing page)

```
Admin > Engineer > Evaluator > Student
```

- Users can have multiple roles
- Highest privilege determines default experience
- Student-only users never see main app navigation

---

## Navigation Access Matrix

| Page | Admin | Engineer | Evaluator | Student |
|------|-------|----------|-----------|---------|
| Dashboard | ✅ | ✅ | ✅ | ❌ (portal) |
| Image Cache | ✅ | ✅ | ❌ | ❌ |
| VM Library | ✅ | ✅ | ❌ | ❌ |
| Range Blueprints | ✅ | ✅ | ❌ | ❌ |
| Training Scenarios | ✅ | ✅ | ✅ (view) | ❌ |
| Content Library | ✅ | ✅ | ✅ | ❌ |
| Training Events | ✅ | ✅ | ✅ (assigned) | ❌ |
| Ranges | ✅ | ✅ | ✅ (assigned) | ❌ |
| Artifacts | ✅ | ✅ | ❌ | ❌ |
| Admin Settings | ✅ | ❌ | ❌ | ❌ |
| Student Portal | ✅ | ✅ | ❌ | ✅ (home) |

---

## Training Event Assignment System

### Tag-Based Bulk Assignment (Primary)

- Training Events use existing `ResourceTag` system
- Users with matching tags automatically see/access those events
- Example: Event tagged `cohort-2025-spring` → all users with that tag assigned

### Individual Assignment (Override)

New `EventAssignment` table for explicit user-to-event links:

```sql
CREATE TABLE event_assignments (
  id UUID PRIMARY KEY,
  event_id UUID REFERENCES training_events(id) ON DELETE CASCADE,
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  assignment_type VARCHAR(20),  -- 'student' or 'evaluator'
  is_excluded BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  UNIQUE(event_id, user_id)
);
```

### Access Resolution Logic

```
User can access event if:
  (user has matching tag OR user explicitly assigned)
  AND NOT explicitly excluded
```

### Role-Specific Event Access

- **Student**: Lab view, VMs configured for their visibility
- **Evaluator**: Student roster, evidence submissions, scoring interface, range overview (read-only)

---

## Role/Perspective Switcher UI

### For Multi-Role Users

**Sidebar placement (primary):**
- Current role badge in user section
- Click to reveal dropdown with available perspectives
- Selecting different perspective reloads view with that role's access

**Header bar indicator:**
- Shows "Viewing as: Engineer ▼"
- Click opens perspective switcher
- Only visible for multi-role users

### Switching Behavior

- Engineer → Student: Redirects to Student Portal
- Student → Engineer: Redirects to main app Dashboard
- Perspective stored in localStorage (persists across sessions)

### Visual Design

```
┌─────────────────────────┐
│ Signed in as: jsmith    │
│ ┌─────────────────────┐ │
│ │ 🛡 Engineer ▼       │ │  ← Clickable dropdown
│ └─────────────────────┘ │
│   ○ Administrator       │  ← Other available roles
│   ● Engineer (active)   │
│   ○ Student Portal →    │
└─────────────────────────┘
```

---

## Frontend Implementation

### Navigation Filtering

`Layout.tsx` filters navigation array based on active perspective:

```typescript
const navigationByRole = {
  admin: ['all pages'],
  engineer: ['all except /admin'],
  evaluator: ['/', '/scenarios', '/content', '/events', '/ranges'],
  student: [] // Redirects to Student Portal
}
```

### Route Protection

- `RoleGuard` component wraps protected routes
- Checks user's roles against required roles
- Students accessing main app → redirect to Student Portal
- Unauthorized access → redirect to Dashboard with toast

### Login Redirect Logic

```typescript
// After successful login:
if (user.roles.includes('admin') || user.roles.includes('engineer')) {
  navigate('/dashboard')
} else if (user.roles.includes('evaluator')) {
  navigate('/dashboard')
} else if (user.roles.includes('student')) {
  navigate('/student-portal')
}
```

---

## Migration

### Existing Data

- Users already have roles in `user_attributes` table
- Four roles already defined: `admin`, `engineer`, `student`, `evaluator`
- No data migration required - direct mapping works

### Legacy Cleanup (Optional)

- Remove deprecated `role` column from `User` model
- Update any code still using legacy `require_role()` function

---

## Implementation Order

1. **Backend**: Add `EventAssignment` model and CRUD endpoints
2. **Frontend**: Role-based navigation filtering in `Layout.tsx`
3. **Frontend**: `RoleGuard` component for route protection
4. **Frontend**: Login redirect logic based on roles
5. **Frontend**: Role/perspective switcher component
6. **Admin UI**: Event assignment management interface
7. **Integration**: Coordinate with Student Portal development

---

## Security Model

- **Frontend-only gating** for navigation and route access
- Backend tag-based visibility remains for resource filtering
- No additional backend role checks required for this phase

---

## Dependencies

- Student Portal (separate development effort)
- VM visibility feature (Issue #128) for controlling which VMs students see in labs

---

## Open Questions

None - design approved.
