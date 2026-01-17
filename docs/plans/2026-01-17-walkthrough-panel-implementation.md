# Walkthrough Panel Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a student-facing Lab page (`/lab/:rangeId`) with an integrated walkthrough panel alongside VNC consoles, allowing students to follow step-by-step guides while working in their VMs.

**Architecture:** Extend MSEL YAML to include a `walkthrough:` section. Create new WalkthroughProgress model for server-side persistence. Build a split-pane Lab page with resizable walkthrough panel on the left and VNC console on the right.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, React 18, TypeScript, Tailwind CSS, react-markdown, react-resizable-panels

---

## Task 1: Add Walkthrough JSON Column to MSEL Model

**Files:**
- Modify: `backend/cyroid/models/msel.py`
- Create: `backend/cyroid/alembic/versions/xxxx_add_walkthrough_to_msel.py` (generated)

**Step 1: Modify MSEL model to add walkthrough column**

Add import and field to `backend/cyroid/models/msel.py`:

```python
# Add JSON import at the top
from sqlalchemy import String, Text, ForeignKey, JSON

# Add this field after the content field in the MSEL class:
    walkthrough: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
```

**Step 2: Generate Alembic migration**

Run:
```bash
docker-compose exec api alembic revision --autogenerate -m "add_walkthrough_to_msel"
```

**Step 3: Apply migration**

Run:
```bash
docker-compose exec api alembic upgrade head
```

**Step 4: Commit**

```bash
git add backend/cyroid/models/msel.py backend/cyroid/alembic/versions/
git commit -m "feat(msel): add walkthrough JSON column to MSEL model"
```

---

## Task 2: Create WalkthroughProgress Model

**Files:**
- Create: `backend/cyroid/models/walkthrough_progress.py`
- Modify: `backend/cyroid/models/__init__.py`
- Create: Alembic migration (generated)

**Step 1: Create the WalkthroughProgress model**

Create file `backend/cyroid/models/walkthrough_progress.py`:

```python
# backend/cyroid/models/walkthrough_progress.py
from typing import Optional, List, TYPE_CHECKING
from uuid import UUID
from sqlalchemy import String, ForeignKey, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cyroid.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from cyroid.models.range import Range
    from cyroid.models.user import User


class WalkthroughProgress(Base, UUIDMixin, TimestampMixin):
    """Tracks student progress through a walkthrough."""
    __tablename__ = "walkthrough_progress"

    range_id: Mapped[UUID] = mapped_column(
        ForeignKey("ranges.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    completed_steps: Mapped[List[str]] = mapped_column(JSON, default=list)
    current_phase: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    current_step: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Relationships
    range: Mapped["Range"] = relationship("Range")
    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        UniqueConstraint('range_id', 'user_id', name='uq_walkthrough_progress_range_user'),
    )
```

**Step 2: Add to models __init__.py**

Add to `backend/cyroid/models/__init__.py`:
```python
from cyroid.models.walkthrough_progress import WalkthroughProgress
```

**Step 3: Generate migration**

Run:
```bash
docker-compose exec api alembic revision --autogenerate -m "add_walkthrough_progress_table"
```

**Step 4: Apply migration**

Run:
```bash
docker-compose exec api alembic upgrade head
```

**Step 5: Commit**

```bash
git add backend/cyroid/models/walkthrough_progress.py backend/cyroid/models/__init__.py backend/cyroid/alembic/versions/
git commit -m "feat(walkthrough): add WalkthroughProgress model for tracking student progress"
```

---

## Task 3: Extend MSEL Parser to Extract Walkthrough Section

**Files:**
- Modify: `backend/cyroid/services/msel_parser.py`

**Step 1: Add YAML parsing to MSELParser**

Add to `backend/cyroid/services/msel_parser.py`:

```python
import yaml
from typing import Optional

class MSELParser:
    # ... existing code ...

    def parse_walkthrough(self, content: str) -> Optional[dict]:
        """Extract walkthrough section from MSEL content.

        Supports both pure YAML format and Markdown with YAML front matter.
        """
        # Try to parse as YAML first
        try:
            data = yaml.safe_load(content)
            if isinstance(data, dict) and 'walkthrough' in data:
                return self._validate_walkthrough(data['walkthrough'])
        except yaml.YAMLError:
            pass

        # Try to extract from YAML front matter (---\n...\n---)
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                try:
                    front_matter = yaml.safe_load(parts[1])
                    if isinstance(front_matter, dict) and 'walkthrough' in front_matter:
                        return self._validate_walkthrough(front_matter['walkthrough'])
                except yaml.YAMLError:
                    pass

        return None

    def _validate_walkthrough(self, walkthrough: dict) -> Optional[dict]:
        """Validate walkthrough structure."""
        if not isinstance(walkthrough, dict):
            return None

        if 'title' not in walkthrough:
            return None

        if 'phases' not in walkthrough or not isinstance(walkthrough['phases'], list):
            return None

        for phase in walkthrough['phases']:
            if not isinstance(phase, dict):
                return None
            if 'id' not in phase or 'name' not in phase:
                return None
            if 'steps' not in phase or not isinstance(phase['steps'], list):
                return None
            for step in phase['steps']:
                if not isinstance(step, dict):
                    return None
                if 'id' not in step or 'title' not in step:
                    return None

        return walkthrough
```

**Step 2: Commit**

