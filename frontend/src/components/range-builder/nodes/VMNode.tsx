// frontend/src/components/range-builder/nodes/VMNode.tsx
import { memo } from 'react'
import { Handle, Position } from '@xyflow/react'
import { Server } from 'lucide-react'
import clsx from 'clsx'
import type { VM, BaseImage } from '../../../types'

interface VMNodeData {
  vm: VM
  baseImage?: BaseImage
}

interface VMNodeProps {
  data: VMNodeData
}

export const VMNode = memo(({ data }: VMNodeProps) => {
  const { vm, baseImage } = data

  const statusColors: Record<string, string> = {
    running: 'border-green-500 bg-green-50',
    stopped: 'border-gray-400 bg-gray-50',
    pending: 'border-yellow-500 bg-yellow-50',
    creating: 'border-blue-500 bg-blue-50',
    error: 'border-red-500 bg-red-50',
  }

  return (
    <div
      className={clsx(
        'px-3 py-2 rounded-lg border-2 shadow-sm min-w-[140px]',
        statusColors[vm.status.toLowerCase()] || 'border-gray-300 bg-white'
      )}
    >
      <Handle type="target" position={Position.Top} className="w-2 h-2" />

      <div className="flex items-center gap-2">
        <Server className={clsx(
          'w-4 h-4',
          baseImage?.os_type === 'linux' ? 'text-orange-600' :
          baseImage?.os_type === 'windows' ? 'text-blue-600' : 'text-gray-600'
        )} />
        <div className="flex-1 min-w-0">
          <div className="text-xs font-semibold text-gray-900 truncate">
            {vm.hostname}
          </div>
          <div className="text-[10px] text-gray-500 truncate">
            {vm.ip_address}
          </div>
        </div>
      </div>
      
      <div className="mt-1 flex items-center gap-1 text-[10px] text-gray-400">
        <span>{vm.cpu} CPU</span>
        <span className="mx-0.5">|</span>
        <span>{vm.ram_mb / 1024}GB</span>
      </div>

      <Handle type="source" position={Position.Bottom} className="w-2 h-2" />
    </div>
  )
})

VMNode.displayName = 'VMNode'
