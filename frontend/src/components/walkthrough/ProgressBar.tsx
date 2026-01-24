// frontend/src/components/walkthrough/ProgressBar.tsx
import { Cloud, Check } from 'lucide-react'

interface ProgressBarProps {
  completed: number
  total: number
  isDirty: boolean
  isSyncing: boolean
  onSave: () => void
}

export function ProgressBar({ completed, total, isDirty, isSyncing }: ProgressBarProps) {
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

      {/* Subtle auto-save status indicator */}
      <div className="flex items-center gap-1 text-xs text-gray-500">
        {isSyncing ? (
          <>
            <Cloud className="w-3.5 h-3.5 animate-pulse text-blue-400" />
            <span className="text-blue-400">Saving...</span>
          </>
        ) : isDirty ? (
          <span className="text-gray-500">•</span>
        ) : (
          <>
            <Check className="w-3.5 h-3.5 text-green-500" />
          </>
        )}
      </div>
    </div>
  )
}