```bash
git add backend/cyroid/services/msel_parser.py
git commit -m "feat(msel): add walkthrough extraction to MSEL parser"
```

---

## Task 4: Update MSEL API to Store and Return Walkthrough

**Files:**
- Modify: `backend/cyroid/api/msel.py`

**Step 1: Update import_msel to extract and store walkthrough**

Modify `backend/cyroid/api/msel.py`:

```python
# In import_msel function, after parsing injects:
    # Parse MSEL
    parser = MSELParser()
    parsed_injects = parser.parse(data.content)
    walkthrough = parser.parse_walkthrough(data.content)  # Add this line

    # Create MSEL
    msel = MSEL(
        range_id=range_id,
        name=data.name,
        content=data.content,
        walkthrough=walkthrough  # Add this line
    )
```

**Step 2: Update MSELResponse to include walkthrough**

```python
class MSELResponse(BaseModel):
    id: UUID
    name: str
    range_id: UUID
    content: Optional[str] = None
    walkthrough: Optional[dict] = None  # Add this line
    injects: List[InjectResponse]

    class Config:
        from_attributes = True
```

**Step 3: Update get_msel to return walkthrough**

In the `get_msel` function, update the return:
```python
    return MSELResponse(
        id=msel.id,
        name=msel.name,
        range_id=msel.range_id,
        content=msel.content,
        walkthrough=msel.walkthrough,  # Add this line
        injects=[...]
    )
```

Also update the return in `import_msel` to include `walkthrough=msel.walkthrough`.

**Step 4: Commit**

```bash
git add backend/cyroid/api/msel.py
git commit -m "feat(msel): store and return walkthrough data in MSEL API"
```

---

## Task 5: Create Walkthrough API Endpoints

**Files:**
- Create: `backend/cyroid/api/walkthrough.py`
- Modify: `backend/cyroid/main.py`

**Step 1: Create walkthrough API**

Create file `backend/cyroid/api/walkthrough.py`:

```python
# backend/cyroid/api/walkthrough.py
from uuid import UUID
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from cyroid.api.deps import get_db, get_current_user
from cyroid.models.user import User
from cyroid.models.range import Range
from cyroid.models.msel import MSEL
from cyroid.models.walkthrough_progress import WalkthroughProgress


router = APIRouter(prefix="/ranges", tags=["walkthrough"])


class WalkthroughResponse(BaseModel):
    walkthrough: Optional[dict] = None


class WalkthroughProgressResponse(BaseModel):
    range_id: UUID
    user_id: UUID
    completed_steps: List[str]
    current_phase: Optional[str]
    current_step: Optional[str]
    updated_at: str

    class Config:
        from_attributes = True


class WalkthroughProgressUpdate(BaseModel):
    completed_steps: List[str]
    current_phase: Optional[str] = None
    current_step: Optional[str] = None


@router.get("/{range_id}/walkthrough", response_model=WalkthroughResponse)
def get_walkthrough(
    range_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the walkthrough content for a range."""
    range_obj = db.query(Range).filter(Range.id == range_id).first()
    if not range_obj:
        raise HTTPException(status_code=404, detail="Range not found")

    msel = db.query(MSEL).filter(MSEL.range_id == range_id).first()
    walkthrough = msel.walkthrough if msel else None

    return WalkthroughResponse(walkthrough=walkthrough)


@router.get("/{range_id}/walkthrough/progress", response_model=Optional[WalkthroughProgressResponse])
def get_walkthrough_progress(
    range_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the user's progress through the walkthrough."""
    range_obj = db.query(Range).filter(Range.id == range_id).first()
    if not range_obj:
        raise HTTPException(status_code=404, detail="Range not found")

    progress = db.query(WalkthroughProgress).filter(
        WalkthroughProgress.range_id == range_id,
        WalkthroughProgress.user_id == current_user.id
    ).first()

    if not progress:
        return None

    return WalkthroughProgressResponse(
        range_id=progress.range_id,
        user_id=progress.user_id,
        completed_steps=progress.completed_steps or [],
        current_phase=progress.current_phase,
        current_step=progress.current_step,
        updated_at=progress.updated_at.isoformat()
    )


@router.put("/{range_id}/walkthrough/progress", response_model=WalkthroughProgressResponse)
def update_walkthrough_progress(
    range_id: UUID,
    data: WalkthroughProgressUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update the user's progress through the walkthrough."""
    range_obj = db.query(Range).filter(Range.id == range_id).first()
    if not range_obj:
        raise HTTPException(status_code=404, detail="Range not found")

    progress = db.query(WalkthroughProgress).filter(
        WalkthroughProgress.range_id == range_id,
        WalkthroughProgress.user_id == current_user.id
    ).first()

    if progress:
        progress.completed_steps = data.completed_steps
        progress.current_phase = data.current_phase
        progress.current_step = data.current_step
    else:
        progress = WalkthroughProgress(
            range_id=range_id,
            user_id=current_user.id,
            completed_steps=data.completed_steps,
            current_phase=data.current_phase,
            current_step=data.current_step
        )
        db.add(progress)

    db.commit()
    db.refresh(progress)

    return WalkthroughProgressResponse(
        range_id=progress.range_id,
        user_id=progress.user_id,
        completed_steps=progress.completed_steps or [],
        current_phase=progress.current_phase,
        current_step=progress.current_step,
        updated_at=progress.updated_at.isoformat()
    )
```

