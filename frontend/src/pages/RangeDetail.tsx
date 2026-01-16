// frontend/src/pages/RangeDetail.tsx
import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { rangesApi, networksApi, vmsApi, templatesApi, NetworkCreate, VMCreate } from '../services/api'
import type { Range, Network, VM, VMTemplate } from '../types'
import {
  ArrowLeft, Plus, Loader2, X, Play, Square, RotateCw,
  Network as NetworkIcon, Server, Trash2, Rocket, Activity, Monitor, Shield, Download, Pencil
} from 'lucide-react'
import clsx from 'clsx'
import { VncConsole } from '../components/console/VncConsole'
import { useAuthStore } from '../stores/authStore'
import ExportRangeDialog from '../components/export/ExportRangeDialog'

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
    is_isolated: true
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
    // Windows-specific (version inherited from template)
    windows_version: '',
    windows_username: '',
    windows_password: '',
    display_type: 'desktop',
    // Network configuration
    use_dhcp: false,
    gateway: '',
    dns_servers: '',
    // Extended configuration
    disk2_gb: null,
    disk3_gb: null,
    enable_shared_folder: false,
    enable_global_shared: false,
    language: null,
    keyboard: null,
    region: null,
    manual_install: false,
    // Linux user configuration
    linux_username: '',
    linux_password: '',
    linux_user_sudo: true
  })
  const [showWindowsOptions, setShowWindowsOptions] = useState(false)
  const [showLinuxISOOptions, setShowLinuxISOOptions] = useState(false)
  const [showLinuxContainerOptions, setShowLinuxContainerOptions] = useState(false)
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [linuxContainerType, setLinuxContainerType] = useState<'kasmvnc' | 'linuxserver' | null>(null)

  // Console modal state
  const [consoleVm, setConsoleVm] = useState<VM | null>(null)
  const token = useAuthStore((state) => state.token)

  // Export dialog state
  const [showExportDialog, setShowExportDialog] = useState(false)

  // Edit range modal state
  const [showEditRangeModal, setShowEditRangeModal] = useState(false)
  const [editRangeForm, setEditRangeForm] = useState({ name: '', description: '' })

  // Edit network modal state
  const [showEditNetworkModal, setShowEditNetworkModal] = useState(false)
  const [editingNetwork, setEditingNetwork] = useState<Network | null>(null)
  const [editNetworkForm, setEditNetworkForm] = useState({
    name: '',
    dns_servers: ''
  })

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
        is_isolated: networkForm.is_isolated
      })
      setShowNetworkModal(false)
      setNetworkForm({ name: '', subnet: '', gateway: '', dns_servers: '', is_isolated: true })
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

  const handleToggleIsolation = async (network: Network) => {
    if (!network.docker_network_id) {
      alert('Network must be provisioned first (deploy the range)')
      return
    }
    try {
      await networksApi.toggleIsolation(network.id)
      fetchData()
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to toggle isolation')
    }
  }

  const openEditRangeModal = () => {
    if (range) {
      setEditRangeForm({
        name: range.name,
        description: range.description || ''
      })
      setShowEditRangeModal(true)
    }
  }

  const handleUpdateRange = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!id) return
    setSubmitting(true)
    setError(null)

    try {
      await rangesApi.update(id, {
        name: editRangeForm.name,
        description: editRangeForm.description || undefined
      })
      setShowEditRangeModal(false)
      fetchData()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to update range')
    } finally {
      setSubmitting(false)
    }
  }

  const openEditNetworkModal = (network: Network) => {
    setEditingNetwork(network)
    setEditNetworkForm({
      name: network.name,
      dns_servers: network.dns_servers || ''
    })
    setShowEditNetworkModal(true)
  }

  const handleUpdateNetwork = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingNetwork) return
    setSubmitting(true)
    setError(null)

    try {
      await networksApi.update(editingNetwork.id, {
        name: editNetworkForm.name,
        dns_servers: editNetworkForm.dns_servers || undefined
      })
      setShowEditNetworkModal(false)
      setEditingNetwork(null)
      fetchData()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to update network')
    } finally {
      setSubmitting(false)
    }
  }

  const handleCreateVm = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!id) return
    setSubmitting(true)
    setError(null)

    try {
      // For Windows with DHCP, ip_address can be empty
      const usesDhcp = showWindowsOptions && vmForm.use_dhcp

      const vmData: VMCreate = {
        range_id: id,
        network_id: vmForm.network_id!,
        template_id: vmForm.template_id!,
        hostname: vmForm.hostname!,
        ip_address: usesDhcp ? '' : vmForm.ip_address!,
        cpu: vmForm.cpu!,
        ram_mb: vmForm.ram_mb!,
        disk_gb: vmForm.disk_gb!
      }

      // Add Windows-specific settings if template is Windows
      if (showWindowsOptions) {
        // Windows version comes from template, not user selection
        if (vmForm.windows_username) vmData.windows_username = vmForm.windows_username
        if (vmForm.windows_password) vmData.windows_password = vmForm.windows_password
        vmData.display_type = vmForm.display_type || 'desktop'
        // Network configuration
        vmData.use_dhcp = vmForm.use_dhcp || false
        if (!vmForm.use_dhcp) {
          if (vmForm.gateway) vmData.gateway = vmForm.gateway
          if (vmForm.dns_servers) vmData.dns_servers = vmForm.dns_servers
        }
        // Extended configuration
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
        // Network configuration (static IP only for Linux)
        if (vmForm.gateway) vmData.gateway = vmForm.gateway
        if (vmForm.dns_servers) vmData.dns_servers = vmForm.dns_servers
        // Extended configuration
        if (vmForm.disk2_gb) vmData.disk2_gb = vmForm.disk2_gb
        if (vmForm.disk3_gb) vmData.disk3_gb = vmForm.disk3_gb
        vmData.enable_shared_folder = vmForm.enable_shared_folder || false
        vmData.enable_global_shared = vmForm.enable_global_shared || false
        // Linux user configuration (cloud-init)
        if (vmForm.linux_username) vmData.linux_username = vmForm.linux_username
        if (vmForm.linux_password) vmData.linux_password = vmForm.linux_password
        vmData.linux_user_sudo = vmForm.linux_user_sudo ?? true
      }

      // Add Linux container settings (KasmVNC, LinuxServer)
      if (showLinuxContainerOptions) {
        // Linux user configuration (env vars)
        if (vmForm.linux_username) vmData.linux_username = vmForm.linux_username
        if (vmForm.linux_password) vmData.linux_password = vmForm.linux_password
        vmData.linux_user_sudo = vmForm.linux_user_sudo ?? true
      }

      await vmsApi.create(vmData)
      setShowVmModal(false)
      setVmForm({
        hostname: '', ip_address: '', network_id: '', template_id: '',
        cpu: 2, ram_mb: 2048, disk_gb: 20,
        windows_version: '', windows_username: '', windows_password: '',
        display_type: 'desktop',
        // Network configuration reset
        use_dhcp: false, gateway: '', dns_servers: '',
        // Extended configuration reset
        disk2_gb: null, disk3_gb: null,
        enable_shared_folder: false, enable_global_shared: false,
        language: null, keyboard: null, region: null, manual_install: false,
        // Linux user configuration reset
        linux_username: '', linux_password: '', linux_user_sudo: true
      })
      setShowWindowsOptions(false)
      setShowLinuxISOOptions(false)
      setShowLinuxContainerOptions(false)
      setLinuxContainerType(null)
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
              <button
                onClick={openEditRangeModal}
                className="ml-2 p-1 text-gray-400 hover:text-primary-600"
                title="Edit range"
              >
                <Pencil className="h-4 w-4" />
              </button>
              <span className={clsx(
                "ml-2 px-2.5 py-0.5 text-sm font-medium rounded-full",
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
            {/* Export button - available in any status */}
            <button
              onClick={() => setShowExportDialog(true)}
              className="inline-flex items-center px-3 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
              title="Export Range"
            >
              <Download className="h-4 w-4 mr-1" />
              Export
            </button>
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
                      <p className="text-xs text-gray-500">
                        {network.subnet} • Gateway: {network.gateway}
                        {network.docker_network_id && (
                          <span className="ml-2 text-green-600">• provisioned</span>
                        )}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    {network.docker_network_id && (
                      <button
                        onClick={() => handleToggleIsolation(network)}
                        className={clsx(
                          "p-1",
                          network.is_isolated
                            ? "text-blue-600 hover:text-blue-800"
                            : "text-gray-400 hover:text-blue-600"
                        )}
                        title={network.is_isolated
                          ? "Isolated - Click to allow external access"
                          : "Open - Click to enable isolation"
                        }
                      >
                        <Shield
                          className="h-4 w-4"
                          fill={network.is_isolated ? "currentColor" : "none"}
                        />
                      </button>
                    )}
                    <button
                      onClick={() => openEditNetworkModal(network)}
                      className="p-1 text-gray-400 hover:text-primary-600"
                      title="Edit network"
                    >
                      <Pencil className="h-4 w-4" />
                    </button>
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
                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="is_isolated"
                    checked={networkForm.is_isolated}
                    onChange={(e) => setNetworkForm({ ...networkForm, is_isolated: e.target.checked })}
                    className="h-4 w-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                  />
                  <label htmlFor="is_isolated" className="ml-2 block text-sm text-gray-700">
                    <span className="font-medium">Network Isolation</span>
                    <p className="text-xs text-gray-500">Block access to host and external networks</p>
                  </label>
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
                      // Detect KasmVNC and LinuxServer containers
                      const baseImage = template?.base_image?.toLowerCase() || ''
                      const isKasmVNC = baseImage.includes('kasmweb/')
                      const isLinuxServer = baseImage.includes('linuxserver/') || baseImage.includes('lscr.io/linuxserver')
                      const isLinuxContainer = (isKasmVNC || isLinuxServer) && !isLinuxISO
                      setShowWindowsOptions(isWindows)
                      setShowLinuxISOOptions(isLinuxISO)
                      setShowLinuxContainerOptions(isLinuxContainer)
                      setLinuxContainerType(isKasmVNC ? 'kasmvnc' : isLinuxServer ? 'linuxserver' : null)
                      setVmForm({
                        ...vmForm,
                        template_id: e.target.value,
                        cpu: template?.default_cpu || (isWindows ? 4 : 2),
                        ram_mb: template?.default_ram_mb || (isWindows ? 8192 : 2048),
                        disk_gb: template?.default_disk_gb || (isWindows ? 64 : 20),
                        windows_version: isWindows ? template?.os_variant || '11' : '',
                        display_type: 'desktop',
                        // Reset Linux user config
                        linux_username: '',
                        linux_password: '',
                        linux_user_sudo: true
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

                {/* IP Address for non-Windows, non-Linux ISO templates (regular containers) */}
                {!showWindowsOptions && !showLinuxISOOptions && (
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
                )}

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
                    {/* IP Assignment */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700">IP Assignment</label>
                      <select
                        value={vmForm.use_dhcp ? 'dhcp' : 'static'}
                        onChange={(e) => setVmForm({ ...vmForm, use_dhcp: e.target.value === 'dhcp' })}
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                      >
                        <option value="static">Static IP</option>
                        <option value="dhcp">DHCP</option>
                      </select>
                    </div>
                    {!vmForm.use_dhcp && (
                      <div className="grid grid-cols-3 gap-4">
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
                        <div>
                          <label className="block text-sm font-medium text-gray-700">Gateway</label>
                          <input
                            type="text"
                            value={vmForm.gateway}
                            onChange={(e) => setVmForm({ ...vmForm, gateway: e.target.value })}
                            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                            placeholder="10.0.1.1"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700">DNS</label>
                          <input
                            type="text"
                            value={vmForm.dns_servers}
                            onChange={(e) => setVmForm({ ...vmForm, dns_servers: e.target.value })}
                            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                            placeholder="8.8.8.8,8.8.4.4"
                          />
                        </div>
                      </div>
                    )}
                    <p className="text-xs text-gray-500">
                      {vmForm.use_dhcp
                        ? 'Windows will request network configuration from DHCP server'
                        : 'Configure static IP, gateway, and DNS servers for Windows'}
                    </p>

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

                {/* Additional Networks Info */}
                {networks.length > 1 && vmForm.network_id && (
                  <div className="bg-blue-50 border border-blue-200 rounded-md p-3">
                    <p className="text-xs text-blue-700">
                      <strong>Multiple Networks:</strong> Additional network interfaces can be added after the VM is started.
                      Go to the <span className="font-medium">Execution Console</span> and use the <span className="font-medium">Network Interfaces</span> panel to connect this VM to other networks.
                    </p>
                    <p className="text-xs text-blue-600 mt-1">
                      Available networks: {networks.filter(n => n.id !== vmForm.network_id).map(n => n.name).join(', ')}
                    </p>
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
                    {/* Network Configuration */}
                    <div className="grid grid-cols-3 gap-4">
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
                      <div>
                        <label className="block text-sm font-medium text-gray-700">Gateway</label>
                        <input
                          type="text"
                          value={vmForm.gateway}
                          onChange={(e) => setVmForm({ ...vmForm, gateway: e.target.value })}
                          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                          placeholder="10.0.1.1"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700">DNS</label>
                        <input
                          type="text"
                          value={vmForm.dns_servers}
                          onChange={(e) => setVmForm({ ...vmForm, dns_servers: e.target.value })}
                          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                          placeholder="8.8.8.8,8.8.4.4"
                        />
                      </div>
                    </div>
                    <p className="text-xs text-gray-500">Static network configuration for the VM</p>
                    {/* User Configuration */}
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700">Username (optional)</label>
                        <input
                          type="text"
                          value={vmForm.linux_username}
                          onChange={(e) => setVmForm({ ...vmForm, linux_username: e.target.value })}
                          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                          placeholder="user"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700">Password (optional)</label>
                        <input
                          type="password"
                          value={vmForm.linux_password}
                          onChange={(e) => setVmForm({ ...vmForm, linux_password: e.target.value })}
                          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                          placeholder="Leave empty for no password"
                        />
                      </div>
                    </div>
                    <label className="flex items-center">
                      <input
                        type="checkbox"
                        checked={vmForm.linux_user_sudo ?? true}
                        onChange={(e) => setVmForm({ ...vmForm, linux_user_sudo: e.target.checked })}
                        className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                      />
                      <span className="ml-2 text-sm text-gray-700">Grant sudo privileges</span>
                    </label>
                    <p className="text-xs text-gray-500">
                      User will be created via cloud-init during installation
                    </p>
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

                {/* Linux Container options (KasmVNC, LinuxServer) */}
                {showLinuxContainerOptions && (
                  <div className="border-t pt-4 space-y-4">
                    <h4 className="text-sm font-medium text-gray-900 flex items-center">
                      <Server className="h-4 w-4 mr-2 text-green-500" />
                      Linux Container Settings
                      <span className="ml-2 text-xs text-gray-500">
                        ({linuxContainerType === 'kasmvnc' ? 'KasmVNC' : 'LinuxServer'})
                      </span>
                    </h4>
                    {/* IP Address for containers */}
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
                    {/* User Configuration */}
                    {linuxContainerType === 'kasmvnc' ? (
                      <>
                        <div>
                          <label className="block text-sm font-medium text-gray-700">User Password (optional)</label>
                          <input
                            type="password"
                            value={vmForm.linux_password}
                            onChange={(e) => setVmForm({ ...vmForm, linux_password: e.target.value })}
                            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                            placeholder="Leave empty for default"
                          />
                          <p className="mt-1 text-xs text-gray-500">
                            Sets the Linux password for kasm-user (for sudo, terminal, etc.)
                          </p>
                        </div>
                        <label className="flex items-center">
                          <input
                            type="checkbox"
                            checked={vmForm.linux_user_sudo ?? false}
                            onChange={(e) => setVmForm({ ...vmForm, linux_user_sudo: e.target.checked })}
                            className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                          />
                          <span className="ml-2 text-sm text-gray-700">Grant sudo privileges</span>
                        </label>
                        <p className="text-xs text-gray-500">
                          Allows kasm-user to run commands as root (password required)
                        </p>
                      </>
                    ) : (
                      <>
                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <label className="block text-sm font-medium text-gray-700">Username (optional)</label>
                            <input
                              type="text"
                              value={vmForm.linux_username}
                              onChange={(e) => setVmForm({ ...vmForm, linux_username: e.target.value })}
                              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                              placeholder="abc"
                            />
                          </div>
                          <div>
                            <label className="block text-sm font-medium text-gray-700">Password (optional)</label>
                            <input
                              type="password"
                              value={vmForm.linux_password}
                              onChange={(e) => setVmForm({ ...vmForm, linux_password: e.target.value })}
                              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                              placeholder="Leave empty for no password"
                            />
                          </div>
                        </div>
                        <label className="flex items-center">
                          <input
                            type="checkbox"
                            checked={vmForm.linux_user_sudo ?? true}
                            onChange={(e) => setVmForm({ ...vmForm, linux_user_sudo: e.target.checked })}
                            className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                          />
                          <span className="ml-2 text-sm text-gray-700">Grant sudo privileges</span>
                        </label>
                        <p className="text-xs text-gray-500">
                          Creates a custom user with the specified credentials
                        </p>
                      </>
                    )}
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
          <div className="relative flex items-center justify-center h-full p-4">
            <div className="w-full max-w-6xl h-[90vh]">
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

      {/* Export Range Dialog */}
      {range && (
        <ExportRangeDialog
          isOpen={showExportDialog}
          onClose={() => setShowExportDialog(false)}
          rangeId={range.id}
          rangeName={range.name}
        />
      )}

      {/* Edit Range Modal */}
      {showEditRangeModal && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex items-center justify-center min-h-screen px-4">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75" onClick={() => setShowEditRangeModal(false)} />
            <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full">
              <div className="flex items-center justify-between p-4 border-b">
                <h3 className="text-lg font-medium text-gray-900">Edit Range</h3>
                <button onClick={() => setShowEditRangeModal(false)} className="text-gray-400 hover:text-gray-500">
                  <X className="h-5 w-5" />
                </button>
              </div>
              <form onSubmit={handleUpdateRange} className="p-4 space-y-4">
                {error && (
                  <div className="p-3 bg-red-50 text-red-700 rounded-md text-sm">{error}</div>
                )}
                <div>
                  <label className="block text-sm font-medium text-gray-700">Name</label>
                  <input
                    type="text"
                    required
                    value={editRangeForm.name}
                    onChange={(e) => setEditRangeForm({ ...editRangeForm, name: e.target.value })}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Description</label>
                  <textarea
                    rows={3}
                    value={editRangeForm.description}
                    onChange={(e) => setEditRangeForm({ ...editRangeForm, description: e.target.value })}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                  />
                </div>
                <div className="flex justify-end space-x-3 pt-4">
                  <button
                    type="button"
                    onClick={() => setShowEditRangeModal(false)}
                    className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={submitting}
                    className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 disabled:opacity-50"
                  >
                    {submitting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                    Save
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Edit Network Modal */}
      {showEditNetworkModal && editingNetwork && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex items-center justify-center min-h-screen px-4">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75" onClick={() => setShowEditNetworkModal(false)} />
            <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full">
              <div className="flex items-center justify-between p-4 border-b">
                <h3 className="text-lg font-medium text-gray-900">Edit Network</h3>
                <button onClick={() => setShowEditNetworkModal(false)} className="text-gray-400 hover:text-gray-500">
                  <X className="h-5 w-5" />
                </button>
              </div>
              <form onSubmit={handleUpdateNetwork} className="p-4 space-y-4">
                {error && (
                  <div className="p-3 bg-red-50 text-red-700 rounded-md text-sm">{error}</div>
                )}
                <div>
                  <label className="block text-sm font-medium text-gray-700">Name</label>
                  <input
                    type="text"
                    required
                    value={editNetworkForm.name}
                    onChange={(e) => setEditNetworkForm({ ...editNetworkForm, name: e.target.value })}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Subnet</label>
                  <input
                    type="text"
                    value={editingNetwork.subnet}
                    disabled
                    className="mt-1 block w-full rounded-md border-gray-300 bg-gray-100 shadow-sm sm:text-sm cursor-not-allowed"
                  />
                  <p className="mt-1 text-xs text-gray-500">Subnet cannot be changed after creation</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Gateway</label>
                  <input
                    type="text"
                    value={editingNetwork.gateway}
                    disabled
                    className="mt-1 block w-full rounded-md border-gray-300 bg-gray-100 shadow-sm sm:text-sm cursor-not-allowed"
                  />
                  <p className="mt-1 text-xs text-gray-500">Gateway cannot be changed after creation</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">DNS Servers</label>
                  <input
                    type="text"
                    value={editNetworkForm.dns_servers}
                    onChange={(e) => setEditNetworkForm({ ...editNetworkForm, dns_servers: e.target.value })}
                    placeholder="e.g., 8.8.8.8,8.8.4.4"
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                  />
                </div>
                <div className="p-3 bg-gray-50 rounded-md">
                  <p className="text-sm text-gray-600">
                    <span className="font-medium">Isolation:</span> Use the shield icon on the network card to toggle isolation on/off for provisioned networks.
                  </p>
                </div>
                <div className="flex justify-end space-x-3 pt-4">
                  <button
                    type="button"
                    onClick={() => setShowEditNetworkModal(false)}
                    className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={submitting}
                    className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 disabled:opacity-50"
                  >
                    {submitting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                    Save
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
