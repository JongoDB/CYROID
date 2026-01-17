# Walkthrough Panel Design

**Issue:** [#8 - Integrated walkthrough/guide panel alongside VM consoles](../../issues/8)
**Date:** 2026-01-17
**Status:** Approved

## Overview

Add a student-facing Lab page (`/lab/:rangeId`) with an integrated walkthrough panel alongside VNC consoles. Instructors author walkthrough content as part of the MSEL, and students follow step-by-step guides while working in their VMs.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Where does it live? | New `/lab/:rangeId` page | Students need clean UI, not Execution Console (evaluator-only) |
| Content authoring | Extend MSEL YAML with `walkthrough:` section | Reuses existing upload/parse infrastructure |
| Progress tracking | Hybrid - local + optional server sync | Fast UX with persistence option |
| Panel layout | Left panel (guide) + right (VNC console) | Natural reading flow, collapsible |
| VM linking | "Open VM" button on steps | Helpful but non-intrusive |

## Data Model

### Walkthrough YAML (in MSEL)

```yaml
name: Red Team Training Lab

injects:
  - id: inject-1
    time: "00:30:00"
    title: "Malware detected"
    ...

walkthrough:
  title: "Red Team Attack Chain"
  phases:
    - id: recon
      name: "Reconnaissance"
      steps:
        - id: step-1
          title: "Scan the network"
          vm: kali
          content: |
            Use nmap to discover hosts on the target network:

            ```bash
            nmap -sn 172.16.0.0/24
            ```

            > **Tip:** Look for the web server on port 80

        - id: step-2
          title: "Identify the web application"
          vm: kali
          content: |
            Navigate to the discovered web server...

    - id: exploit
      name: "Exploitation"
      steps:
        - id: step-3
          title: "SQL Injection"
          vm: kali
          content: |
            Test the login form for SQL injection...
```

### TypeScript Types

```typescript
interface WalkthroughStep {
  id: string
  title: string
  content: string      // Markdown
  vm?: string          // VM hostname to link to
}

interface WalkthroughPhase {
  id: string
  name: string
  steps: WalkthroughStep[]
}

interface Walkthrough {
  title: string
  phases: WalkthroughPhase[]
}

interface WalkthroughProgress {
  rangeId: string
  visitorId: string
  completedSteps: string[]
  currentPhase: string
  currentStep: string
  updatedAt: string
}
```

### Database Schema

```python
# Extend MSEL model
class MSEL(Base):
    # ... existing fields ...
    walkthrough: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

# New table for progress sync
class WalkthroughProgress(Base):
    __tablename__ = "walkthrough_progress"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    range_id: Mapped[UUID] = mapped_column(ForeignKey("ranges.id"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    completed_steps: Mapped[list[str]] = mapped_column(JSON, default=list)
    current_phase: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    current_step: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # Unique constraint: one progress record per user per range
    __table_args__ = (UniqueConstraint('range_id', 'user_id'),)
```

## API Endpoints

```
GET  /api/v1/ranges/{id}/walkthrough
     Response: { walkthrough: Walkthrough | null }

GET  /api/v1/ranges/{id}/walkthrough/progress
     Response: { progress: WalkthroughProgress | null }

PUT  /api/v1/ranges/{id}/walkthrough/progress
     Body: { completed_steps: string[], current_phase?: string, current_step?: string }
     Response: { progress: WalkthroughProgress }
```

## UI Architecture

### Page Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  Red Team Training Lab                       [Progress: 4/12] [?]  │
├────────────────────────┬────────────────────────────────────────────┤
│                        │                                            │
│  📖 WALKTHROUGH   [−]  │   ┌──────────────────────────────────────┐ │
│  ───────────────────   │   │                                      │ │
│  [Recon] [Exploit]     │   │     VNC Console: kali                │ │
│                        │   │     (172.16.0.10)                    │ │
│  Phase 1: Recon        │   │                                      │ │
│  ─────────────────     │   │     root@kali:~# _                   │ │
│  [x] Scan network      │   │                                      │ │
│  [ ] Identify targets  │   │                                      │ │
│                        │   └──────────────────────────────────────┘ │
│  ─────────────────     │                                            │
│  ## Scan Network       │   VM Selector:                             │
│                        │   [kali ●] [webserver] [dc01] [workstation]│
│  Use nmap to find...   │                                            │
│  ```                   │                                            │
│  nmap -sn 172.16.0/24  │                                            │
│  ```                   │                                            │
│                        │                                            │
│  [Open kali ↗]         │   [Save Progress]                          │
│  [◀ Prev] [Next ▶]     │                                            │
└────────────────────────┴────────────────────────────────────────────┘
```

### Component Structure

```
frontend/src/
├── pages/
│   └── StudentLab.tsx              # New /lab/:rangeId page
│
├── components/
│   ├── walkthrough/
│   │   ├── WalkthroughPanel.tsx    # Main left panel container
│   │   ├── PhaseNav.tsx            # Phase tabs/pills
│   │   ├── StepList.tsx            # Step checkboxes
│   │   ├── StepContent.tsx         # Markdown renderer
│   │   └── ProgressBar.tsx         # Progress indicator + sync
│   │
│   └── lab/
│       ├── VMSelector.tsx          # Clickable VM tabs
│       └── ConsoleEmbed.tsx        # Embedded VNC viewer
```

### Key Behaviors

1. **Panel Resize**: Left panel resizable (default 30%), collapsible to icon strip
2. **Step Navigation**: Click step in list or use Prev/Next buttons
3. **Checkbox Toggle**: Click checkbox to mark step complete (saves to localStorage)
4. **VM Context**: "Open VM" button switches to that VM's console
5. **Progress Sync**: "Save Progress" button syncs to server; auto-sync on navigation away
6. **Markdown Rendering**: Support headers, code blocks, blockquotes (tips/warnings), images

## Progress Tracking Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  User toggles   │────▶│  Save to        │────▶│  Mark "dirty"   │
│  checkbox       │     │  localStorage   │     │  for sync       │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                        ┌───────────────────────────────┘
                        ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  User clicks    │────▶│  PUT /progress  │────▶│  Clear dirty    │
│  "Save Progress"│     │  to server      │     │  flag           │
└─────────────────┘     └─────────────────┘     └─────────────────┘

Also triggers on:
- beforeunload (auto-save on navigate away)
- Every 5 minutes (background sync if dirty)
```

## Implementation Phases

### Phase 1 (This Implementation)

**Backend:**
- [ ] Add `walkthrough` JSON column to MSEL model (migration)
- [ ] Extend MSEL parser to extract `walkthrough:` section
- [ ] Create WalkthroughProgress model and migration
- [ ] Add GET/PUT `/ranges/{id}/walkthrough` endpoints
- [ ] Add GET/PUT `/ranges/{id}/walkthrough/progress` endpoints

**Frontend:**
- [ ] Create StudentLab page with routing
- [ ] Build WalkthroughPanel with PhaseNav, StepList, StepContent
- [ ] Build VMSelector and ConsoleEmbed components
- [ ] Implement localStorage progress with server sync
- [ ] Add markdown rendering (react-markdown or similar)
- [ ] Implement resizable split-pane layout

### Out of Scope (Future Enhancements)

- Auto-validation of step completion (detect command execution)
- Embedded terminals in guide code blocks
- Progressive hints system
- Time tracking per phase
- Branching/conditional paths
- Instructor dashboard for class-wide progress
- Export completion reports

## Success Criteria

1. Instructor uploads MSEL with `walkthrough:` section - parses correctly
2. Student navigates to `/lab/:rangeId` - sees split-pane with guide + console
3. Student can navigate phases, click steps, toggle checkboxes
4. Progress persists in localStorage across page refreshes
5. "Save Progress" syncs to server, visible on return
6. "Open VM" button switches console to referenced VM
7. Markdown renders correctly (code blocks, tips, headers)

## Dependencies

- `react-resizable-panels` or similar for split-pane
- `react-markdown` + `remark-gfm` for markdown rendering
- Existing VNC console infrastructure (VncConsole component)