**Step 2: Register router in main.py**

Add to `backend/cyroid/main.py`:
```python
from cyroid.api.walkthrough import router as walkthrough_router

# In the router registration section:
app.include_router(walkthrough_router, prefix="/api/v1")
```

**Step 3: Commit**

```bash
git add backend/cyroid/api/walkthrough.py backend/cyroid/main.py
git commit -m "feat(walkthrough): add walkthrough and progress API endpoints"
```

---

## Task 6: Add Walkthrough Types to Frontend

**Files:**
- Modify: `frontend/src/types/index.ts`

**Step 1: Add TypeScript types**

Add to `frontend/src/types/index.ts`:

```typescript
// Walkthrough Types
export interface WalkthroughStep {
  id: string
  title: string
  content: string
  vm?: string
}

export interface WalkthroughPhase {
  id: string
  name: string
  steps: WalkthroughStep[]
}

export interface Walkthrough {
  title: string
  phases: WalkthroughPhase[]
}

export interface WalkthroughProgress {
  range_id: string
  user_id: string
  completed_steps: string[]
  current_phase: string | null
  current_step: string | null
  updated_at: string
}
```

**Step 2: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat(walkthrough): add walkthrough TypeScript types"
```

---

## Task 7: Add Walkthrough API to Frontend

**Files:**
- Modify: `frontend/src/services/api.ts`

**Step 1: Add walkthrough API functions**

Add to `frontend/src/services/api.ts`:

```typescript
import type { Walkthrough, WalkthroughProgress } from '../types'

export interface WalkthroughResponse {
  walkthrough: Walkthrough | null
}

export interface WalkthroughProgressUpdate {
  completed_steps: string[]
  current_phase?: string
  current_step?: string
}

export const walkthroughApi = {
  get: (rangeId: string) =>
    api.get<WalkthroughResponse>(`/ranges/${rangeId}/walkthrough`),

  getProgress: (rangeId: string) =>
    api.get<WalkthroughProgress | null>(`/ranges/${rangeId}/walkthrough/progress`),

  updateProgress: (rangeId: string, data: WalkthroughProgressUpdate) =>
    api.put<WalkthroughProgress>(`/ranges/${rangeId}/walkthrough/progress`, data),
}
```

**Step 2: Commit**

```bash
git add frontend/src/services/api.ts
git commit -m "feat(walkthrough): add walkthrough API client functions"
```

---

## Task 8: Install Frontend Dependencies

**Files:**
- Modify: `frontend/package.json`

**Step 1: Install react-resizable-panels and react-markdown**

Run:
```bash
cd /Users/JonWFH/jondev/CYROID/frontend && npm install react-resizable-panels react-markdown remark-gfm
```

**Step 2: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "deps(frontend): add react-resizable-panels and react-markdown"
```

---

## Task 9: Create StepContent Component

**Files:**
- Create: `frontend/src/components/walkthrough/StepContent.tsx`

**Step 1: Create component**

Create `frontend/src/components/walkthrough/StepContent.tsx`:

```typescript
// frontend/src/components/walkthrough/StepContent.tsx
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { ExternalLink } from 'lucide-react'
import { WalkthroughStep } from '../../types'

interface StepContentProps {
  step: WalkthroughStep
  onOpenVM?: (vmHostname: string) => void
}

export function StepContent({ step, onOpenVM }: StepContentProps) {
  return (
    <div className="p-4">
      <h2 className="text-lg font-semibold text-white mb-4">{step.title}</h2>

      <div className="prose prose-invert prose-sm max-w-none">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            code({ inline, className, children, ...props }: { inline?: boolean; className?: string; children?: React.ReactNode }) {
              return !inline ? (
                <pre className="bg-gray-900 rounded-lg p-3 overflow-x-auto">
                  <code className={className} {...props}>
                    {children}
                  </code>
                </pre>
              ) : (
                <code className="bg-gray-700 px-1 rounded" {...props}>
                  {children}
                </code>
              )
            },
            blockquote({ children }: { children?: React.ReactNode }) {
              return (
                <blockquote className="border-l-4 border-blue-500 pl-4 py-1 my-3 bg-blue-900/20 rounded-r">
                  {children}
                </blockquote>
              )
            },
          }}
        >
          {step.content || ''}
        </ReactMarkdown>
      </div>

      {step.vm && onOpenVM && (
        <button
          onClick={() => onOpenVM(step.vm!)}
          className="mt-4 inline-flex items-center gap-2 px-3 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          <span>Open {step.vm}</span>
          <ExternalLink className="w-4 h-4" />
        </button>
      )}
    </div>
  )
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/walkthrough/StepContent.tsx
git commit -m "feat(walkthrough): create StepContent component with markdown rendering"
```

---

## Task 10: Create PhaseNav and StepList Components

**Files:**
- Create: `frontend/src/components/walkthrough/PhaseNav.tsx`
- Create: `frontend/src/components/walkthrough/StepList.tsx`

**Step 1: Create PhaseNav component**

Create `frontend/src/components/walkthrough/PhaseNav.tsx`:

