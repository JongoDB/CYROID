// frontend/src/pages/RangeDetail.tsx
import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { rangesApi, networksApi, vmsApi, templatesApi, NetworkCreate, VMCreate } from '../services/api'
import type { Range, Network, VM, VMTemplate } from '../types'
import {
  ArrowLeft, Plus, Loader2, X, Play, Square, RotateCw,
  Network as NetworkIcon, Server, Trash2, Rocket, Activity, Monitor
} from 'lucide-react'
import clsx from 'clsx'
import { VncConsole } from '../components/console/VncConsole'
import { useAuthStore } from '../stores/authStore'

const statusColors: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-800',
  deploying: 'bg-yellow-100 text-yellow-800',
  running: 'bg-green-100 text-green-800',
  stopped: 'bg-gray-100 text-gray-800',
  pending: 'bg-gray-100 text-gray-800',
  creating: 'bg-yellow-100 text-yellow-800',
  error: 'bg-red-100 text-red-800'
}

export default function RangeDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [range, setRange] = useState<Range | null>(null)
  const [networks, setNetworks] = useState<Network[]>([])
  const [vms, setVms] = useState<VM[]>([])
  const [templates, setTemplates] = useState<VMTemplate[]>([])
  const [loading, setLoading] = useState(true)

  // Network modal state
  const [showNetworkModal, setShowNetworkModal] = useState(false)
  const [networkForm, setNetworkForm] = useState<Partial<NetworkCreate>>({
    name: '',
    subnet: '',
    gateway: '',
    dns_servers: '',
    isolation_level: 'controlled'
  })

  // VM modal state
  const [showVmModal, setShowVmModal] = useState(false)
  const [vmForm, setVmForm] = useState<Partial<VMCreate>>({
    hostname: '',
    ip_address: '',
    network_id: '',
    template_id: '',
    cpu: 2,
    ram_mb: 2048,
    disk_gb: 20,
    // Windows-specific
    windows_version: '',
    windows_username: '',
    windows_password: '',
    iso_url: '',
    display_type: 'desktop',
    // Extended dockur/windows configuration
    use_dhcp: false,
    disk2_gb: null,
    disk3_gb: null,
    enable_shared_folder: false,
    enable_global_shared: false,
    language: null,
    keyboard: null,
    region: null,
    manual_install: false
  })
  const [showWindowsOptions, setShowWindowsOptions] = useState(false)
  const [showLinuxISOOptions, setShowLinuxISOOptions] = useState(false)

  // Console modal state
  const [consoleVm, setConsoleVm] = useState<VM | null>(null)
  const token = useAuthStore((state) => state.token)

  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchData = async () => {
    if (!id) return
    try {
      const [rangeRes, networksRes, vmsRes, templatesRes] = await Promise.all([
        rangesApi.get(id),
        networksApi.list(id),
        vmsApi.list(id),
        templatesApi.list()
      ])
      setRange(rangeRes.data)
      setNetworks(networksRes.data)
      setVms(vmsRes.data)
      setTemplates(templatesRes.data)
    } catch (err) {
      console.error('Failed to fetch range:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [id])

  const handleDeploy = async () => {
    if (!id) return
    try {
      await rangesApi.deploy(id)
      fetchData()
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to deploy range')
    }
  }

  const handleStart = async () => {
    if (!id) return
    try {
      await rangesApi.start(id)
      fetchData()
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to start range')
    }
  }

  const handleStop = async () => {
    if (!id) return
    try {
      await rangesApi.stop(id)
      fetchData()
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to stop range')
    }
  }

  const handleCreateNetwork = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!id) return
    setSubmitting(true)
    setError(null)

    try {
      await networksApi.create({
        range_id: id,
        name: networkForm.name!,
        subnet: networkForm.subnet!,
        gateway: networkForm.gateway!,
        dns_servers: networkForm.dns_servers || undefined,
        isolation_level: networkForm.isolation_level as 'complete' | 'controlled' | 'open'
      })
      setShowNetworkModal(false)
      setNetworkForm({ name: '', subnet: '', gateway: '', dns_servers: '', isolation_level: 'controlled' })
      fetchData()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create network')
    } finally {
      setSubmitting(false)
    }
  }

  const handleDeleteNetwork = async (network: Network) => {
    if (!confirm(`Delete network "${network.name}"?`)) return
    try {
      await networksApi.delete(network.id)
      fetchData()
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to delete network')
    }
  }

  const handleCreateVm = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!id) return
    setSubmitting(true)
    setError(null)

    try {
      const vmData: VMCreate = {
        range_id: id,
        network_id: vmForm.network_id!,
        template_id: vmForm.template_id!,
        hostname: vmForm.hostname!,
        ip_address: vmForm.ip_address!,
        cpu: vmForm.cpu!,
        ram_mb: vmForm.ram_mb!,
        disk_gb: vmForm.disk_gb!
      }

      // Add Windows-specific settings if template is Windows
      if (showWindowsOptions) {
        if (vmForm.windows_version) vmData.windows_version = vmForm.windows_version
        if (vmForm.windows_username) vmData.windows_username = vmForm.windows_username
        if (vmForm.windows_password) vmData.windows_password = vmForm.windows_password
        if (vmForm.iso_url) vmData.iso_url = vmForm.iso_url
        vmData.display_type = vmForm.display_type || 'desktop'
        // Extended dockur/windows configuration
        vmData.use_dhcp = vmForm.use_dhcp || false
        if (vmForm.disk2_gb) vmData.disk2_gb = vmForm.disk2_gb
        if (vmForm.disk3_gb) vmData.disk3_gb = vmForm.disk3_gb
        vmData.enable_shared_folder = vmForm.enable_shared_folder || false
        vmData.enable_global_shared = vmForm.enable_global_shared || false
        if (vmForm.language) vmData.language = vmForm.language
        if (vmForm.keyboard) vmData.keyboard = vmForm.keyboard
        if (vmForm.region) vmData.region = vmForm.region
        vmData.manual_install = vmForm.manual_install || false
      }

      // Add Linux ISO-specific settings
      if (showLinuxISOOptions) {
        vmData.display_type = vmForm.display_type || 'desktop'
        if (vmForm.iso_url) vmData.iso_url = vmForm.iso_url
        if (vmForm.disk2_gb) vmData.disk2_gb = vmForm.disk2_gb
        if (vmForm.disk3_gb) vmData.disk3_gb = vmForm.disk3_gb
        vmData.enable_shared_folder = vmForm.enable_shared_folder || false
        vmData.enable_global_shared = vmForm.enable_global_shared || false
      }

      await vmsApi.create(vmData)
      setShowVmModal(false)
      setVmForm({
        hostname: '', ip_address: '', network_id: '', template_id: '',
        cpu: 2, ram_mb: 2048, disk_gb: 20,
        windows_version: '', windows_username: '', windows_password: '', iso_url: '',
        display_type: 'desktop',
        // Extended dockur/windows configuration reset
        use_dhcp: false, disk2_gb: null, disk3_gb: null,
        enable_shared_folder: false, enable_global_shared: false,
        language: null, keyboard: null, region: null, manual_install: false
      })
      setShowWindowsOptions(false)
      setShowLinuxISOOptions(false)
      fetchData()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create VM')
    } finally {
      setSubmitting(false)
    }
  }

  const handleVmAction = async (vm: VM, action: 'start' | 'stop' | 'restart') => {
    try {
      if (action === 'start') await vmsApi.start(vm.id)
      else if (action === 'stop') await vmsApi.stop(vm.id)
      else if (action === 'restart') await vmsApi.restart(vm.id)
      fetchData()
    } catch (err: any) {
      alert(err.response?.data?.detail || `Failed to ${action} VM`)
    }
  }

  const handleDeleteVm = async (vm: VM) => {
    if (!confirm(`Delete VM "${vm.hostname}"?`)) return
    try {
      await vmsApi.delete(vm.id)
      fetchData()
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to delete VM')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    )
  }

  if (!range) {
    return (
      <div className="text-center py-12">
        <h3 className="text-lg font-medium text-gray-900">Range not found</h3>
        <Link to="/ranges" className="mt-4 text-primary-600 hover:text-primary-700">
          Back to ranges
        </Link>
      </div>
    )
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <Link to="/ranges" className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700 mb-4">
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back to Ranges
        </Link>
        <div className="sm:flex sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center">
              <h1 className="text-2xl font-bold text-gray-900">{range.name}</h1>
              <span className={clsx(
                "ml-3 px-2.5 py-0.5 text-sm font-medium rounded-full",
                statusColors[range.status]
              )}>
                {range.status}
              </span>
            </div>
            <p className="mt-1 text-sm text-gray-500">{range.description || 'No description'}</p>
          </div>
          <div className="mt-4 sm:mt-0 flex items-center space-x-3">
            {range.status === 'draft' && (
              <button
                onClick={handleDeploy}
                className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700"
              >
                <Rocket className="h-4 w-4 mr-2" />
                Deploy
              </button>
            )}
            {(range.status === 'stopped' || range.status === 'draft') && (
              <button
                onClick={handleStart}
                className="inline-flex items-center px-3 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
              >
                <Play className="h-4 w-4 mr-1" />
                Start
              </button>
            )}
            {range.status === 'running' && (
              <>
                <button
                  onClick={() => navigate(`/execution/${id}`)}
                  className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700"
                >
                  <Activity className="h-4 w-4 mr-2" />
                  Execution Console
                </button>
                <button
                  onClick={handleStop}
                  className="inline-flex items-center px-3 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
                >
                  <Square className="h-4 w-4 mr-1" />
                  Stop
                </button>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Networks Section */}
      <div className="bg-white shadow rounded-lg mb-6">
        <div className="px-4 py-5 sm:px-6 flex items-center justify-between border-b">
          <h3 className="text-lg font-medium text-gray-900">Networks</h3>
          <button
            onClick={() => setShowNetworkModal(true)}
            className="inline-flex items-center px-3 py-1.5 border border-transparent text-sm font-medium rounded-md text-primary-600 bg-primary-100 hover:bg-primary-200"
          >
            <Plus className="h-4 w-4 mr-1" />
            Add Network
          </button>
        </div>
        <div className="px-4 py-4 sm:px-6">
          {networks.length === 0 ? (
            <p className="text-sm text-gray-500 text-center py-4">No networks configured</p>
          ) : (
            <div className="space-y-3">
              {networks.map((network) => (
                <div key={network.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div className="flex items-center">
                    <NetworkIcon className="h-5 w-5 text-gray-400 mr-3" />
                    <div>
                      <p className="text-sm font-medium text-gray-900">{network.name}</p>
                      <p className="text-xs text-gray-500">{network.subnet} • Gateway: {network.gateway}</p>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className={clsx(
                      "px-2 py-0.5 text-xs font-medium rounded",
                      network.isolation_level === 'complete' ? 'bg-red-100 text-red-700' :
                      network.isolation_level === 'controlled' ? 'bg-yellow-100 text-yellow-700' :
                      'bg-green-100 text-green-700'
                    )}>
                      {network.isolation_level}
                    </span>
                    <button
                      onClick={() => handleDeleteNetwork(network)}
                      className="p-1 text-gray-400 hover:text-red-600"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* VMs Section */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:px-6 flex items-center justify-between border-b">
          <h3 className="text-lg font-medium text-gray-900">Virtual Machines</h3>
          <button
            onClick={() => setShowVmModal(true)}
            disabled={networks.length === 0 || templates.length === 0}
            className="inline-flex items-center px-3 py-1.5 border border-transparent text-sm font-medium rounded-md text-primary-600 bg-primary-100 hover:bg-primary-200 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Plus className="h-4 w-4 mr-1" />
            Add VM
          </button>
        </div>
        <div className="px-4 py-4 sm:px-6">
          {networks.length === 0 ? (
            <p className="text-sm text-gray-500 text-center py-4">Add a network before creating VMs</p>
          ) : vms.length === 0 ? (
            <p className="text-sm text-gray-500 text-center py-4">No virtual machines configured</p>
          ) : (
            <div className="space-y-3">
              {vms.map((vm) => {
                const template = templates.find(t => t.id === vm.template_id)
                const network = networks.find(n => n.id === vm.network_id)
                return (
                  <div key={vm.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <div className="flex items-center">
                      <Server className={clsx(
                        "h-5 w-5 mr-3",
                        vm.status === 'running' ? 'text-green-500' : 'text-gray-400'
                      )} />
                      <div>
                        <div className="flex items-center">
                          <p className="text-sm font-medium text-gray-900">{vm.hostname}</p>
                          <span className={clsx(
                            "ml-2 px-1.5 py-0.5 text-xs font-medium rounded",
                            statusColors[vm.status]
                          )}>
                            {vm.status}
                          </span>
                        </div>
                        <p className="text-xs text-gray-500">
                          {vm.ip_address} • {template?.name || 'Unknown'} • {network?.name || 'Unknown'}
                        </p>
                        <p className="text-xs text-gray-400">
                          {vm.cpu} CPU • {vm.ram_mb / 1024}GB RAM • {vm.disk_gb}GB
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center space-x-1">
                      {(vm.status === 'stopped' || vm.status === 'pending') && (
                        <button
                          onClick={() => handleVmAction(vm, 'start')}
                          className="p-1.5 text-gray-400 hover:text-green-600"
                          title="Start"
                        >
                          <Play className="h-4 w-4" />
                        </button>
                      )}
                      {vm.status === 'running' && (
                        <>
                          <button
                            onClick={() => setConsoleVm(vm)}
                            className="p-1.5 text-gray-400 hover:text-blue-600"
                            title="Open Console"
                          >
                            <Monitor className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => handleVmAction(vm, 'stop')}
                            className="p-1.5 text-gray-400 hover:text-yellow-600"
                            title="Stop"
                          >
                            <Square className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => handleVmAction(vm, 'restart')}
                            className="p-1.5 text-gray-400 hover:text-blue-600"
                            title="Restart"
                          >
                            <RotateCw className="h-4 w-4" />
                          </button>
                        </>
                      )}
                      <button
                        onClick={() => handleDeleteVm(vm)}
                        className="p-1.5 text-gray-400 hover:text-red-600"
                        title="Delete"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>

      {/* Network Modal */}
      {showNetworkModal && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex items-center justify-center min-h-screen px-4">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75" onClick={() => setShowNetworkModal(false)} />
            <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full">
              <div className="flex items-center justify-between p-4 border-b">
                <h3 className="text-lg font-medium text-gray-900">Add Network</h3>
                <button onClick={() => setShowNetworkModal(false)} className="text-gray-400 hover:text-gray-500">
                  <X className="h-5 w-5" />
                </button>
              </div>
              <form onSubmit={handleCreateNetwork} className="p-4 space-y-4">
                {error && <div className="p-3 bg-red-50 text-red-700 rounded-md text-sm">{error}</div>}
                <div>
                  <label className="block text-sm font-medium text-gray-700">Name</label>
                  <input
                    type="text"
                    required
                    value={networkForm.name}
                    onChange={(e) => setNetworkForm({ ...networkForm, name: e.target.value })}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                    placeholder="e.g., Corporate LAN"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Subnet</label>
                    <input
                      type="text"
                      required
                      value={networkForm.subnet}
                      onChange={(e) => setNetworkForm({ ...networkForm, subnet: e.target.value })}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                      placeholder="10.0.1.0/24"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Gateway</label>
                    <input
                      type="text"
                      required
                      value={networkForm.gateway}
                      onChange={(e) => setNetworkForm({ ...networkForm, gateway: e.target.value })}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                      placeholder="10.0.1.1"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">DNS Servers</label>
                  <input
                    type="text"
                    value={networkForm.dns_servers}
                    onChange={(e) => setNetworkForm({ ...networkForm, dns_servers: e.target.value })}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                    placeholder="8.8.8.8,8.8.4.4"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Isolation Level</label>
                  <select
                    value={networkForm.isolation_level}
                    onChange={(e) => setNetworkForm({ ...networkForm, isolation_level: e.target.value as 'complete' | 'controlled' | 'open' })}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                  >
                    <option value="complete">Complete (No external access)</option>
                    <option value="controlled">Controlled (Limited access)</option>
                    <option value="open">Open (Full access)</option>
                  </select>
                </div>
                <div className="flex justify-end space-x-3 pt-4">
                  <button type="button" onClick={() => setShowNetworkModal(false)} className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50">Cancel</button>
                  <button type="submit" disabled={submitting} className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 disabled:opacity-50">
                    {submitting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                    Create
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* VM Modal */}
      {showVmModal && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex items-center justify-center min-h-screen px-4">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75" onClick={() => setShowVmModal(false)} />
            <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full">
              <div className="flex items-center justify-between p-4 border-b">
                <h3 className="text-lg font-medium text-gray-900">Add Virtual Machine</h3>
                <button onClick={() => setShowVmModal(false)} className="text-gray-400 hover:text-gray-500">
                  <X className="h-5 w-5" />
                </button>
              </div>
              <form onSubmit={handleCreateVm} className="p-4 space-y-4">
                {error && <div className="p-3 bg-red-50 text-red-700 rounded-md text-sm">{error}</div>}
                <div>
                  <label className="block text-sm font-medium text-gray-700">Template</label>
                  <select
                    required
                    value={vmForm.template_id}
                    onChange={(e) => {
                      const template = templates.find(t => t.id === e.target.value)
                      const isWindows = template?.os_type === 'windows'
                      const isLinuxISO = template?.os_type === 'linux' && template?.base_image?.startsWith('iso:')
                      setShowWindowsOptions(isWindows)
                      setShowLinuxISOOptions(isLinuxISO)
                      setVmForm({
                        ...vmForm,
                        template_id: e.target.value,
                        cpu: template?.default_cpu || (isWindows ? 4 : 2),
                        ram_mb: template?.default_ram_mb || (isWindows ? 8192 : 2048),
                        disk_gb: template?.default_disk_gb || (isWindows ? 64 : 20),
                        windows_version: isWindows ? template?.os_variant || '11' : '',
                        display_type: 'desktop'
                      })
                    }}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                  >
                    <option value="">Select a template</option>
                    {templates.map(t => (
                      <option key={t.id} value={t.id}>{t.name} ({t.os_type === 'windows' ? 'Windows' : 'Linux'} - {t.os_variant})</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Network</label>
                  <select
                    required
                    value={vmForm.network_id}
                    onChange={(e) => setVmForm({ ...vmForm, network_id: e.target.value })}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                  >
                    <option value="">Select a network</option>
                    {networks.map(n => (
                      <option key={n.id} value={n.id}>{n.name} ({n.subnet})</option>
                    ))}
                  </select>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Hostname</label>
                    <input
                      type="text"
                      required
                      value={vmForm.hostname}
                      onChange={(e) => setVmForm({ ...vmForm, hostname: e.target.value })}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                      placeholder="web-server-01"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">IP Address</label>
                    <input
                      type="text"
                      required
                      value={vmForm.ip_address}
                      onChange={(e) => setVmForm({ ...vmForm, ip_address: e.target.value })}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                      placeholder="10.0.1.10"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">CPU</label>
                    <input
                      type="number"
                      min={1}
                      max={32}
                      value={vmForm.cpu}
                      onChange={(e) => setVmForm({ ...vmForm, cpu: parseInt(e.target.value) })}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">RAM (MB)</label>
                    <input
                      type="number"
                      min={512}
                      step={512}
                      value={vmForm.ram_mb}
                      onChange={(e) => setVmForm({ ...vmForm, ram_mb: parseInt(e.target.value) })}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Disk (GB)</label>
                    <input
                      type="number"
                      min={5}
                      value={vmForm.disk_gb}
                      onChange={(e) => setVmForm({ ...vmForm, disk_gb: parseInt(e.target.value) })}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                    />
                  </div>
                </div>

                {/* Windows-specific options */}
                {showWindowsOptions && (
                  <div className="border-t pt-4 space-y-4">
                    <h4 className="text-sm font-medium text-gray-900 flex items-center">
                      <Server className="h-4 w-4 mr-2 text-purple-500" />
                      Windows Settings
                    </h4>
                    <div>
                      <label className="block text-sm font-medium text-gray-700">Environment Type</label>
                      <select
                        value={vmForm.display_type}
                        onChange={(e) => setVmForm({ ...vmForm, display_type: e.target.value as 'desktop' | 'server' })}
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                      >
                        <option value="desktop">Desktop (VNC/Web Console)</option>
                        <option value="server">Server (RDP Only)</option>
                      </select>
                      <p className="mt-1 text-xs text-gray-500">
                        {vmForm.display_type === 'desktop'
                          ? 'Desktop mode provides VNC web console access on port 8006'
                          : 'Server mode is headless, use RDP (port 3389) to connect'}
                      </p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700">Windows Version</label>
                      <select
                        value={vmForm.windows_version}
                        onChange={(e) => setVmForm({ ...vmForm, windows_version: e.target.value })}
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                      >
                        <optgroup label="Desktop">
                          <option value="11">Windows 11 Pro (7.2 GB)</option>
                          <option value="11l">Windows 11 LTSC (4.7 GB)</option>
                          <option value="11e">Windows 11 Enterprise (6.6 GB)</option>
                          <option value="10">Windows 10 Pro (5.7 GB)</option>
                          <option value="10l">Windows 10 LTSC (4.6 GB)</option>
                          <option value="10e">Windows 10 Enterprise (5.2 GB)</option>
                          <option value="8e">Windows 8.1 Enterprise (3.7 GB)</option>
                        </optgroup>
                        <optgroup label="Server">
                          <option value="2025">Windows Server 2025 (6.7 GB)</option>
                          <option value="2022">Windows Server 2022 (6.0 GB)</option>
                          <option value="2019">Windows Server 2019 (5.3 GB)</option>
                          <option value="2016">Windows Server 2016 (6.5 GB)</option>
                          <option value="2012">Windows Server 2012 (4.3 GB)</option>
                          <option value="2008">Windows Server 2008 (3.0 GB)</option>
                        </optgroup>
                        <optgroup label="Legacy">
                          <option value="7u">Windows 7 Ultimate (3.1 GB)</option>
                          <option value="vu">Windows Vista Ultimate (3.0 GB)</option>
                          <option value="xp">Windows XP Professional (0.6 GB)</option>
                          <option value="2k">Windows 2000 Professional (0.4 GB)</option>
                          <option value="2003">Windows Server 2003 (0.6 GB)</option>
                        </optgroup>
                      </select>
                      <p className="mt-1 text-xs text-gray-500">ISO will be auto-downloaded by dockur/windows</p>
                    </div>

                    {/* IP Assignment */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700">IP Assignment</label>
                      <select
                        value={vmForm.use_dhcp ? 'dhcp' : 'static'}
                        onChange={(e) => setVmForm({ ...vmForm, use_dhcp: e.target.value === 'dhcp' })}
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                      >
                        <option value="static">Static IP (use IP address field above)</option>
                        <option value="dhcp">DHCP (Windows requests IP automatically)</option>
                      </select>
                      <p className="mt-1 text-xs text-gray-500">
                        {vmForm.use_dhcp
                          ? 'Windows will request an IP from the network DHCP server'
                          : 'Windows will use the static IP address specified above'}
                      </p>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700">Username (optional)</label>
                        <input
                          type="text"
                          value={vmForm.windows_username}
                          onChange={(e) => setVmForm({ ...vmForm, windows_username: e.target.value })}
                          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                          placeholder="Docker"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700">Password (optional)</label>
                        <input
                          type="password"
                          value={vmForm.windows_password}
                          onChange={(e) => setVmForm({ ...vmForm, windows_password: e.target.value })}
                          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                          placeholder="Leave empty for no password"
                        />
                      </div>
                    </div>

                    {/* Shared Folders */}
                    <div className="space-y-2">
                      <label className="block text-sm font-medium text-gray-700">Shared Folders</label>
                      <label className="flex items-center">
                        <input
                          type="checkbox"
                          checked={vmForm.enable_shared_folder || false}
                          onChange={(e) => setVmForm({ ...vmForm, enable_shared_folder: e.target.checked })}
                          className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                        />
                        <span className="ml-2 text-sm text-gray-700">Enable per-VM shared folder (/shared)</span>
                      </label>
                      <label className="flex items-center">
                        <input
                          type="checkbox"
                          checked={vmForm.enable_global_shared || false}
                          onChange={(e) => setVmForm({ ...vmForm, enable_global_shared: e.target.checked })}
                          className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                        />
                        <span className="ml-2 text-sm text-gray-700">Mount global shared folder (/global, read-only)</span>
                      </label>
                      <p className="text-xs text-gray-500">Shared folders appear as network drives in Windows</p>
                    </div>

                    {/* Additional Storage */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700">Additional Disks (optional)</label>
                      <div className="grid grid-cols-2 gap-4 mt-1">
                        <div>
                          <input
                            type="number"
                            min={1}
                            max={1000}
                            value={vmForm.disk2_gb || ''}
                            onChange={(e) => setVmForm({ ...vmForm, disk2_gb: e.target.value ? parseInt(e.target.value) : null })}
                            className="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                            placeholder="2nd Disk (GB)"
                          />
                        </div>
                        <div>
                          <input
                            type="number"
                            min={1}
                            max={1000}
                            value={vmForm.disk3_gb || ''}
                            onChange={(e) => setVmForm({ ...vmForm, disk3_gb: e.target.value ? parseInt(e.target.value) : null })}
                            className="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                            placeholder="3rd Disk (GB)"
                          />
                        </div>
                      </div>
                      <p className="mt-1 text-xs text-gray-500">Additional disks appear as D: and E: drives in Windows</p>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700">Custom ISO URL (optional)</label>
                      <input
                        type="url"
                        value={vmForm.iso_url}
                        onChange={(e) => setVmForm({ ...vmForm, iso_url: e.target.value })}
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                        placeholder="https://example.com/custom.iso"
                      />
                      <p className="mt-1 text-xs text-gray-500">Overrides the automatic ISO download</p>
                    </div>

                    {/* Localization - Collapsible */}
                    <details className="border rounded-md p-3 bg-gray-50">
                      <summary className="cursor-pointer text-sm font-medium text-gray-700">Localization Settings</summary>
                      <div className="mt-3 space-y-3">
                        <div>
                          <label className="block text-sm font-medium text-gray-700">Language</label>
                          <select
                            value={vmForm.language || ''}
                            onChange={(e) => setVmForm({ ...vmForm, language: e.target.value || null })}
                            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                          >
                            <option value="">Default (English)</option>
                            <option value="Arabic">Arabic</option>
                            <option value="Chinese">Chinese (Simplified)</option>
                            <option value="Dutch">Dutch</option>
                            <option value="French">French</option>
                            <option value="German">German</option>
                            <option value="Italian">Italian</option>
                            <option value="Japanese">Japanese</option>
                            <option value="Korean">Korean</option>
                            <option value="Polish">Polish</option>
                            <option value="Portuguese">Portuguese</option>
                            <option value="Russian">Russian</option>
                            <option value="Spanish">Spanish</option>
                            <option value="Turkish">Turkish</option>
                          </select>
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <label className="block text-sm font-medium text-gray-700">Keyboard Layout</label>
                            <input
                              type="text"
                              value={vmForm.keyboard || ''}
                              onChange={(e) => setVmForm({ ...vmForm, keyboard: e.target.value || null })}
                              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                              placeholder="e.g., en-US, de-DE"
                            />
                          </div>
                          <div>
                            <label className="block text-sm font-medium text-gray-700">Region</label>
                            <input
                              type="text"
                              value={vmForm.region || ''}
                              onChange={(e) => setVmForm({ ...vmForm, region: e.target.value || null })}
                              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                              placeholder="e.g., en-US, fr-FR"
                            />
                          </div>
                        </div>
                      </div>
                    </details>

                    {/* Advanced Options - Collapsible */}
                    <details className="border rounded-md p-3 bg-gray-50">
                      <summary className="cursor-pointer text-sm font-medium text-gray-700">Advanced Options</summary>
                      <div className="mt-3">
                        <label className="flex items-center">
                          <input
                            type="checkbox"
                            checked={vmForm.manual_install || false}
                            onChange={(e) => setVmForm({ ...vmForm, manual_install: e.target.checked })}
                            className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                          />
                          <span className="ml-2 text-sm text-gray-700">Manual Installation Mode</span>
                        </label>
                        <p className="mt-1 text-xs text-gray-500">
                          Enable for custom/interactive Windows setup. Disables unattended installation.
                        </p>
                      </div>
                    </details>
                  </div>
                )}

                {/* Linux ISO-specific options */}
                {showLinuxISOOptions && (
                  <div className="border-t pt-4 space-y-4">
                    <h4 className="text-sm font-medium text-gray-900 flex items-center">
                      <Server className="h-4 w-4 mr-2 text-orange-500" />
                      Linux VM Settings
                    </h4>
                    <div>
                      <label className="block text-sm font-medium text-gray-700">Environment Type</label>
                      <select
                        value={vmForm.display_type}
                        onChange={(e) => setVmForm({ ...vmForm, display_type: e.target.value as 'desktop' | 'server' })}
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                      >
                        <option value="desktop">Desktop (VNC/Web Console)</option>
                        <option value="server">Server (Headless)</option>
                      </select>
                      <p className="mt-1 text-xs text-gray-500">
                        {vmForm.display_type === 'desktop'
                          ? 'Desktop mode provides VNC web console access on port 8006'
                          : 'Server mode is headless, no GUI - use SSH to connect'}
                      </p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700">Custom ISO URL (optional)</label>
                      <input
                        type="url"
                        value={vmForm.iso_url}
                        onChange={(e) => setVmForm({ ...vmForm, iso_url: e.target.value })}
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                        placeholder="https://example.com/custom-linux.iso"
                      />
                      <p className="mt-1 text-xs text-gray-500">Overrides the template's default ISO</p>
                    </div>
                    {/* Shared Folders */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">Shared Folders</label>
                      <label className="flex items-center">
                        <input
                          type="checkbox"
                          checked={vmForm.enable_shared_folder || false}
                          onChange={(e) => setVmForm({ ...vmForm, enable_shared_folder: e.target.checked })}
                          className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                        />
                        <span className="ml-2 text-sm text-gray-700">Enable per-VM shared folder (/shared)</span>
                      </label>
                      <label className="flex items-center mt-2">
                        <input
                          type="checkbox"
                          checked={vmForm.enable_global_shared || false}
                          onChange={(e) => setVmForm({ ...vmForm, enable_global_shared: e.target.checked })}
                          className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                        />
                        <span className="ml-2 text-sm text-gray-700">Mount global shared folder (/global, read-only)</span>
                      </label>
                    </div>
                    {/* Additional Storage */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700">Additional Disks (optional)</label>
                      <div className="grid grid-cols-2 gap-4 mt-1">
                        <div>
                          <input
                            type="number"
                            min={1}
                            max={1000}
                            value={vmForm.disk2_gb || ''}
                            onChange={(e) => setVmForm({ ...vmForm, disk2_gb: e.target.value ? parseInt(e.target.value) : null })}
                            className="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                            placeholder="2nd Disk (GB)"
                          />
                        </div>
                        <div>
                          <input
                            type="number"
                            min={1}
                            max={1000}
                            value={vmForm.disk3_gb || ''}
                            onChange={(e) => setVmForm({ ...vmForm, disk3_gb: e.target.value ? parseInt(e.target.value) : null })}
                            className="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                            placeholder="3rd Disk (GB)"
                          />
                        </div>
                      </div>
                      <p className="mt-1 text-xs text-gray-500">Additional virtual disks for the VM</p>
                    </div>
                  </div>
                )}

                <div className="flex justify-end space-x-3 pt-4">
                  <button type="button" onClick={() => setShowVmModal(false)} className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50">Cancel</button>
                  <button type="submit" disabled={submitting} className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 disabled:opacity-50">
                    {submitting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                    Create
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* VNC Console Modal */}
      {consoleVm && token && (
        <div className="fixed inset-0 z-50 overflow-hidden">
          <div className="absolute inset-0 bg-gray-900/80" onClick={() => setConsoleVm(null)} />
          <div className="relative flex items-center justify-center min-h-screen p-4">
            <div className="w-full max-w-5xl">
              <VncConsole
                vmId={consoleVm.id}
                vmHostname={consoleVm.hostname}
                token={token}
                onClose={() => setConsoleVm(null)}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
