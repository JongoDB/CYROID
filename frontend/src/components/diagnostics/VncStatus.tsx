// frontend/src/components/diagnostics/VncStatus.tsx
import { useState, useEffect } from 'react'
import { Monitor, CheckCircle, XCircle, AlertTriangle, RefreshCw, Wrench, ExternalLink } from 'lucide-react'
import { rangesApi, VncStatusResponse, VncVmStatus } from '../../services/api'
import { toast } from '../../stores/toastStore'

interface VncStatusProps {
  rangeId: string
  onRefresh?: () => void
}

export function VncStatus({ rangeId, onRefresh }: VncStatusProps) {
  const [vncStatus, setVncStatus] = useState<VncStatusResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [repairing, setRepairing] = useState(false)
  const [expanded, setExpanded] = useState(false)

  const fetchVncStatus = async () => {
    setLoading(true)
    try {
      const response = await rangesApi.getVncStatus(rangeId)
      setVncStatus(response.data)
    } catch (error) {
      console.error('Failed to fetch VNC status:', error)
      toast.error('Failed to fetch VNC status')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchVncStatus()
  }, [rangeId])

  const handleRepairVnc = async () => {
    setRepairing(true)
    try {
      const response = await rangesApi.repairVnc(rangeId)
      toast.success(response.data.message)
      await fetchVncStatus()
      onRefresh?.()
    } catch (error: unknown) {
      const message = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to repair VNC'
      toast.error(message)
    } finally {
      setRepairing(false)
    }
  }

  const getStatusIcon = (vm: VncVmStatus) => {
    if (vm.issues.length > 0) {
      return <XCircle className="w-4 h-4 text-red-500" />
    }
    if (vm.has_db_mapping && vm.vnc_url) {
      return <CheckCircle className="w-4 h-4 text-green-500" />
    }
    return <AlertTriangle className="w-4 h-4 text-yellow-500" />
  }

  if (loading && !vncStatus) {
    return (
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
        <div className="flex items-center gap-2 text-gray-400">
          <RefreshCw className="w-4 h-4 animate-spin" />
          Loading VNC status...
        </div>
      </div>
    )
  }

  if (!vncStatus) {
    return null
  }

  const hasIssues = vncStatus.summary.vms_with_issues > 0
  const isDind = vncStatus.is_dind

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
      {/* Header */}
      <div
        className="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-750"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3">
          <Monitor className={hasIssues ? 'w-5 h-5 text-yellow-500' : 'w-5 h-5 text-green-500'} />
          <div>
            <h3 className="font-medium text-white">VNC Console Status</h3>
            <p className="text-sm text-gray-400">
              {vncStatus.summary.vms_with_vnc}/{vncStatus.summary.total_vms} VMs with VNC configured
              {hasIssues && ` (${vncStatus.summary.vms_with_issues} with issues)`}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {hasIssues && (
            <span className="px-2 py-1 text-xs font-medium rounded-full bg-yellow-500/20 text-yellow-400">
              Issues Detected
            </span>
          )}
          <button
            onClick={(e) => {
              e.stopPropagation()
              fetchVncStatus()
            }}
            className="p-1 text-gray-400 hover:text-white rounded"
            disabled={loading}
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Expanded Content */}
      {expanded && (
        <div className="border-t border-gray-700 p-4 space-y-4">
          {/* DinD Info */}
          {isDind && (
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-gray-400">DinD Container:</span>
                <span className="ml-2 text-white font-mono">{vncStatus.dind_container_id || 'N/A'}</span>
              </div>
              <div>
                <span className="text-gray-400">DinD IP:</span>
                <span className="ml-2 text-white font-mono">{vncStatus.dind_mgmt_ip || 'N/A'}</span>
              </div>
              <div>
                <span className="text-gray-400">Traefik Routes:</span>
                <span className={`ml-2 ${vncStatus.traefik_routes_exist ? 'text-green-400' : 'text-red-400'}`}>
                  {vncStatus.traefik_routes_exist ? 'Configured' : 'Missing'}
                </span>
              </div>
              <div>
                <span className="text-gray-400">VNC Mappings:</span>
                <span className="ml-2 text-white">{vncStatus.vnc_mappings_count}</span>
              </div>
              <div>
                <span className="text-gray-400">Socat Proxies:</span>
                <span className={`ml-2 ${vncStatus.socat_processes && vncStatus.socat_processes.length > 0 && !vncStatus.socat_processes[0].includes('No socat') ? 'text-green-400' : 'text-yellow-400'}`}>
                  {vncStatus.socat_processes && vncStatus.socat_processes.length > 0 && !vncStatus.socat_processes[0].includes('No socat') ? `${vncStatus.socat_processes.filter(p => p.trim()).length} running` : 'None running'}
                </span>
              </div>
            </div>
          )}

          {/* VM VNC Status Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-400 border-b border-gray-700">
                  <th className="pb-2 pr-4">Status</th>
                  <th className="pb-2 pr-4">VM</th>
                  <th className="pb-2 pr-4">IP</th>
                  <th className="pb-2 pr-4">Proxy Port</th>
                  <th className="pb-2 pr-4">Issues</th>
                  <th className="pb-2">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700">
                {vncStatus.vms.map((vm) => (
                  <tr key={vm.vm_id} className="text-gray-200">
                    <td className="py-2 pr-4">{getStatusIcon(vm)}</td>
                    <td className="py-2 pr-4">
                      <div>
                        <span className="font-medium">{vm.hostname}</span>
                        <span className="ml-2 text-xs text-gray-500">({vm.vm_status})</span>
                      </div>
                    </td>
                    <td className="py-2 pr-4 font-mono text-xs">{vm.ip_address || '-'}</td>
                    <td className="py-2 pr-4">
                      {vm.proxy_port ? (
                        <span className="font-mono text-xs">{vm.proxy_port}</span>
                      ) : (
                        <span className="text-gray-500">-</span>
                      )}
                    </td>
                    <td className="py-2 pr-4">
                      {vm.issues.length > 0 ? (
                        <ul className="text-xs text-red-400 list-disc list-inside">
                          {vm.issues.map((issue, i) => (
                            <li key={i}>{issue}</li>
                          ))}
                        </ul>
                      ) : (
                        <span className="text-green-400 text-xs">None</span>
                      )}
                    </td>
                    <td className="py-2">
                      {vm.vnc_url && vm.vm_status === 'running' && (
                        <a
                          href={vm.vnc_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-xs text-cyan-400 hover:text-cyan-300"
                        >
                          <ExternalLink className="w-3 h-3" />
                          Open
                        </a>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Repair Button */}
          {isDind && hasIssues && (
            <div className="pt-2 border-t border-gray-700">
              <button
                onClick={handleRepairVnc}
                disabled={repairing}
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-yellow-600 hover:bg-yellow-500 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {repairing ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    Repairing VNC...
                  </>
                ) : (
                  <>
                    <Wrench className="w-4 h-4" />
                    Repair VNC Configuration
                  </>
                )}
              </button>
              <p className="mt-2 text-xs text-gray-400">
                This will recreate iptables DNAT rules, regenerate Traefik routes, and update the database.
              </p>
            </div>
          )}

          {/* Socat Processes (collapsible) */}
          {isDind && vncStatus.socat_processes && vncStatus.socat_processes.length > 0 && (
            <details className="pt-2">
              <summary className="text-sm text-gray-400 cursor-pointer hover:text-gray-300">
                View Socat Proxy Processes ({vncStatus.socat_processes.filter(p => p.trim()).length} lines)
              </summary>
              <pre className="mt-2 p-2 bg-gray-900 rounded text-xs font-mono text-gray-300 overflow-x-auto">
                {vncStatus.socat_processes.join('\n')}
              </pre>
            </details>
          )}

          {/* Network Interfaces (collapsible) */}
          {isDind && vncStatus.network_interfaces && vncStatus.network_interfaces.length > 0 && (
            <details className="pt-2">
              <summary className="text-sm text-gray-400 cursor-pointer hover:text-gray-300">
                View DinD Network Interfaces ({vncStatus.network_interfaces.filter(i => i.trim()).length} lines)
              </summary>
              <pre className="mt-2 p-2 bg-gray-900 rounded text-xs font-mono text-gray-300 overflow-x-auto">
                {vncStatus.network_interfaces.join('\n')}
              </pre>
            </details>
          )}
        </div>
      )}
    </div>
  )
}