```typescript
// frontend/src/components/walkthrough/PhaseNav.tsx
import clsx from 'clsx'
import { WalkthroughPhase } from '../../types'

interface PhaseNavProps {
  phases: WalkthroughPhase[]
  currentPhase: string
  onPhaseChange: (phaseId: string) => void
  completedSteps: Set<string>
}

export function PhaseNav({ phases, currentPhase, onPhaseChange, completedSteps }: PhaseNavProps) {
  const getPhaseProgress = (phase: WalkthroughPhase) => {
    const completed = phase.steps.filter(s => completedSteps.has(s.id)).length
    return { completed, total: phase.steps.length }
  }

  return (
    <div className="flex gap-2 px-4 py-2 overflow-x-auto">
      {phases.map((phase) => {
        const { completed, total } = getPhaseProgress(phase)
        const isComplete = completed === total
        const isCurrent = phase.id === currentPhase

        return (
          <button
            key={phase.id}
            onClick={() => onPhaseChange(phase.id)}
            className={clsx(
              'px-3 py-1.5 rounded-full text-sm font-medium whitespace-nowrap transition-colors',
              isCurrent
                ? 'bg-blue-600 text-white'
                : isComplete
                ? 'bg-green-600/20 text-green-400 border border-green-600/40'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            )}
          >
            {phase.name}
            <span className="ml-1 text-xs opacity-75">
              ({completed}/{total})
            </span>
          </button>
        )
      })}
    </div>
  )
}
```

**Step 2: Create StepList component**

Create `frontend/src/components/walkthrough/StepList.tsx`:

```typescript
// frontend/src/components/walkthrough/StepList.tsx
import clsx from 'clsx'
import { Check, Circle } from 'lucide-react'
import { WalkthroughStep } from '../../types'

interface StepListProps {
  steps: WalkthroughStep[]
  currentStep: string
  completedSteps: Set<string>
  onStepChange: (stepId: string) => void
  onToggleComplete: (stepId: string) => void
}

export function StepList({
  steps,
  currentStep,
  completedSteps,
  onStepChange,
  onToggleComplete
}: StepListProps) {
  return (
    <div className="px-4 py-2 space-y-1">
      {steps.map((step) => {
        const isComplete = completedSteps.has(step.id)
        const isCurrent = step.id === currentStep

        return (
          <div
            key={step.id}
            className={clsx(
              'flex items-center gap-2 p-2 rounded cursor-pointer transition-colors',
              isCurrent ? 'bg-gray-700' : 'hover:bg-gray-700/50'
            )}
            onClick={() => onStepChange(step.id)}
          >
            <button
              onClick={(e) => {
                e.stopPropagation()
                onToggleComplete(step.id)
              }}
              className={clsx(
                'w-5 h-5 rounded flex items-center justify-center flex-shrink-0',
                isComplete
                  ? 'bg-green-600 text-white'
                  : 'border border-gray-500 text-gray-500 hover:border-gray-400'
              )}
            >
              {isComplete ? <Check className="w-3 h-3" /> : <Circle className="w-3 h-3" />}
            </button>
            <span
              className={clsx(
                'text-sm',
                isComplete ? 'text-gray-400 line-through' : 'text-gray-200'
              )}
            >
              {step.title}
            </span>
          </div>
        )
      })}
    </div>
  )
}
```

**Step 3: Commit**

```bash
git add frontend/src/components/walkthrough/PhaseNav.tsx frontend/src/components/walkthrough/StepList.tsx
git commit -m "feat(walkthrough): create PhaseNav and StepList components"
```

---

## Task 11: Create ProgressBar Component

**Files:**
- Create: `frontend/src/components/walkthrough/ProgressBar.tsx`

**Step 1: Create component**

Create `frontend/src/components/walkthrough/ProgressBar.tsx`:

```typescript
// frontend/src/components/walkthrough/ProgressBar.tsx
import { Save, Cloud } from 'lucide-react'
import clsx from 'clsx'

interface ProgressBarProps {
  completed: number
  total: number
  isDirty: boolean
  isSyncing: boolean
  onSave: () => void
}

export function ProgressBar({ completed, total, isDirty, isSyncing, onSave }: ProgressBarProps) {
  const percent = total > 0 ? Math.round((completed / total) * 100) : 0

  return (
    <div className="flex items-center gap-3 px-4 py-2 bg-gray-800 border-b border-gray-700">
      <div className="flex-1">
        <div className="flex items-center justify-between text-sm mb-1">
          <span className="text-gray-400">Progress</span>
          <span className="text-gray-300">{completed}/{total} steps</span>
        </div>
        <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-blue-500 transition-all duration-300"
            style={{ width: `${percent}%` }}
          />
        </div>
      </div>

      <button
        onClick={onSave}
        disabled={isSyncing || !isDirty}
        className={clsx(
          'flex items-center gap-1.5 px-3 py-1.5 rounded text-sm font-medium transition-colors',
          isDirty
            ? 'bg-blue-600 text-white hover:bg-blue-700'
            : 'bg-gray-700 text-gray-400'
        )}
      >
        {isSyncing ? (
          <>
            <Cloud className="w-4 h-4 animate-pulse" />
            <span>Saving...</span>
          </>
        ) : isDirty ? (
          <>
            <Save className="w-4 h-4" />
            <span>Save Progress</span>
          </>
        ) : (
          <>
            <Cloud className="w-4 h-4" />
            <span>Saved</span>
          </>
        )}
      </button>
    </div>
  )
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/walkthrough/ProgressBar.tsx
git commit -m "feat(walkthrough): create ProgressBar component with sync status"
```

---

## Task 12: Create WalkthroughPanel Component

