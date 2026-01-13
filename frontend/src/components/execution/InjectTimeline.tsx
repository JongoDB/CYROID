// frontend/src/components/execution/InjectTimeline.tsx
import { useState } from 'react'
import {
  Play, SkipForward, Clock, CheckCircle, XCircle,
  AlertCircle, Loader2, ChevronDown, ChevronUp, FileCode
} from 'lucide-react'
import { Inject, InjectStatus, MSEL } from '../../types'
import { mselApi } from '../../services/api'
import clsx from 'clsx'

interface Props {
  msel: MSEL
  onInjectUpdate: () => void
}

const statusConfig: Record<InjectStatus, { icon: React.ReactNode; color: string; bgColor: string }> = {
  pending: {
    icon: <Clock className="w-4 h-4" />,
    color: 'text-gray-500',
    bgColor: 'bg-gray-100'
  },
  executing: {
    icon: <Loader2 className="w-4 h-4 animate-spin" />,
    color: 'text-blue-500',
    bgColor: 'bg-blue-100'
  },
  completed: {
    icon: <CheckCircle className="w-4 h-4" />,
    color: 'text-green-500',
    bgColor: 'bg-green-100'
  },
  failed: {
    icon: <XCircle className="w-4 h-4" />,
    color: 'text-red-500',
    bgColor: 'bg-red-100'
  },
  skipped: {
    icon: <SkipForward className="w-4 h-4" />,
    color: 'text-yellow-500',
    bgColor: 'bg-yellow-100'
  },
}

function formatTime(minutes: number): string {
  const hours = Math.floor(minutes / 60)
  const mins = minutes % 60
  return `T+${hours.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}`
}

function InjectCard({ inject, onExecute, onSkip }: {
  inject: Inject
  onExecute: () => void
  onSkip: () => void
}) {
  const [expanded, setExpanded] = useState(false)
  const [executing, setExecuting] = useState(false)
  const config = statusConfig[inject.status]

  const handleExecute = async () => {
    setExecuting(true)
    await onExecute()
    setExecuting(false)
  }

  return (
    <div className={clsx(
      'border rounded-lg overflow-hidden',
      inject.status === 'pending' ? 'border-gray-200' : 'border-l-4',
      inject.status === 'completed' && 'border-l-green-500',
      inject.status === 'failed' && 'border-l-red-500',
      inject.status === 'skipped' && 'border-l-yellow-500',
      inject.status === 'executing' && 'border-l-blue-500'
    )}>
      <div
        className="flex items-center justify-between p-3 bg-white cursor-pointer hover:bg-gray-50"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3">
          <div className={clsx('p-1.5 rounded', config.bgColor, config.color)}>
            {executing ? <Loader2 className="w-4 h-4 animate-spin" /> : config.icon}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono text-gray-500">
                {formatTime(inject.inject_time_minutes)}
              </span>
              <span className="text-xs text-gray-400">|</span>
              <span className="text-sm font-medium">{inject.title}</span>
            </div>
            {inject.description && (
              <p className="text-xs text-gray-500 mt-0.5 line-clamp-1">
                {inject.description}
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {inject.status === 'pending' && (
            <>
              <button
                onClick={(e) => { e.stopPropagation(); handleExecute() }}
                disabled={executing}
                className="flex items-center gap-1 px-2 py-1 text-xs bg-green-500 text-white rounded hover:bg-green-600 disabled:opacity-50"
              >
                <Play className="w-3 h-3" />
                Execute
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); onSkip() }}
                disabled={executing}
                className="flex items-center gap-1 px-2 py-1 text-xs bg-gray-200 text-gray-700 rounded hover:bg-gray-300 disabled:opacity-50"
              >
                <SkipForward className="w-3 h-3" />
                Skip
              </button>
            </>
          )}
          {inject.executed_at && (
            <span className="text-xs text-gray-400">
              {new Date(inject.executed_at).toLocaleTimeString()}
            </span>
          )}
          {expanded ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
        </div>
      </div>

      {expanded && inject.actions.length > 0 && (
        <div className="border-t bg-gray-50 p-3 space-y-2">
          <h4 className="text-xs font-medium text-gray-500 uppercase">Actions</h4>
          {inject.actions.map((action, idx) => (
            <div key={idx} className="flex items-start gap-2 text-sm">
              <FileCode className="w-4 h-4 text-gray-400 mt-0.5" />
              <div>
                <span className="font-medium capitalize">{action.type.replace('_', ' ')}</span>
                <span className="text-gray-500"> on </span>
                <span className="font-mono text-blue-600">{action.target_vm}</span>
                {action.path && (
                  <span className="text-gray-500"> at <code className="bg-gray-200 px-1 rounded">{action.path}</code></span>
                )}
                {action.command && (
                  <span className="text-gray-500">: <code className="bg-gray-200 px-1 rounded">{action.command}</code></span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function InjectTimeline({ msel, onInjectUpdate }: Props) {
  const [error, setError] = useState<string | null>(null)

  const handleExecute = async (injectId: string) => {
    setError(null)
    try {
      await mselApi.executeInject(injectId)
      onInjectUpdate()
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to execute inject'
      setError(errorMessage)
    }
  }

  const handleSkip = async (injectId: string) => {
    setError(null)
    try {
      await mselApi.skipInject(injectId)
      onInjectUpdate()
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to skip inject'
      setError(errorMessage)
    }
  }

  const pendingCount = msel.injects.filter(i => i.status === 'pending').length
  const completedCount = msel.injects.filter(i => i.status === 'completed').length
  const failedCount = msel.injects.filter(i => i.status === 'failed').length

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="px-4 py-3 border-b">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-medium">{msel.name}</h3>
            <p className="text-xs text-gray-500">{msel.injects.length} injects</p>
          </div>
          <div className="flex items-center gap-3 text-xs">
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 bg-gray-300 rounded-full" />
              {pendingCount} pending
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 bg-green-500 rounded-full" />
              {completedCount} completed
            </span>
            {failedCount > 0 && (
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 bg-red-500 rounded-full" />
                {failedCount} failed
              </span>
            )}
          </div>
        </div>
      </div>

      {error && (
        <div className="mx-4 mt-3 flex items-center gap-2 p-2 bg-red-50 text-red-700 rounded text-sm">
          <AlertCircle className="w-4 h-4" />
          {error}
        </div>
      )}

      <div className="p-4 space-y-2 max-h-96 overflow-y-auto">
        {msel.injects.map((inject) => (
          <InjectCard
            key={inject.id}
            inject={inject}
            onExecute={() => handleExecute(inject.id)}
            onSkip={() => handleSkip(inject.id)}
          />
        ))}
      </div>
    </div>
  )
}
