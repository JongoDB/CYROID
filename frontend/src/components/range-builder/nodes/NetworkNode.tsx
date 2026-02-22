// frontend/src/components/range-builder/nodes/NetworkNode.tsx
import { memo } from 'react'
import { Handle, Position } from '@xyflow/react'
import { Network as NetworkIcon, Shield, Globe, Wifi } from 'lucide-react'
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

  return (
    <div
      className={clsx(
        'px-4 py-3 rounded-xl border-2 shadow-md min-w-[300px] min-h-[200px]',
        network.is_isolated
          ? 'border-blue-400 bg-blue-50'
          : 'border-green-400 bg-green-50'
      )}
    >
      <Handle type="target" position={Position.Left} className="w-2 h-2" />

      <div className="flex items-center gap-2 mb-2 pb-2 border-b border-gray-200">
        <NetworkIcon className="w-5 h-5 text-gray-600" />
        <div className="flex-1">
          <div className="text-sm font-semibold text-gray-900">{network.name}</div>
          <div className="text-xs text-gray-500">{network.subnet}</div>
        </div>
        <div className="flex items-center gap-1">
          <span className={clsx(
            'flex items-center gap-1 px-2 py-0.5 text-[10px] font-medium rounded',
            network.is_isolated ? 'bg-blue-100 text-blue-700' : 'bg-green-100 text-green-700'
          )}>
            <Shield className="w-3 h-3" fill={network.is_isolated ? 'currentColor' : 'none'} />
            {network.is_isolated ? 'Isolated' : 'Open'}
          </span>
          <span className={clsx(
            'flex items-center gap-1 px-2 py-0.5 text-[10px] font-medium rounded',
            network.internet_enabled ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
          )}>
            <Globe className="w-3 h-3" fill={network.internet_enabled ? 'currentColor' : 'none'} />
            {network.internet_enabled ? 'Internet' : 'Offline'}
          </span>
          <span className={clsx(
            'flex items-center gap-1 px-2 py-0.5 text-[10px] font-medium rounded',
            network.dhcp_enabled ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-500'
          )}>
            <Wifi className="w-3 h-3" fill={network.dhcp_enabled ? 'currentColor' : 'none'} />
            {network.dhcp_enabled ? 'DHCP' : 'Static'}
          </span>
        </div>
      </div>

      <div className="text-[10px] text-gray-400">
        Gateway: {network.gateway}
        {network.dns_servers && ` | DNS: ${network.dns_servers}`}
        {network.dns_search && ` | Search: ${network.dns_search}`}
      </div>

      <Handle type="source" position={Position.Right} className="w-2 h-2" />
    </div>
  )
})

NetworkNode.displayName = 'NetworkNode'