**Files:**
- Create: `frontend/src/components/walkthrough/WalkthroughPanel.tsx`
- Create: `frontend/src/components/walkthrough/index.ts`

**Step 1: Create WalkthroughPanel**

Create `frontend/src/components/walkthrough/WalkthroughPanel.tsx`:

```typescript
// frontend/src/components/walkthrough/WalkthroughPanel.tsx
import { useState, useEffect, useCallback, useMemo } from 'react'
import { ChevronLeft, ChevronRight, BookOpen, X } from 'lucide-react'
import { Walkthrough } from '../../types'
import { walkthroughApi } from '../../services/api'
import { PhaseNav } from './PhaseNav'
import { StepList } from './StepList'
import { StepContent } from './StepContent'
import { ProgressBar } from './ProgressBar'

interface WalkthroughPanelProps {
  rangeId: string
  walkthrough: Walkthrough
  onOpenVM: (vmHostname: string) => void
  onCollapse?: () => void
}

const STORAGE_KEY_PREFIX = 'cyroid_walkthrough_'
const SYNC_INTERVAL_MS = 5 * 60 * 1000 // 5 minutes

export function WalkthroughPanel({ rangeId, walkthrough, onOpenVM, onCollapse }: WalkthroughPanelProps) {
  const [currentPhase, setCurrentPhase] = useState(walkthrough.phases[0]?.id || '')
  const [currentStep, setCurrentStep] = useState(walkthrough.phases[0]?.steps[0]?.id || '')
  const [completedSteps, setCompletedSteps] = useState<Set<string>>(new Set())
  const [isDirty, setIsDirty] = useState(false)
  const [isSyncing, setIsSyncing] = useState(false)

  // Load from localStorage on mount
  useEffect(() => {
    const storageKey = `${STORAGE_KEY_PREFIX}${rangeId}`
    const saved = localStorage.getItem(storageKey)
    if (saved) {
      try {
        const data = JSON.parse(saved)
        setCompletedSteps(new Set(data.completedSteps || []))
        if (data.currentPhase) setCurrentPhase(data.currentPhase)
        if (data.currentStep) setCurrentStep(data.currentStep)
      } catch (e) {
        console.error('Failed to parse saved progress:', e)
      }
    }

    // Load from server
    walkthroughApi.getProgress(rangeId).then(res => {
      if (res.data) {
        setCompletedSteps(new Set(res.data.completed_steps || []))
        if (res.data.current_phase) setCurrentPhase(res.data.current_phase)
        if (res.data.current_step) setCurrentStep(res.data.current_step)
      }
    }).catch(() => {})
  }, [rangeId])

  // Save to localStorage when state changes
  useEffect(() => {
    const storageKey = `${STORAGE_KEY_PREFIX}${rangeId}`
    localStorage.setItem(storageKey, JSON.stringify({
      completedSteps: Array.from(completedSteps),
      currentPhase,
      currentStep,
    }))
  }, [rangeId, completedSteps, currentPhase, currentStep])

  // Auto-sync to server
  useEffect(() => {
    if (!isDirty) return
    const timer = setInterval(() => {
      if (isDirty) syncToServer()
    }, SYNC_INTERVAL_MS)
    return () => clearInterval(timer)
  }, [isDirty])

  // Sync on page unload
  useEffect(() => {
    const handleBeforeUnload = () => {
      if (isDirty) {
        const token = localStorage.getItem('token')
        navigator.sendBeacon(
          `/api/v1/ranges/${rangeId}/walkthrough/progress`,
          new Blob([JSON.stringify({
            completed_steps: Array.from(completedSteps),
            current_phase: currentPhase,
            current_step: currentStep,
          })], { type: 'application/json' })
        )
      }
    }
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [rangeId, completedSteps, currentPhase, currentStep, isDirty])

  const syncToServer = useCallback(async () => {
    setIsSyncing(true)
    try {
      await walkthroughApi.updateProgress(rangeId, {
        completed_steps: Array.from(completedSteps),
        current_phase: currentPhase,
        current_step: currentStep,
      })
      setIsDirty(false)
    } catch (e) {
      console.error('Failed to sync progress:', e)
    } finally {
      setIsSyncing(false)
    }
  }, [rangeId, completedSteps, currentPhase, currentStep])

  const currentPhaseData = walkthrough.phases.find(p => p.id === currentPhase)
  const currentStepData = currentPhaseData?.steps.find(s => s.id === currentStep)

  const totalSteps = useMemo(() =>
    walkthrough.phases.reduce((acc, p) => acc + p.steps.length, 0),
    [walkthrough]
  )

  const handleToggleComplete = (stepId: string) => {
    setCompletedSteps(prev => {
      const next = new Set(prev)
      if (next.has(stepId)) {
        next.delete(stepId)
      } else {
        next.add(stepId)
      }
      return next
    })
    setIsDirty(true)
  }

  const handleStepChange = (stepId: string) => {
    setCurrentStep(stepId)
    setIsDirty(true)
  }

  const handlePhaseChange = (phaseId: string) => {
    setCurrentPhase(phaseId)
    const phase = walkthrough.phases.find(p => p.id === phaseId)
    if (phase?.steps[0]) {
      setCurrentStep(phase.steps[0].id)
    }
    setIsDirty(true)
  }

  const navigateStep = (direction: 'prev' | 'next') => {
    const allSteps = walkthrough.phases.flatMap(p => p.steps.map(s => ({ ...s, phaseId: p.id })))
    const currentIndex = allSteps.findIndex(s => s.id === currentStep)
    const newIndex = direction === 'next' ? currentIndex + 1 : currentIndex - 1

    if (newIndex >= 0 && newIndex < allSteps.length) {
      const newStep = allSteps[newIndex]
      if (newStep.phaseId !== currentPhase) {
        setCurrentPhase(newStep.phaseId)
      }
      setCurrentStep(newStep.id)
      setIsDirty(true)
    }
  }

  return (
    <div className="h-full flex flex-col bg-gray-800 border-r border-gray-700">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-gray-800 border-b border-gray-700">
        <div className="flex items-center gap-2">
          <BookOpen className="w-5 h-5 text-blue-400" />
          <h1 className="font-semibold text-white">{walkthrough.title}</h1>
        </div>
        {onCollapse && (
          <button
            onClick={onCollapse}
            className="p-1 text-gray-400 hover:text-white"
          >
            <X className="w-5 h-5" />
          </button>
        )}
      </div>

      {/* Progress */}
      <ProgressBar
        completed={completedSteps.size}
        total={totalSteps}
        isDirty={isDirty}
        isSyncing={isSyncing}
        onSave={syncToServer}
      />

      {/* Phase Navigation */}
      <PhaseNav
        phases={walkthrough.phases}
        currentPhase={currentPhase}
        onPhaseChange={handlePhaseChange}
        completedSteps={completedSteps}
      />

      {/* Step List */}
      {currentPhaseData && (
        <div className="border-b border-gray-700">
          <StepList
            steps={currentPhaseData.steps}
            currentStep={currentStep}
            completedSteps={completedSteps}
            onStepChange={handleStepChange}
            onToggleComplete={handleToggleComplete}
          />
        </div>
      )}

      {/* Step Content */}
      <div className="flex-1 overflow-y-auto">
        {currentStepData && (
          <StepContent step={currentStepData} onOpenVM={onOpenVM} />
        )}
      </div>

      {/* Navigation */}
      <div className="flex items-center justify-between px-4 py-3 bg-gray-800 border-t border-gray-700">
        <button
          onClick={() => navigateStep('prev')}
          className="flex items-center gap-1 px-3 py-1.5 text-sm bg-gray-700 text-gray-300 rounded hover:bg-gray-600"
        >
          <ChevronLeft className="w-4 h-4" />
          Prev
        </button>
        <button
          onClick={() => navigateStep('next')}
          className="flex items-center gap-1 px-3 py-1.5 text-sm bg-gray-700 text-gray-300 rounded hover:bg-gray-600"
        >
          Next
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}
```

