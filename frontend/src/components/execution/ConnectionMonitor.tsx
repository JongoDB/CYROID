// frontend/src/components/execution/ConnectionMonitor.tsx
import { useEffect, useState } from 'react'
import { Plug, ArrowRight, RefreshCw, Filter } from 'lucide-react'
import { Connection, ConnectionState, VM } from '../../types'
import { connectionsApi } from '../../services/api'
import clsx from 'clsx'

interface Props {
  rangeId: string
  vms: VM[]
}

const stateColors: Record<ConnectionState, string> = {
  established: 'text-green-500',
  closed: 'text-gray-400',
  timeout: 'text-yellow-500',
  reset: 'text-red-500',
}

const protocolColors: Record<string, string> = {
  tcp: 'bg-blue-100 text-blue-700',
  udp: 'bg-purple-100 text-purple-700',
  icmp: 'bg-orange-100 text-orange-700',
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatTime(timestamp: string): string {
  return new Date(timestamp).toLocaleTimeString()
}

export function ConnectionMonitor({ rangeId, vms }: Props) {
  const [connections, setConnections] = useState<Connection[]>([])
  const [loading, setLoading] = useState(true)
  const [activeOnly, setActiveOnly] = useState(false)
  const [total, setTotal] = useState(0)

  const vmMap = new Map(vms.map(vm => [vm.id, vm]))

  useEffect(() => {
    loadConnections()
    const interval = setInterval(loadConnections, 5000)
    return () => clearInterval(interval)
  }, [rangeId, activeOnly])

  const loadConnections = async () => {
    try {
      const response = await connectionsApi.getRangeConnections(rangeId, 50, 0, activeOnly)
      setConnections(response.data.connections)
      setTotal(response.data.total)
    } catch (error) {
      console.error('Failed to load connections:', error)
    } finally {
      setLoading(false)
    }
  }

  const getVMName = (vmId: string | null): string => {
    if (!vmId) return 'External'
    const vm = vmMap.get(vmId)
    return vm?.hostname || 'Unknown'
  }

  const activeConnections = connections.filter(c => c.state === 'established').length

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="px-4 py-3 border-b">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Plug className="w-5 h-5 text-gray-500" />
            <h3 className="font-medium">Network Connections</h3>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 text-xs">
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                {activeConnections} active
              </span>
              <span className="text-gray-400">/ {total} total</span>
            </div>
            <button
              onClick={() => setActiveOnly(!activeOnly)}
              className={clsx(
                'flex items-center gap-1 px-2 py-1 text-xs rounded',
                activeOnly ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600'
              )}
            >
              <Filter className="w-3 h-3" />
              {activeOnly ? 'Active only' : 'All'}
            </button>
            <button
              onClick={loadConnections}
              className="p-1 hover:bg-gray-100 rounded"
            >
              <RefreshCw className={clsx('w-4 h-4 text-gray-500', loading && 'animate-spin')} />
            </button>
          </div>
        </div>
      </div>

      <div className="max-h-64 overflow-y-auto">
        {loading && connections.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            <div className="w-6 h-6 border-2 border-gray-300 border-t-blue-500 rounded-full animate-spin mx-auto" />
            <p className="mt-2 text-sm">Loading connections...</p>
          </div>
        ) : connections.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            <Plug className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">No connections recorded</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
              <tr>
                <th className="px-3 py-2 text-left">Source</th>
                <th className="px-3 py-2 text-center"></th>
                <th className="px-3 py-2 text-left">Destination</th>
                <th className="px-3 py-2 text-center">Protocol</th>
                <th className="px-3 py-2 text-center">State</th>
                <th className="px-3 py-2 text-right">Data</th>
                <th className="px-3 py-2 text-right">Time</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {connections.map((conn) => (
                <tr key={conn.id} className="hover:bg-gray-50">
                  <td className="px-3 py-2">
                    <div className="font-mono text-xs">
                      <span className="text-gray-900">{getVMName(conn.src_vm_id)}</span>
                      <span className="text-gray-400">:{conn.src_port}</span>
                    </div>
                    <div className="text-xs text-gray-400">{conn.src_ip}</div>
                  </td>
                  <td className="px-2 py-2 text-center">
                    <ArrowRight className="w-4 h-4 text-gray-300 mx-auto" />
                  </td>
                  <td className="px-3 py-2">
                    <div className="font-mono text-xs">
                      <span className="text-gray-900">{getVMName(conn.dst_vm_id)}</span>
                      <span className="text-gray-400">:{conn.dst_port}</span>
                    </div>
                    <div className="text-xs text-gray-400">{conn.dst_ip}</div>
                  </td>
                  <td className="px-3 py-2 text-center">
                    <span className={clsx(
                      'px-1.5 py-0.5 text-xs font-medium rounded uppercase',
                      protocolColors[conn.protocol]
                    )}>
                      {conn.protocol}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-center">
                    <span className={clsx('text-xs capitalize', stateColors[conn.state])}>
                      {conn.state}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right text-xs text-gray-500">
                    <div>{formatBytes(conn.bytes_sent)}</div>
                    <div>{formatBytes(conn.bytes_received)}</div>
                  </td>
                  <td className="px-3 py-2 text-right text-xs text-gray-400">
                    {formatTime(conn.started_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
