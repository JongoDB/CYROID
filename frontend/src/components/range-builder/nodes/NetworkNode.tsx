// frontend/src/components/range-builder/nodes/NetworkNode.tsx
import { memo } from 'react'
import { Handle, Position } from '@xyflow/react'
import { Network as NetworkIcon } from 'lucide-react'
import clsx from 'clsx'
import type { Network } from '../../../types'

interface NetworkNodeData {
  network: Network
}

interface NetworkNodeProps {
  data: NetworkNodeData
}

export const NetworkNode = memo(({ data }: NetworkNodeProps) => {
  const { network } = data

  const isolationColors: Record<string, string> = {
    complete: 'border-red-400 bg-red-50',
    controlled: 'border-yellow-400 bg-yellow-50',
    open: 'border-green-400 bg-green-50',
  }

  return (
    <div
      className={clsx(
        'px-4 py-3 rounded-xl border-2 shadow-md min-w-[300px] min-h-[200px]',
        isolationColors[network.isolation_level] || 'border-gray-300 bg-gray-50'
      )}
    >
      <Handle type="target" position={Position.Left} className="w-2 h-2" />
      
      <div className="flex items-center gap-2 mb-2 pb-2 border-b border-gray-200">
        <NetworkIcon className="w-5 h-5 text-gray-600" />
        <div className="flex-1">
          <div className="text-sm font-semibold text-gray-900">{network.name}</div>
          <div className="text-xs text-gray-500">{network.subnet}</div>
        </div>
        <span className={clsx(
          'px-2 py-0.5 text-[10px] font-medium rounded',
          network.isolation_level === 'complete' ? 'bg-red-100 text-red-700' :
          network.isolation_level === 'controlled' ? 'bg-yellow-100 text-yellow-700' :
          'bg-green-100 text-green-700'
        )}>
          {network.isolation_level}
        </span>
      </div>
      
      <div className="text-[10px] text-gray-400">
        Gateway: {network.gateway}
        {network.dns_servers && ` | DNS: ${network.dns_servers}`}
      </div>

      <Handle type="source" position={Position.Right} className="w-2 h-2" />
    </div>
  )
})

NetworkNode.displayName = 'NetworkNode'