**Step 2: Create index.ts**

Create `frontend/src/components/walkthrough/index.ts`:

```typescript
export { WalkthroughPanel } from './WalkthroughPanel'
export { PhaseNav } from './PhaseNav'
export { StepList } from './StepList'
export { StepContent } from './StepContent'
export { ProgressBar } from './ProgressBar'
```

**Step 3: Commit**

```bash
git add frontend/src/components/walkthrough/WalkthroughPanel.tsx frontend/src/components/walkthrough/index.ts
git commit -m "feat(walkthrough): create WalkthroughPanel component with progress tracking"
```

---

## Task 13: Create VMSelector Component

**Files:**
- Create: `frontend/src/components/lab/VMSelector.tsx`

**Step 1: Create component**

Create `frontend/src/components/lab/VMSelector.tsx`:

```typescript
// frontend/src/components/lab/VMSelector.tsx
import clsx from 'clsx'
import { Monitor } from 'lucide-react'
import { VM } from '../../types'

interface VMSelectorProps {
  vms: VM[]
  selectedVmId: string | null
  onSelectVM: (vmId: string) => void
}

export function VMSelector({ vms, selectedVmId, onSelectVM }: VMSelectorProps) {
  const runningVms = vms.filter(vm => vm.status === 'running')

  if (runningVms.length === 0) {
    return (
      <div className="flex items-center justify-center px-4 py-3 bg-gray-800 border-t border-gray-700">
        <span className="text-gray-400 text-sm">No running VMs</span>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-2 px-4 py-3 bg-gray-800 border-t border-gray-700 overflow-x-auto">
      <span className="text-gray-400 text-sm flex-shrink-0">VMs:</span>
      {runningVms.map((vm) => (
        <button
          key={vm.id}
          onClick={() => onSelectVM(vm.id)}
          className={clsx(
            'flex items-center gap-1.5 px-3 py-1.5 rounded text-sm whitespace-nowrap transition-colors',
            selectedVmId === vm.id
              ? 'bg-blue-600 text-white'
              : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
          )}
        >
          <Monitor className="w-4 h-4" />
          {vm.hostname}
          {selectedVmId === vm.id && (
            <span className="w-2 h-2 rounded-full bg-green-400" />
          )}
        </button>
      ))}
    </div>
  )
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/lab/VMSelector.tsx
git commit -m "feat(lab): create VMSelector component for switching VM consoles"
```

---

## Task 14: Create ConsoleEmbed Component

**Files:**
- Create: `frontend/src/components/lab/ConsoleEmbed.tsx`
- Create: `frontend/src/components/lab/index.ts`

**Step 1: Create ConsoleEmbed component**

Create `frontend/src/components/lab/ConsoleEmbed.tsx`:

