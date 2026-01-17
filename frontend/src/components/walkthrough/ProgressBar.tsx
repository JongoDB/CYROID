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
