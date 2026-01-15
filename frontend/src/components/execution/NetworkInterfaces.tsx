// frontend/src/components/execution/NetworkInterfaces.tsx
import { useEffect, useState } from 'react'
import { Network as NetworkIcon, Server, RefreshCw, Wifi, Plus, Trash2 } from 'lucide-react'
import { VM, Network } from '../../types'
import { vmsApi, networksApi, VMNetworkInfo, NetworkInterface } from '../../services/api'
import clsx from 'clsx'

interface Props {
  rangeId: string
  vms: VM[]
  networks?: Network[]
}

export function NetworkInterfaces({ rangeId, vms, networks: propNetworks }: Props) {
  const [vmNetworks, setVmNetworks] = useState<VMNetworkInfo[]>([])
  const [networks, setNetworks] = useState<Network[]>(propNetworks || [])
  const [loading, setLoading] = useState(true)
  const [addingNetwork, setAddingNetwork] = useState<{
    vmId: string
    networkId: string
    ipAddress: string
  } | null>(null)
  const [showAddForm, setShowAddForm] = useState<string | null>(null)

  useEffect(() => {
    loadNetworkData()
    const interval = setInterval(loadNetworkData, 10000) // Refresh every 10 seconds
    return () => clearInterval(interval)
  }, [rangeId, vms])

  useEffect(() => {
    if (!propNetworks) {
      loadNetworks()
    }
  }, [rangeId, propNetworks])

  const loadNetworks = async () => {
    try {
      const response = await networksApi.list(rangeId)
      setNetworks(response.data)
    } catch (error) {
      console.error('Failed to load networks:', error)
    }
  }

  const loadNetworkData = async () => {
    try {
      const response = await vmsApi.getRangeNetworks(rangeId)
      setVmNetworks(response.data.vms)
    } catch (error) {
      console.error('Failed to load network interfaces:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleAddNetwork = async (vmId: string, networkId: string, ipAddress: string) => {
    setAddingNetwork({ vmId, networkId, ipAddress })
    try {
      await vmsApi.addNetwork(vmId, networkId, ipAddress || undefined)
      await loadNetworkData()
      setShowAddForm(null)
    } catch (error) {
      console.error('Failed to add network:', error)
    } finally {
      setAddingNetwork(null)
    }
  }

  const handleRemoveNetwork = async (vmId: string, networkId: string) => {
    try {
      await vmsApi.removeNetwork(vmId, networkId)
      await loadNetworkData()
    } catch (error) {
      console.error('Failed to remove network:', error)
    }
  }

  // Get VM by ID
  const getVM = (vmId: string) => vms.find(vm => vm.id === vmId)

  // Get available networks that aren't already connected to a VM
  const getAvailableNetworks = (vmInterfaces: NetworkInterface[]) => {
    const connectedNetworkIds = new Set(
      vmInterfaces
        .filter(iface => iface.cyroid_network_id)
        .map(iface => iface.cyroid_network_id)
    )
    return networks.filter(net => !connectedNetworkIds.has(net.id))
  }

  // Calculate total interfaces
  const totalInterfaces = vmNetworks.reduce(
    (acc, vm) => acc + vm.interfaces.length,
    0
  )

  const managementCount = vmNetworks.reduce(
    (acc, vm) => acc + vm.interfaces.filter(i => i.is_management).length,
    0
  )

  const rangeCount = totalInterfaces - managementCount

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="px-4 py-3 border-b">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <NetworkIcon className="w-5 h-5 text-gray-500" />
            <h3 className="font-medium">Network Interfaces</h3>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 text-xs">
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 bg-blue-500 rounded-full" />
                {managementCount} mgmt
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 bg-green-500 rounded-full" />
                {rangeCount} range
              </span>
            </div>
            <button
              onClick={loadNetworkData}
              className="p-1 hover:bg-gray-100 rounded"
              title="Refresh"
            >
              <RefreshCw className={clsx('w-4 h-4 text-gray-500', loading && 'animate-spin')} />
            </button>
          </div>
        </div>
      </div>

      <div className="max-h-80 overflow-y-auto">
        {loading && vmNetworks.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            <div className="w-6 h-6 border-2 border-gray-300 border-t-blue-500 rounded-full animate-spin mx-auto" />
            <p className="mt-2 text-sm">Loading network interfaces...</p>
          </div>
        ) : vmNetworks.length === 0 || vmNetworks.every(vm => vm.interfaces.length === 0) ? (
          <div className="p-8 text-center text-gray-500">
            <NetworkIcon className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">No network interfaces</p>
            <p className="text-xs mt-1">Start VMs to see their network connections</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {vmNetworks.map((vmNet) => {
              const vm = getVM(vmNet.vm_id)
              if (!vm) return null

              const availableNetworks = getAvailableNetworks(vmNet.interfaces)

              return (
                <div key={vmNet.vm_id} className="p-3">
                  {/* VM Header */}
                  <div className="flex items-center gap-2 mb-2">
                    <Server className="w-4 h-4 text-orange-500" />
                    <span className="font-medium text-sm">{vmNet.hostname}</span>
                    <span className={clsx(
                      'text-xs px-1.5 py-0.5 rounded',
                      vmNet.status === 'running' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
                    )}>
                      {vmNet.status}
                    </span>
                  </div>

                  {/* Network Interfaces */}
                  {vmNet.interfaces.length === 0 ? (
                    <div className="text-xs text-gray-400 ml-6">No network interfaces</div>
                  ) : (
                    <div className="space-y-1.5 ml-6">
                      {vmNet.interfaces.map((iface, idx) => (
                        <div
                          key={`${vmNet.vm_id}-${iface.network_name}-${idx}`}
                          className="flex items-center justify-between text-xs bg-gray-50 rounded px-2 py-1.5"
                        >
                          <div className="flex items-center gap-2">
                            <Wifi className={clsx(
                              'w-3 h-3',
                              iface.is_management ? 'text-blue-500' : 'text-green-500'
                            )} />
                            <div>
                              <span className={clsx(
                                'font-medium',
                                iface.is_management ? 'text-blue-700' : 'text-gray-700'
                              )}>
                                {iface.cyroid_network_name || iface.network_name}
                              </span>
                              {iface.is_management && (
                                <span className="ml-1 text-[10px] bg-blue-100 text-blue-600 px-1 rounded">
                                  mgmt
                                </span>
                              )}
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-gray-600">
                              {iface.ip_address || 'No IP'}
                            </span>
                            {iface.subnet && (
                              <span className="text-gray-400" title="Subnet">
                                ({iface.subnet})
                              </span>
                            )}
                            {/* Don't show remove for management or primary network */}
                            {!iface.is_management && iface.cyroid_network_id && vm.network_id !== iface.cyroid_network_id && vmNet.status === 'running' && (
                              <button
                                onClick={() => handleRemoveNetwork(vmNet.vm_id, iface.cyroid_network_id!)}
                                className="p-0.5 hover:bg-red-100 rounded text-red-500"
                                title="Remove network"
                              >
                                <Trash2 className="w-3 h-3" />
                              </button>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Add Network Button/Form */}
                  {vmNet.status === 'running' && availableNetworks.length > 0 && (
                    <div className="ml-6 mt-2">
                      {showAddForm === vmNet.vm_id ? (
                        <AddNetworkForm
                          networks={availableNetworks}
                          onAdd={(networkId, ipAddress) => handleAddNetwork(vmNet.vm_id, networkId, ipAddress)}
                          onCancel={() => setShowAddForm(null)}
                          isLoading={addingNetwork?.vmId === vmNet.vm_id}
                        />
                      ) : (
                        <button
                          onClick={() => setShowAddForm(vmNet.vm_id)}
                          className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700"
                        >
                          <Plus className="w-3 h-3" />
                          Add network interface
                        </button>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

interface AddNetworkFormProps {
  networks: Network[]
  onAdd: (networkId: string, ipAddress: string) => void
  onCancel: () => void
  isLoading: boolean
}

function AddNetworkForm({ networks, onAdd, onCancel, isLoading }: AddNetworkFormProps) {
  const [selectedNetwork, setSelectedNetwork] = useState(networks[0]?.id || '')
  const [ipAddress, setIpAddress] = useState('')

  const selectedNet = networks.find(n => n.id === selectedNetwork)

  return (
    <div className="bg-blue-50 rounded p-2 space-y-2">
      <div className="flex gap-2">
        <select
          value={selectedNetwork}
          onChange={(e) => setSelectedNetwork(e.target.value)}
          className="flex-1 text-xs border border-gray-300 rounded px-2 py-1"
          disabled={isLoading}
        >
          {networks.map((net) => (
            <option key={net.id} value={net.id}>
              {net.name} ({net.subnet})
            </option>
          ))}
        </select>
        <input
          type="text"
          placeholder={selectedNet ? `IP (${selectedNet.subnet})` : 'IP Address'}
          value={ipAddress}
          onChange={(e) => setIpAddress(e.target.value)}
          className="w-32 text-xs border border-gray-300 rounded px-2 py-1 font-mono"
          disabled={isLoading}
        />
      </div>
      <div className="flex gap-2 justify-end">
        <button
          onClick={onCancel}
          className="text-xs px-2 py-1 text-gray-600 hover:bg-gray-200 rounded"
          disabled={isLoading}
        >
          Cancel
        </button>
        <button
          onClick={() => onAdd(selectedNetwork, ipAddress)}
          className="text-xs px-2 py-1 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
          disabled={isLoading || !selectedNetwork}
        >
          {isLoading ? 'Adding...' : 'Add'}
        </button>
      </div>
    </div>
  )
}