```typescript
// frontend/src/components/lab/ConsoleEmbed.tsx
import { VncConsole } from '../console/VncConsole'
import { Monitor } from 'lucide-react'

interface ConsoleEmbedProps {
  vmId: string | null
  vmHostname: string | null
  token: string
}

export function ConsoleEmbed({ vmId, vmHostname, token }: ConsoleEmbedProps) {
  if (!vmId || !vmHostname) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-900">
        <div className="text-center">
          <Monitor className="w-16 h-16 text-gray-600 mx-auto mb-4" />
          <p className="text-gray-400">Select a VM to view its console</p>
          <p className="text-gray-500 text-sm mt-2">
            Use the VM selector below or click "Open VM" in the walkthrough
          </p>
        </div>
      </div>
    )
  }

  return (
    <VncConsole
      vmId={vmId}
      vmHostname={vmHostname}
      token={token}
      onClose={() => {}}
    />
  )
}
```

**Step 2: Create index.ts**

Create `frontend/src/components/lab/index.ts`:

```typescript
export { VMSelector } from './VMSelector'
export { ConsoleEmbed } from './ConsoleEmbed'
```

**Step 3: Commit**

```bash
git add frontend/src/components/lab/ConsoleEmbed.tsx frontend/src/components/lab/index.ts
git commit -m "feat(lab): create ConsoleEmbed component for embedded VNC"
```

---

## Task 15: Create StudentLab Page

**Files:**
- Create: `frontend/src/pages/StudentLab.tsx`
- Modify: `frontend/src/App.tsx`

**Step 1: Create StudentLab page**

Create `frontend/src/pages/StudentLab.tsx`:

```typescript
// frontend/src/pages/StudentLab.tsx
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels'
import { BookOpen, Loader2, AlertCircle } from 'lucide-react'
import { rangesApi, vmsApi, walkthroughApi } from '../services/api'
import { Range, VM, Walkthrough } from '../types'
import { WalkthroughPanel } from '../components/walkthrough'
import { VMSelector, ConsoleEmbed } from '../components/lab'

export default function StudentLab() {
  const { rangeId } = useParams<{ rangeId: string }>()
  const [range, setRange] = useState<Range | null>(null)
  const [vms, setVMs] = useState<VM[]>([])
  const [walkthrough, setWalkthrough] = useState<Walkthrough | null>(null)
  const [selectedVmId, setSelectedVmId] = useState<string | null>(null)
  const [isCollapsed, setIsCollapsed] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const token = localStorage.getItem('token') || ''
  const selectedVm = vms.find(vm => vm.id === selectedVmId) || null

  useEffect(() => {
    if (!rangeId) {
      setError('No range ID provided')
      setLoading(false)
      return
    }

    const loadData = async () => {
      try {
        const [rangeRes, vmsRes, walkthroughRes] = await Promise.all([
          rangesApi.get(rangeId),
          vmsApi.list(rangeId),
          walkthroughApi.get(rangeId),
        ])

        setRange(rangeRes.data)
        setVMs(vmsRes.data)
        setWalkthrough(walkthroughRes.data.walkthrough)

        // Auto-select first running VM
        const runningVm = vmsRes.data.find(vm => vm.status === 'running')
        if (runningVm) {
          setSelectedVmId(runningVm.id)
        }

        setLoading(false)
      } catch (err: unknown) {
        const error = err as { response?: { data?: { detail?: string } } }
        setError(error.response?.data?.detail || 'Failed to load lab')
        setLoading(false)
      }
    }

    loadData()
  }, [rangeId])

  // Update document title
  useEffect(() => {
    if (range) {
      document.title = `Lab: ${range.name} - CYROID`
    }
    return () => {
      document.title = 'CYROID'
    }
  }, [range])

  const handleOpenVM = (vmHostname: string) => {
    const vm = vms.find(v => v.hostname === vmHostname)
    if (vm) {
      setSelectedVmId(vm.id)
    }
  }

  if (loading) {
    return (
      <div className="h-screen w-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin mx-auto mb-2" />
          <p className="text-gray-400">Loading lab...</p>
        </div>
      </div>
    )
  }

  if (error || !range) {
    return (
      <div className="h-screen w-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center max-w-md px-4">
          <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-3" />
          <p className="text-red-400 mb-2">{error || 'Range not found'}</p>
          <a href="/ranges" className="text-blue-400 hover:underline">
            Return to ranges
          </a>
        </div>
      </div>
    )
  }

  if (!walkthrough) {
    return (
      <div className="h-screen w-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center max-w-md px-4">
          <BookOpen className="w-12 h-12 text-gray-600 mx-auto mb-3" />
          <p className="text-gray-400 mb-2">No walkthrough available for this range</p>
          <p className="text-gray-500 text-sm mb-4">
            An instructor needs to upload an MSEL with a walkthrough section.
          </p>
          <a href={`/ranges/${rangeId}`} className="text-blue-400 hover:underline">
            View range details
          </a>
        </div>
      </div>
    )
  }

  return (
    <div className="h-screen w-screen bg-gray-900 flex flex-col">
      <PanelGroup direction="horizontal" className="flex-1">
        {/* Walkthrough Panel */}
        {!isCollapsed && (
          <>
            <Panel defaultSize={30} minSize={20} maxSize={50}>
              <WalkthroughPanel
                rangeId={rangeId!}
                walkthrough={walkthrough}
                onOpenVM={handleOpenVM}
                onCollapse={() => setIsCollapsed(true)}
              />
            </Panel>
            <PanelResizeHandle className="w-1 bg-gray-700 hover:bg-blue-500 transition-colors cursor-col-resize" />
          </>
        )}

        {/* Console Panel */}
        <Panel defaultSize={isCollapsed ? 100 : 70}>
          <div className="h-full flex flex-col relative">
            {/* Collapse toggle when collapsed */}
            {isCollapsed && (
              <button
                onClick={() => setIsCollapsed(false)}
                className="absolute left-2 top-2 z-10 p-2 bg-gray-800 rounded hover:bg-gray-700"
                title="Show walkthrough"
              >
                <BookOpen className="w-5 h-5 text-blue-400" />
              </button>
            )}

            {/* Console */}
            <div className="flex-1">
              <ConsoleEmbed
                vmId={selectedVmId}
                vmHostname={selectedVm?.hostname || null}
                token={token}
              />
            </div>

            {/* VM Selector */}
            <VMSelector
              vms={vms}
              selectedVmId={selectedVmId}
              onSelectVM={setSelectedVmId}
            />
          </div>
        </Panel>
      </PanelGroup>
    </div>
  )
}
```

