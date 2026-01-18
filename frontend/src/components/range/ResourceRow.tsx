// frontend/src/components/range/ResourceRow.tsx
import { StatusIcon } from './StatusIcon'
import clsx from 'clsx'

interface Props {
  name: string
  detail?: string
  status: string
  statusDetail?: string
  durationMs?: number
}

export function ResourceRow({ name, detail, status, statusDetail, durationMs }: Props) {
  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}ms`
    return `${(ms / 1000).toFixed(1)}s`
  }

  const getStatusText = () => {
    if (statusDetail) return statusDetail
    switch (status) {
      case 'pending': return 'Pending'
      case 'creating': return 'Creating...'
      case 'starting': return 'Starting...'
      case 'running': return 'Running'
      case 'created': return 'Created'
      case 'failed': return 'Failed'
      default: return status
    }
  }

  return (
    <div className={clsx(
      'flex items-center py-2 px-4 border-b border-gray-700 last:border-b-0',
      status === 'failed' && 'bg-red-900/20'
    )}>
      <StatusIcon status={status} className="mr-3 flex-shrink-0" />
      <span className="w-32 font-medium text-white truncate">{name}</span>
      <span className="w-36 text-gray-400 text-sm truncate">{detail || '--'}</span>
      <span className={clsx(
        'flex-1 text-sm truncate',
        status === 'failed' ? 'text-red-400' :
        status === 'running' || status === 'created' ? 'text-green-400' :
        status === 'creating' || status === 'starting' ? 'text-blue-400' :
        'text-gray-400'
      )}>
        {getStatusText()}
      </span>
      <span className="w-16 text-right text-gray-500 text-sm">
        {durationMs ? formatDuration(durationMs) : '--'}
      </span>
    </div>
  )
}
