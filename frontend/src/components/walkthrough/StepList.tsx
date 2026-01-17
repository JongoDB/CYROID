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