**Step 2: Add route to App.tsx**

Modify `frontend/src/App.tsx` - add import and route:

```typescript
// Add import at the top:
import StudentLab from './pages/StudentLab'

// Add route after the StandaloneConsole route (line ~45, before the Layout routes):
      {/* Student Lab - protected but no layout (immersive experience) */}
      <Route
        path="/lab/:rangeId"
        element={
          <ProtectedRoute>
            <StudentLab />
          </ProtectedRoute>
        }
      />
```

**Step 3: Commit**

```bash
git add frontend/src/pages/StudentLab.tsx frontend/src/App.tsx
git commit -m "feat(lab): create StudentLab page with split-pane layout"
```

---

## Task 16: Add "Open Lab" Button to RangeDetail

**Files:**
- Modify: `frontend/src/pages/RangeDetail.tsx`

**Step 1: Add Lab button to header actions**

In `frontend/src/pages/RangeDetail.tsx`:
- Add `BookOpen` to the lucide-react imports
- Find the header section with range action buttons (near status badge)
- Add the Open Lab button for running ranges:

```typescript
{range.status === 'running' && (
  <a
    href={`/lab/${range.id}`}
    target="_blank"
    rel="noopener noreferrer"
    className="inline-flex items-center gap-2 px-3 py-1.5 bg-purple-600 text-white rounded hover:bg-purple-700"
  >
    <BookOpen className="w-4 h-4" />
    Open Lab
  </a>
)}
```

**Step 2: Commit**

```bash
git add frontend/src/pages/RangeDetail.tsx
git commit -m "feat(range): add Open Lab button to RangeDetail for running ranges"
```

---

## Task 17: Version Bump and Release

**Files:**
- Modify: `backend/cyroid/config.py`
- Modify: `CHANGELOG.md`

**Step 1: Update version**

Update `backend/cyroid/config.py`:
```python
app_version: str = "0.4.11"
```

**Step 2: Update CHANGELOG**

Add to `CHANGELOG.md` after the `[0.4.10]` section:

```markdown
## [0.4.11] - 2026-01-17

### Added

- **Student Lab Page with Walkthrough Panel** ([#8](../../issues/8)): New `/lab/:rangeId` page provides a student-focused experience with integrated step-by-step walkthrough alongside VNC consoles.
  - WalkthroughPanel: Collapsible left panel with phase navigation, step checklist, and markdown content
  - Progress tracking: Local storage + optional server sync with auto-save
  - VM integration: "Open VM" button switches console to referenced VM
  - Split-pane layout: Resizable panels with embedded VNC console
  - Markdown rendering: Code blocks, blockquotes (tips/warnings), headers
  - MSEL extension: Walkthrough content authored in YAML `walkthrough:` section
  - New WalkthroughProgress model for server-side progress persistence
  - "Open Lab" button on RangeDetail page for running ranges
```

**Step 3: Commit and tag**

```bash
git add backend/cyroid/config.py CHANGELOG.md
git commit -m "release: v0.4.11 - Student Lab with Walkthrough Panel"
git tag -a v0.4.11 -m "v0.4.11 - Student Lab with Walkthrough Panel (#8)"
```

**Step 4: Close issue**

```bash
gh issue close 8 -c "Implemented in v0.4.11 - Student lab page with walkthrough panel, VNC console integration, and progress tracking"
```

---

## Summary

This implementation adds:

1. **Backend**:
   - `walkthrough` JSON column on MSEL model
   - `WalkthroughProgress` model for tracking student progress
   - MSEL parser extended to extract `walkthrough:` YAML section
   - New API endpoints: `GET/PUT /ranges/{id}/walkthrough/progress`

2. **Frontend**:
   - New `/lab/:rangeId` route for student lab experience
   - `WalkthroughPanel` with phase navigation, step list, and markdown content
   - `VMSelector` for switching between running VMs
   - `ConsoleEmbed` for embedded VNC console
   - Progress tracking with localStorage + server sync
   - Resizable split-pane layout

3. **Dependencies**:
   - `react-resizable-panels` for split-pane layout
   - `react-markdown` + `remark-gfm` for markdown rendering
