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
        const isComplete = completed === total && total > 0
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
