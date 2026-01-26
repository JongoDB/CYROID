// frontend/src/pages/RangeDetail.tsx
import { useEffect, useState, useMemo, useCallback, useRef } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { rangesApi, networksApi, vmsApi, imagesApi, NetworkCreate, VMCreate } from '../services/api'
import type { Range, Network, VM, RealtimeEvent, BaseImage, GoldenImageLibrary, SnapshotWithLineage } from '../types'
import {
  ArrowLeft, Plus, Loader2, X, Play, Square, RotateCw, Camera,
  Network as NetworkIcon, Server, Trash2, Rocket, Activity, Monitor, Shield, Download, Pencil, Globe, Router, Wifi, Radio, Wrench, BookOpen, LayoutTemplate, Terminal
} from 'lucide-react'
import clsx from 'clsx'
import { VncConsole } from '../components/console/VncConsole'
import { VMConsole } from '../components/console/VMConsole'
import { useAuthStore } from '../stores/authStore'
import { RelativeTime } from '../components/common/RelativeTime'
import { useIsArmHost } from '../stores/systemStore'
import { EmulationWarning } from '../components/common/EmulationWarning'
import ExportRangeDialog from '../components/export/ExportRangeDialog'
import { DeploymentProgress } from '../components/range/DeploymentProgress'
import { useRealtimeRange } from '../hooks/useRealtimeRange'
import { toast } from '../stores/toastStore'
import { DiagnosticsTab } from '../components/diagnostics'
import { ActivityTab } from '../components/range/ActivityTab'
import { TrainingTab } from '../components/range/TrainingTab'
import { ConfirmDialog } from '../components/common/ConfirmDialog'
import { SaveBlueprintModal } from '../components/blueprints'
import { CreateSnapshotModal } from '../components/range/CreateSnapshotModal'
import { ScenarioPickerModal, VMMappingModal } from '../components/scenarios'
import type { Scenario } from '../types'

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
  // Image Library data for VM creation
  const [baseImages, setBaseImages] = useState<BaseImage[]>([])
  const [goldenImages, setGoldenImages] = useState<GoldenImageLibrary[]>([])
  const [availableSnapshots, setAvailableSnapshots] = useState<SnapshotWithLineage[]>([])
  const [loading, setLoading] = useState(true)

  // Tab state
  const [activeTab, setActiveTab] = useState<'builder' | 'training' | 'diagnostics' | 'activity'>('builder')

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
  // Image Library source types: base (fresh container/ISO), golden (configured), snapshot (fork)
  const [vmSourceType, setVmSourceType] = useState<'base' | 'golden' | 'snapshot'>('base')
  const [vmForm, setVmForm] = useState<Partial<VMCreate>>({
    hostname: '',
    ip_address: '',
    network_id: '',
    // Image Library source fields (mutually exclusive)
    base_image_id: '',
    golden_image_id: '',
    snapshot_id: '',
    // Legacy template_id for backward compatibility
    template_id: '',
    cpu: 2,
    ram_mb: 2048,
    disk_gb: 20,
    // Windows-specific (version inherited from image)
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
    linux_user_sudo: true,
    // Boot source for QEMU VMs (Windows/Linux)
    boot_source: undefined,
    // Target architecture for QEMU VMs
    arch: undefined as 'x86_64' | 'arm64' | undefined
  })
  const [showWindowsOptions, setShowWindowsOptions] = useState(false)
  const [showLinuxISOOptions, setShowLinuxISOOptions] = useState(false)
  const [showLinuxContainerOptions, setShowLinuxContainerOptions] = useState(false)
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [linuxContainerType, setLinuxContainerType] = useState<'kasmvnc' | 'linuxserver' | null>(null)

  // Console state
  const [consoleVm, setConsoleVm] = useState<VM | null>(null)
  const [consoleType, setConsoleType] = useState<'vnc' | 'terminal'>('vnc')
  const token = useAuthStore((state) => state.token)

  // Open console - new window by default, Shift+click for inline
  const handleOpenConsole = async (vm: VM, event: React.MouseEvent, type: 'vnc' | 'terminal' = 'vnc') => {
    if (event.shiftKey) {
      // Shift+click: Open inline modal
      setConsoleType(type)
      setConsoleVm(vm)
      return
    }

    // Default: Open in new window
    const width = type === 'vnc' ? 1280 : 900
    const height = type === 'vnc' ? 800 : 600
    const left = (window.screen.width - width) / 2
    const top = (window.screen.height - height) / 2
    window.open(
      `/console/${vm.id}?type=${type}`,
      `console_${vm.id}_${type}`,
      `width=${width},height=${height},left=${left},top=${top},menubar=no,toolbar=no,location=no,status=no,resizable=yes,scrollbars=no`
    )
  }

  // Export dialog state
  const [showExportDialog, setShowExportDialog] = useState(false)

  // Save Blueprint modal state
  const [showSaveBlueprintModal, setShowSaveBlueprintModal] = useState(false)

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

  // Loading states for actions
  const [stoppingRange, setStoppingRange] = useState(false)
  const [vmActionLoading, setVmActionLoading] = useState<string | null>(null) // VM ID being actioned

  // Delete confirmation state
  const [deleteConfirm, setDeleteConfirm] = useState<{
    type: 'network' | 'vm' | 'range' | null
    item: Network | VM | Range | null
    isLoading: boolean
  }>({ type: null, item: null, isLoading: false })

  // Snapshot modal state
  const [snapshotVm, setSnapshotVm] = useState<VM | null>(null)

  // Scenario modal state
  const [showScenarioPicker, setShowScenarioPicker] = useState(false)
  const [selectedScenario, setSelectedScenario] = useState<Scenario | null>(null)

  // Architecture detection for emulation warning
  const isArmHost = useIsArmHost()

  // Track VMs with recent status changes for pulse animation
  const [recentlyChangedVms, setRecentlyChangedVms] = useState<Set<string>>(new Set())
  const vmStatusRef = useRef<Record<string, string>>({})

  // Handle real-time events
  const handleRealtimeEvent = useCallback((event: RealtimeEvent) => {
    // Show toast for significant events
    if (event.event_type === 'deployment_completed') {
      toast.success(event.message)
      fetchData()
    } else if (event.event_type === 'deployment_failed') {
      toast.error(event.message)
      fetchData()
    } else if (event.event_type === 'vm_error') {
      toast.error(`VM Error: ${event.message}`)
    } else if (event.event_type === 'vm_started' || event.event_type === 'vm_stopped') {
      // Refresh to get latest VM status
      fetchData()
    }
  }, [])

  // Handle VM status changes with pulse animation
  const handleVmStatusChange = useCallback((vmId: string, newStatus: string) => {
    const previousStatus = vmStatusRef.current[vmId]
    if (previousStatus && previousStatus !== newStatus) {
      // Trigger pulse animation
      setRecentlyChangedVms(prev => new Set(prev).add(vmId))
      // Remove after animation completes
      setTimeout(() => {
        setRecentlyChangedVms(prev => {
          const next = new Set(prev)
          next.delete(vmId)
          return next
        })
      }, 1000)
    }
    vmStatusRef.current[vmId] = newStatus
  }, [])

  // Handle range status changes
  const handleStatusChange = useCallback((rangeStatus: string, vmStatuses: Record<string, string>) => {
    // Update local state with new statuses
    setRange(prev => prev ? { ...prev, status: rangeStatus as Range['status'] } : null)

    // Check for individual VM status changes
    Object.entries(vmStatuses).forEach(([vmId, status]) => {
      handleVmStatusChange(vmId, status)
    })

    setVms(prev => prev.map(vm => {
      const newStatus = vmStatuses[vm.id]
      if (newStatus && newStatus !== vm.status) {
        return { ...vm, status: newStatus as VM['status'] }
      }
      return vm
    }))
  }, [handleVmStatusChange])

  // Real-time WebSocket connection
  const { connectionState } = useRealtimeRange(id || null, {
    onEvent: handleRealtimeEvent,
    onStatusChange: handleStatusChange,
    enabled: !!id,
  })

  // Calculate error count for diagnostics badge
  const errorCount = useMemo(() => {
    if (!range) return 0
    let count = 0
    if (range.status === 'error') count++
    if (range.router?.status === 'error') count++
    count += vms.filter(vm => vm.status === 'error').length
    return count
  }, [range, vms])

  // Get the currently selected base image for the VM form
  const selectedBaseImage = useMemo(() => {
    return baseImages.find(img => img.id === vmForm.base_image_id) || null
  }, [baseImages, vmForm.base_image_id])

  // Get the currently selected golden image for the VM form
  const selectedGoldenImage = useMemo(() => {
    return goldenImages.find(img => img.id === vmForm.golden_image_id) || null
  }, [goldenImages, vmForm.golden_image_id])

  // Get the currently selected snapshot for the VM form
  const selectedSnapshot = useMemo(() => {
    return availableSnapshots.find(s => s.id === vmForm.snapshot_id) || null
  }, [availableSnapshots, vmForm.snapshot_id])

  // Get the currently selected image (any type) for emulation checks
  const selectedImage = useMemo(() => {
    if (vmSourceType === 'base') return selectedBaseImage
    if (vmSourceType === 'golden') return selectedGoldenImage
    if (vmSourceType === 'snapshot') return selectedSnapshot
    return null
  }, [vmSourceType, selectedBaseImage, selectedGoldenImage, selectedSnapshot])

  // Extract subnet prefix from first network for blueprint suggestion
  const suggestedPrefix = networks?.[0]?.subnet
    ? networks[0].subnet.split('.').slice(0, 2).join('.')
    : '10.100';

  // State for available IPs dropdown
  const [availableIps, setAvailableIps] = useState<string[]>([])
  const [loadingIps, setLoadingIps] = useState(false)

  // Helper: Calculate default gateway from subnet (e.g., 10.0.1.0/24 -> 10.0.1.1)
  const calculateGatewayFromSubnet = useCallback((subnet: string): string => {
    const match = subnet.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\/\d{1,2}$/)
    if (match) {
      return `${match[1]}.${match[2]}.${match[3]}.1`
    }
    return ''
  }, [])

  // Fetch available IPs when network is selected for VM
  const fetchAvailableIps = useCallback(async (networkId: string) => {
    if (!networkId) {
      setAvailableIps([])
      return
    }
    setLoadingIps(true)
    try {
      const response = await vmsApi.getAvailableIps(networkId, 50)
      setAvailableIps(response.available_ips || [])
      // Auto-select the first available IP
      if (response.available_ips?.length > 0) {
        setVmForm(prev => ({ ...prev, ip_address: response.available_ips[0] }))
      }
    } catch (err) {
      console.error('Failed to fetch available IPs:', err)
      setAvailableIps([])
    } finally {
      setLoadingIps(false)
    }
  }, [])

  // Handler: When subnet changes, auto-fill gateway
  const handleSubnetChange = useCallback((subnet: string) => {
    const gateway = calculateGatewayFromSubnet(subnet)
    setNetworkForm(prev => ({ ...prev, subnet, gateway }))
  }, [calculateGatewayFromSubnet])

  // Handler: When network is selected for VM, fetch available IPs and set prefix
  const handleNetworkSelectForVm = useCallback((networkId: string) => {
    setVmForm(prev => ({ ...prev, network_id: networkId, ip_address: '' }))
    fetchAvailableIps(networkId)
  }, [fetchAvailableIps])

  // Determine if selected image requires emulation on ARM host
  const imageRequiresEmulation = useMemo(() => {
    if (!isArmHost || !selectedImage) return false

    // Windows always requires emulation on ARM (x86-only via QEMU)
    if (selectedImage.os_type === 'windows') return true

    // For base images, check image_type
    if (vmSourceType === 'base' && selectedBaseImage) {
      // ISO-based images may need emulation
      if (selectedBaseImage.image_type === 'iso') {
        // These distros have native ARM64 ISO support
        const arm64Distros = ['ubuntu', 'debian', 'fedora', 'alpine', 'rocky', 'alma', 'kali']
        const imageName = selectedBaseImage.name?.toLowerCase() || ''
        return !arm64Distros.some(distro => imageName.includes(distro))
      }
      // Container images are typically multi-arch
      return false
    }

    // For golden images and snapshots, check vm_type
    if (selectedImage.vm_type === 'linux_vm' || selectedImage.vm_type === 'windows_vm') {
      // QEMU-based VMs may need emulation
      const arm64Distros = ['ubuntu', 'debian', 'fedora', 'alpine', 'rocky', 'alma', 'kali']
      const imageName = selectedImage.name?.toLowerCase() || ''
      return !arm64Distros.some(distro => imageName.includes(distro))
    }

    // Docker containers are typically multi-arch, no emulation needed
    return false
  }, [isArmHost, selectedImage, vmSourceType, selectedBaseImage])

  const fetchData = async () => {
    if (!id) return
    try {
      const [rangeRes, networksRes, vmsRes, baseImagesRes, goldenImagesRes, snapshotsRes] = await Promise.all([
        rangesApi.get(id),
        networksApi.list(id),
        vmsApi.list(id),
        imagesApi.listBaseImages(),
        imagesApi.listGoldenImages(),
        imagesApi.listLibrarySnapshots()  // Fetch all global snapshots for VM creation
      ])
      setRange(rangeRes.data)
      setNetworks(networksRes.data)
      setVms(vmsRes.data)
      setBaseImages(baseImagesRes.data)
      setGoldenImages(goldenImagesRes.data)
      setAvailableSnapshots(snapshotsRes.data)
    } catch (err) {
      console.error('Failed to fetch range:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [id])

  // Handle Escape key to close console modal
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && consoleVm) {
        setConsoleVm(null)
      }
    }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [consoleVm])

  const handleDeploy = async () => {
    if (!id || !range) return

    const previousStatus = range.status
    // Optimistic update - immediately show deploying status
    setRange({ ...range, status: 'deploying' })
    toast.success(`Deploying "${range.name}"...`)

    try {
      await rangesApi.deploy(id)
      // Don't fetch immediately - let DeploymentProgress poll for status
      // The component will call onDeploymentComplete when done
    } catch (err: any) {
      // Revert optimistic update on error
      setRange({ ...range, status: previousStatus })
      const detail = err.response?.data?.detail
      // Check if this is a validation error with structured detail
      if (detail && typeof detail === 'object' && detail.errors) {
        // Display validation errors clearly
        const errorList = detail.errors.map((e: string) => `• ${e}`).join('\n')
        alert(`${detail.message || 'Deployment validation failed'}\n\n${errorList}\n\n${detail.hint || ''}`)
      } else {
        alert(typeof detail === 'string' ? detail : 'Failed to deploy range')
      }
    }
  }

  const handleStart = async () => {
    if (!id || !range) return
    toast.info(`Starting "${range.name}"...`)
    try {
      await rangesApi.start(id)
      toast.success(`Range "${range.name}" started`)
      fetchData()
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to start range')
    }
  }

  const handleStop = async () => {
    if (!id || !range) return
    setStoppingRange(true)
    toast.info(`Stopping "${range.name}"...`)
    try {
      await rangesApi.stop(id)
      toast.success(`Range "${range.name}" stopped`)
      fetchData()
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to stop range')
    } finally {
      setStoppingRange(false)
    }
  }

  const handleDeleteRange = () => {
    if (!range) return
    setDeleteConfirm({ type: 'range', item: range, isLoading: false })
  }

  const confirmDeleteRange = async () => {
    if (!deleteConfirm.item || deleteConfirm.type !== 'range') return
    setDeleteConfirm(prev => ({ ...prev, isLoading: true }))
    try {
      await rangesApi.delete((deleteConfirm.item as Range).id)
      toast.success('Range deleted successfully')
      navigate('/ranges')
    } catch (err: any) {
      setDeleteConfirm({ type: null, item: null, isLoading: false })
      toast.error(err.response?.data?.detail || 'Failed to delete range')
    }
  }

  const handleSync = async () => {
    if (!id) return
    try {
      const response = await rangesApi.sync(id)
      const result = response.data
      if (result.status === 'no_changes') {
        alert('All resources already provisioned')
      } else {
        alert(`Synced ${result.networks_synced} networks and ${result.vms_synced} VMs`)
      }
      fetchData()
    } catch (err: any) {
      const detail = err.response?.data?.detail
      if (detail && typeof detail === 'object' && detail.errors) {
        const errorList = detail.errors.map((e: string) => `• ${e}`).join('\n')
        alert(`${detail.message || 'Sync validation failed'}\n\n${errorList}\n\n${detail.hint || ''}`)
      } else {
        alert(typeof detail === 'string' ? detail : 'Failed to sync range')
      }
    }
  }

  // Check if there are unprovisioned resources that need sync
  const hasUnprovisionedResources = useMemo(() => {
    const unprovisionedNetworks = networks.filter(n => !n.docker_network_id).length
    const unprovisionedVms = vms.filter(v => !v.container_id).length
    return unprovisionedNetworks > 0 || unprovisionedVms > 0
  }, [networks, vms])

  // Scenario handlers
  const handleScenarioSelect = (scenario: Scenario) => {
    setSelectedScenario(scenario)
    setShowScenarioPicker(false)
  }

  const handleApplyScenario = async (roleMapping: Record<string, string>) => {
    if (!id || !selectedScenario) return
    await rangesApi.applyScenario(id, {
      scenario_id: selectedScenario.id,
      role_mapping: roleMapping,
    })
    setSelectedScenario(null)
    toast.success('Scenario applied successfully')
    fetchData()
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

  const handleDeleteNetwork = (network: Network) => {
    setDeleteConfirm({ type: 'network', item: network, isLoading: false })
  }

  const confirmDeleteNetwork = async () => {
    if (!deleteConfirm.item || deleteConfirm.type !== 'network') return
    const network = deleteConfirm.item as Network
    setDeleteConfirm(prev => ({ ...prev, isLoading: true }))
    try {
      await networksApi.delete(network.id)
      setDeleteConfirm({ type: null, item: null, isLoading: false })
      fetchData()
    } catch (err: any) {
      setDeleteConfirm({ type: null, item: null, isLoading: false })
      toast.error(err.response?.data?.detail || 'Failed to delete network')
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

  const handleToggleInternet = async (network: Network) => {
    if (!network.docker_network_id) {
      alert('Network must be provisioned first (deploy the range)')
      return
    }
    // Note: With DinD deployment, internet access is set via iptables at deploy time
    // Dynamic toggling requires range redeployment
    try {
      await networksApi.toggleInternet(network.id)
      fetchData()
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to toggle internet access. With DinD, you may need to redeploy.')
    }
  }

  const handleToggleDhcp = async (network: Network) => {
    if (!network.docker_network_id) {
      alert('Network must be provisioned first (deploy the range)')
      return
    }
    // Note: DHCP is not currently supported with DinD deployments
    try {
      await networksApi.toggleDhcp(network.id)
      fetchData()
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to toggle DHCP. DHCP may not be available with DinD deployment.')
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
        hostname: vmForm.hostname!,
        ip_address: usesDhcp ? '' : vmForm.ip_address!,
        cpu: vmForm.cpu!,
        ram_mb: vmForm.ram_mb!,
        disk_gb: vmForm.disk_gb!
      }

      // Add image source (exactly one of base_image_id, golden_image_id, snapshot_id)
      if (vmSourceType === 'base') {
        vmData.base_image_id = vmForm.base_image_id!
      } else if (vmSourceType === 'golden') {
        vmData.golden_image_id = vmForm.golden_image_id!
      } else {
        vmData.snapshot_id = vmForm.snapshot_id!
      }

      // Add Windows-specific settings if template is Windows
      if (showWindowsOptions) {
        // Windows version comes from template, not user selection
        if (vmForm.windows_username) vmData.windows_username = vmForm.windows_username
        if (vmForm.windows_password) vmData.windows_password = vmForm.windows_password
        vmData.display_type = vmForm.display_type || 'desktop'
        // Boot source for QEMU VMs
        if (vmForm.boot_source) vmData.boot_source = vmForm.boot_source
        // Target architecture
        if (vmForm.arch) vmData.arch = vmForm.arch
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
        // Boot source for QEMU VMs
        if (vmForm.boot_source) vmData.boot_source = vmForm.boot_source
        // Target architecture
        if (vmForm.arch) vmData.arch = vmForm.arch
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
      setVmSourceType('base')
      setVmForm({
        hostname: '', ip_address: '', network_id: '',
        base_image_id: '', golden_image_id: '', snapshot_id: '', template_id: '',
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
        linux_username: '', linux_password: '', linux_user_sudo: true,
        // Boot source reset
        boot_source: undefined,
        // Architecture reset
        arch: undefined
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
    setVmActionLoading(vm.id)
    try {
      if (action === 'start') await vmsApi.start(vm.id)
      else if (action === 'stop') await vmsApi.stop(vm.id)
      else if (action === 'restart') await vmsApi.restart(vm.id)
      const actionLabel = action === 'start' ? 'started' : action === 'stop' ? 'stopped' : 'restarted'
      toast.success(`VM ${vm.hostname} ${actionLabel}`)
      fetchData()
    } catch (err: any) {
      toast.error(err.response?.data?.detail || `Failed to ${action} VM`)
    } finally {
      setVmActionLoading(null)
    }
  }

  const handleDeleteVm = (vm: VM) => {
    setDeleteConfirm({ type: 'vm', item: vm, isLoading: false })
  }

  const confirmDeleteVm = async () => {
    if (!deleteConfirm.item || deleteConfirm.type !== 'vm') return
    const vm = deleteConfirm.item as VM
    setDeleteConfirm(prev => ({ ...prev, isLoading: true }))
    try {
      await vmsApi.delete(vm.id)
      setDeleteConfirm({ type: null, item: null, isLoading: false })
      fetchData()
    } catch (err: any) {
      setDeleteConfirm({ type: null, item: null, isLoading: false })
      toast.error(err.response?.data?.detail || 'Failed to delete VM')
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
                statusColors[range.status.toLowerCase()]
              )}>
                {range.status.toLowerCase()}
              </span>
              {range.router && (
                <span className={clsx(
                  "ml-2 px-2.5 py-0.5 text-sm font-medium rounded-full flex items-center gap-1",
                  range.router.status === 'running' ? 'bg-green-100 text-green-800' :
                  range.router.status === 'error' ? 'bg-red-100 text-red-800' :
                  'bg-gray-100 text-gray-800'
                )}
                title={range.router.error_message || `DinD Container: ${range.router.status}`}
                >
                  <Router className="h-3 w-3" />
                  {range.router.status === 'running' ? 'DinD Up' :
                   range.router.status === 'error' ? 'DinD Error' :
                   range.router.status}
                </span>
              )}
            </div>
            <p className="mt-1 text-sm text-gray-500">{range.description || 'No description'}</p>
            {/* Lifecycle timestamps */}
            <div className="mt-1 text-sm text-gray-500 flex items-center gap-2">
              <RelativeTime date={range.created_at} prefix="Created " />
              {range.deployed_at && (
                <>
                  <span>-</span>
                  <RelativeTime date={range.deployed_at} prefix="Deployed " />
                </>
              )}
              {range.started_at && (
                <>
                  <span>-</span>
                  <RelativeTime date={range.started_at} prefix="Started " />
                </>
              )}
              {range.stopped_at && range.status === 'stopped' && (
                <>
                  <span>-</span>
                  <RelativeTime date={range.stopped_at} prefix="Stopped " />
                </>
              )}
            </div>
            {/* Real-time connection indicator */}
            <div className="mt-1 flex items-center gap-1.5">
              <Radio className={clsx(
                "h-3 w-3",
                connectionState === 'connected' ? 'text-green-500' :
                connectionState === 'connecting' ? 'text-yellow-500 animate-pulse' :
                'text-gray-400'
              )} />
              <span className="text-xs text-gray-400">
                {connectionState === 'connected' ? 'Live updates' :
                 connectionState === 'connecting' ? 'Connecting...' :
                 'Offline'}
              </span>
            </div>
          </div>
          <div className="mt-4 sm:mt-0 flex items-center space-x-3">
            {(range.status === 'draft' || range.status === 'error') && (
              <button
                onClick={handleDeploy}
                className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700"
              >
                <Rocket className="h-4 w-4 mr-2" />
                {range.status === 'error' ? 'Retry Deploy' : 'Deploy'}
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
                <a
                  href={`/lab/${range.id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-3 py-1.5 bg-purple-600 text-white rounded hover:bg-purple-700"
                >
                  <BookOpen className="w-4 h-4" />
                  Open Lab
                </a>
                <button
                  onClick={() => setShowScenarioPicker(true)}
                  className="inline-flex items-center px-3 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
                >
                  <Play className="h-4 w-4 mr-1" />
                  Add Scenario
                </button>
                <button
                  onClick={handleStop}
                  disabled={stoppingRange}
                  className="inline-flex items-center px-3 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {stoppingRange ? (
                    <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                  ) : (
                    <Square className="h-4 w-4 mr-1" />
                  )}
                  {stoppingRange ? 'Stopping...' : 'Stop'}
                </button>
                {hasUnprovisionedResources && (
                  <button
                    onClick={handleSync}
                    className="inline-flex items-center px-3 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-green-600 hover:bg-green-700"
                    title="Provision new networks and VMs to the running range"
                  >
                    <RotateCw className="h-4 w-4 mr-1" />
                    Sync
                  </button>
                )}
              </>
            )}
            {/* Export button - available in any status */}
            <button
              onClick={() => setShowExportDialog(true)}
              className="inline-flex items-center px-3 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
              title="Export as portable ZIP package for backup or transfer"
            >
              <Download className="h-4 w-4 mr-1" />
              Export
            </button>
            {/* Save as Blueprint button */}
            <button
              onClick={() => setShowSaveBlueprintModal(true)}
              className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
              title="Save as reusable blueprint for deploying multiple instances"
            >
              <LayoutTemplate className="h-4 w-4 mr-2" />
              Save as Blueprint
            </button>
            {/* Delete Range button */}
            <button
              onClick={handleDeleteRange}
              className="inline-flex items-center px-3 py-2 border border-red-300 rounded-md shadow-sm text-sm font-medium text-red-700 bg-white hover:bg-red-50"
              title="Delete Range"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Deployment Progress - shown when deploying */}
      {range.status === 'deploying' && (
        <div className="mb-6">
          <DeploymentProgress
            rangeId={range.id}
            rangeStatus={range.status}
            onDeploymentComplete={() => fetchData()}
          />
        </div>
      )}

      {/* Tab Navigation */}
      <div className="mb-6 border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('builder')}
            className={clsx(
              "py-2 px-1 border-b-2 font-medium text-sm",
              activeTab === 'builder'
                ? "border-primary-500 text-primary-600"
                : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
            )}
          >
            Builder
          </button>
          <button
            onClick={() => setActiveTab('training')}
            className={clsx(
              "py-2 px-1 border-b-2 font-medium text-sm flex items-center gap-2",
              activeTab === 'training'
                ? "border-primary-500 text-primary-600"
                : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
            )}
          >
            <BookOpen className="h-4 w-4" />
            Training
          </button>
          <button
            onClick={() => setActiveTab('diagnostics')}
            className={clsx(
              "py-2 px-1 border-b-2 font-medium text-sm flex items-center gap-2",
              activeTab === 'diagnostics'
                ? "border-primary-500 text-primary-600"
                : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
            )}
          >
            <Wrench className="h-4 w-4" />
            Diagnostics
            {errorCount > 0 && (
              <span className="px-1.5 py-0.5 text-xs bg-red-100 text-red-700 rounded-full">
                {errorCount}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab('activity')}
            className={clsx(
              "py-2 px-1 border-b-2 font-medium text-sm flex items-center gap-2",
              activeTab === 'activity'
                ? "border-primary-500 text-primary-600"
                : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
            )}
          >
            <Activity className="h-4 w-4" />
            Activity
          </button>
        </nav>
      </div>

      {/* Builder Tab Content */}
      {activeTab === 'builder' && (
        <>
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
                      <>
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
                        {network.vyos_interface && (
                          <>
                            <button
                              onClick={() => handleToggleInternet(network)}
                              className={clsx(
                                "p-1",
                                network.internet_enabled
                                  ? "text-green-600 hover:text-green-800"
                                  : "text-gray-400 hover:text-green-600"
                              )}
                              title={network.internet_enabled
                                ? "Internet enabled - Click to disable"
                                : "No internet - Click to enable NAT"
                              }
                            >
                              <Globe
                                className="h-4 w-4"
                                fill={network.internet_enabled ? "currentColor" : "none"}
                              />
                            </button>
                            <button
                              onClick={() => handleToggleDhcp(network)}
                              className={clsx(
                                "p-1",
                                network.dhcp_enabled
                                  ? "text-blue-600 hover:text-blue-800"
                                  : "text-gray-400 hover:text-blue-600"
                              )}
                              title={network.dhcp_enabled
                                ? "DHCP enabled - Click to disable"
                                : "DHCP disabled - Click to enable"
                              }
                            >
                              <Wifi
                                className="h-4 w-4"
                                fill={network.dhcp_enabled ? "currentColor" : "none"}
                              />
                            </button>
                          </>
                        )}
                      </>
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
            disabled={networks.length === 0 || (baseImages.length === 0 && goldenImages.length === 0 && availableSnapshots.length === 0)}
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
                const network = networks.find(n => n.id === vm.network_id)
                // Get image source name (base image, golden image, or legacy template)
                const imageName = vm.base_image?.name || vm.golden_image?.name || vm.template?.name || 'Unknown'
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
                            "ml-2 px-1.5 py-0.5 text-xs font-medium rounded transition-all",
                            statusColors[vm.status.toLowerCase()],
                            recentlyChangedVms.has(vm.id) && "animate-pulse-once ring-2 ring-blue-400"
                          )}>
                            {vm.status.toLowerCase()}
                          </span>
                        </div>
                        <p className="text-xs text-gray-500">
                          {vm.ip_address} • {imageName} • {network?.name || 'Unknown'}
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
                          disabled={vmActionLoading === vm.id}
                          className="p-1.5 text-gray-400 hover:text-green-600 disabled:opacity-50"
                          title="Start"
                        >
                          {vmActionLoading === vm.id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Play className="h-4 w-4" />
                          )}
                        </button>
                      )}
                      {vm.status === 'running' && (
                        <>
                          <button
                            onClick={(e) => handleOpenConsole(vm, e, 'vnc')}
                            className="p-1.5 text-gray-400 hover:text-blue-600"
                            title="VM Console (VNC) - Shift+click for inline"
                          >
                            <Monitor className="h-4 w-4" />
                          </button>
                          <button
                            onClick={(e) => handleOpenConsole(vm, e, 'terminal')}
                            className="p-1.5 text-gray-400 hover:text-green-600"
                            title="Container Shell - Shift+click for inline"
                          >
                            <Terminal className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => handleVmAction(vm, 'stop')}
                            disabled={vmActionLoading === vm.id}
                            className="p-1.5 text-gray-400 hover:text-yellow-600 disabled:opacity-50"
                            title="Stop"
                          >
                            {vmActionLoading === vm.id ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <Square className="h-4 w-4" />
                            )}
                          </button>
                          <button
                            onClick={() => handleVmAction(vm, 'restart')}
                            disabled={vmActionLoading === vm.id}
                            className="p-1.5 text-gray-400 hover:text-blue-600 disabled:opacity-50"
                            title="Restart"
                          >
                            {vmActionLoading === vm.id ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <RotateCw className="h-4 w-4" />
                            )}
                          </button>
                          <button
                            onClick={() => setSnapshotVm(vm)}
                            className="p-1.5 text-gray-400 hover:text-purple-600"
                            title="Create Snapshot"
                          >
                            <Camera className="h-4 w-4" />
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
        </>
      )}

      {/* Training Tab Content */}
      {activeTab === 'training' && (
        <div className="bg-white shadow rounded-lg">
          <TrainingTab
            rangeId={range.id}
            studentGuideId={range.student_guide_id || null}
            canManage={true}
            onUpdate={fetchData}
          />
        </div>
      )}

      {/* Diagnostics Tab Content */}
      {activeTab === 'diagnostics' && (
        <DiagnosticsTab
          range={range}
          networks={networks}
          vms={vms}
        />
      )}

      {/* Activity Tab Content */}
      {activeTab === 'activity' && (
        <div className="bg-white shadow rounded-lg">
          <ActivityTab rangeId={range.id} />
        </div>
      )}

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
                      onChange={(e) => handleSubnetChange(e.target.value)}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                      placeholder="10.0.1.0/24"
                    />
                    <p className="mt-1 text-xs text-gray-500">Gateway will auto-fill as .1 in subnet</p>
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

                {/* Image Library Source Type Selection */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Create from</label>
                  <div className="flex flex-wrap gap-2">
                    <label className="flex items-center">
                      <input
                        type="radio"
                        name="vmSourceType"
                        value="base"
                        checked={vmSourceType === 'base'}
                        disabled={baseImages.length === 0}
                        onChange={() => {
                          setVmSourceType('base')
                          setVmForm({
                            ...vmForm,
                            base_image_id: '',
                            golden_image_id: '',
                            snapshot_id: '',
                            template_id: '',
                            cpu: 2,
                            ram_mb: 2048,
                            disk_gb: 20
                          })
                          setShowWindowsOptions(false)
                          setShowLinuxISOOptions(false)
                          setShowLinuxContainerOptions(false)
                          setLinuxContainerType(null)
                        }}
                        className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 disabled:opacity-50"
                      />
                      <span className={clsx("ml-2 text-sm", baseImages.length === 0 ? "text-gray-400" : "text-gray-700")}>
                        Base Image
                        {baseImages.length === 0 && " (none)"}
                      </span>
                    </label>
                    <label className="flex items-center">
                      <input
                        type="radio"
                        name="vmSourceType"
                        value="golden"
                        checked={vmSourceType === 'golden'}
                        disabled={goldenImages.length === 0}
                        onChange={() => {
                          setVmSourceType('golden')
                          setVmForm({
                            ...vmForm,
                            base_image_id: '',
                            golden_image_id: '',
                            snapshot_id: '',
                            template_id: '',
                            cpu: 2,
                            ram_mb: 2048,
                            disk_gb: 20
                          })
                          setShowWindowsOptions(false)
                          setShowLinuxISOOptions(false)
                          setShowLinuxContainerOptions(false)
                          setLinuxContainerType(null)
                        }}
                        className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 disabled:opacity-50"
                      />
                      <span className={clsx("ml-2 text-sm", goldenImages.length === 0 ? "text-gray-400" : "text-gray-700")}>
                        Golden Image
                        {goldenImages.length === 0 && " (none)"}
                      </span>
                    </label>
                    <label className="flex items-center">
                      <input
                        type="radio"
                        name="vmSourceType"
                        value="snapshot"
                        checked={vmSourceType === 'snapshot'}
                        disabled={availableSnapshots.length === 0}
                        onChange={() => {
                          setVmSourceType('snapshot')
                          setVmForm({
                            ...vmForm,
                            base_image_id: '',
                            golden_image_id: '',
                            snapshot_id: '',
                            template_id: '',
                            cpu: 2,
                            ram_mb: 2048,
                            disk_gb: 20
                          })
                          setShowWindowsOptions(false)
                          setShowLinuxISOOptions(false)
                          setShowLinuxContainerOptions(false)
                          setLinuxContainerType(null)
                        }}
                        className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 disabled:opacity-50"
                      />
                      <span className={clsx("ml-2 text-sm", availableSnapshots.length === 0 ? "text-gray-400" : "text-gray-700")}>
                        Snapshot
                        {availableSnapshots.length === 0 && " (none)"}
                      </span>
                    </label>
                  </div>
                  <p className="mt-1 text-xs text-gray-500">
                    {vmSourceType === 'base' && "Fresh container or ISO install"}
                    {vmSourceType === 'golden' && "Pre-configured image from snapshot or import"}
                    {vmSourceType === 'snapshot' && "Point-in-time fork of a golden image"}
                  </p>
                </div>

                {/* Base Image Selector */}
                {vmSourceType === 'base' && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Base Image</label>
                    <select
                      required
                      value={vmForm.base_image_id}
                      onChange={(e) => {
                        const baseImage = baseImages.find(img => img.id === e.target.value)
                        const isWindows = baseImage?.os_type === 'windows'
                        const isLinuxISO = baseImage?.os_type === 'linux' && baseImage?.image_type === 'iso'
                        // Detect KasmVNC and LinuxServer containers
                        const dockerTag = baseImage?.docker_image_tag?.toLowerCase() || ''
                        const isKasmVNC = dockerTag.includes('kasmweb/')
                        const isLinuxServer = dockerTag.includes('linuxserver/') || dockerTag.includes('lscr.io/linuxserver')
                        const isLinuxContainer = baseImage?.image_type === 'container' && (isKasmVNC || isLinuxServer)
                        setShowWindowsOptions(isWindows)
                        setShowLinuxISOOptions(isLinuxISO)
                        setShowLinuxContainerOptions(isLinuxContainer)
                        setLinuxContainerType(isKasmVNC ? 'kasmvnc' : isLinuxServer ? 'linuxserver' : null)
                        setVmForm({
                          ...vmForm,
                          base_image_id: e.target.value,
                          golden_image_id: '',
                          snapshot_id: '',
                          template_id: '',
                          cpu: baseImage?.default_cpu || (isWindows ? 4 : 2),
                          ram_mb: baseImage?.default_ram_mb || (isWindows ? 8192 : 2048),
                          disk_gb: baseImage?.default_disk_gb || (isWindows ? 64 : 20),
                          windows_version: isWindows ? '11' : '',
                          display_type: 'desktop',
                          linux_username: '',
                          linux_password: '',
                          linux_user_sudo: true
                        })
                      }}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                    >
                      <option value="">Select a base image</option>
                      {baseImages.map(img => (
                        <option key={img.id} value={img.id}>
                          {img.name} ({img.image_type === 'container' ? 'Container' : 'ISO'} - {img.os_type})
                        </option>
                      ))}
                    </select>
                    {selectedBaseImage && (
                      <p className="mt-1 text-xs text-gray-500">
                        Defaults: {selectedBaseImage.default_cpu} CPU, {(selectedBaseImage.default_ram_mb / 1024).toFixed(1)}GB RAM, {selectedBaseImage.default_disk_gb}GB disk
                      </p>
                    )}
                  </div>
                )}

                {/* Golden Image Selector */}
                {vmSourceType === 'golden' && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Golden Image</label>
                    <select
                      required
                      value={vmForm.golden_image_id}
                      onChange={(e) => {
                        const goldenImage = goldenImages.find(img => img.id === e.target.value)
                        const isWindows = goldenImage?.os_type === 'windows'
                        const isLinuxVM = goldenImage?.vm_type === 'linux_vm'
                        setShowWindowsOptions(isWindows)
                        setShowLinuxISOOptions(isLinuxVM)
                        setShowLinuxContainerOptions(goldenImage?.vm_type === 'container' && !isWindows)
                        setLinuxContainerType(null)
                        // Filter display_type to only valid VMCreate values (headless not supported)
                        const displayType = goldenImage?.display_type === 'desktop' || goldenImage?.display_type === 'server'
                          ? goldenImage.display_type : 'desktop'
                        setVmForm({
                          ...vmForm,
                          base_image_id: '',
                          golden_image_id: e.target.value,
                          snapshot_id: '',
                          template_id: '',
                          cpu: goldenImage?.default_cpu || 2,
                          ram_mb: goldenImage?.default_ram_mb || 4096,
                          disk_gb: goldenImage?.default_disk_gb || 40,
                          windows_version: isWindows ? '11' : '',
                          display_type: displayType
                        })
                      }}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                    >
                      <option value="">Select a golden image</option>
                      {goldenImages.map(img => (
                        <option key={img.id} value={img.id}>
                          {img.name} ({img.source === 'snapshot' ? 'Snapshot' : 'Imported'} - {img.os_type})
                          {img.base_image && ` ← ${img.base_image.name}`}
                        </option>
                      ))}
                    </select>
                    {selectedGoldenImage && (
                      <p className="mt-1 text-xs text-gray-500">
                        Defaults: {selectedGoldenImage.default_cpu} CPU, {(selectedGoldenImage.default_ram_mb / 1024).toFixed(1)}GB RAM, {selectedGoldenImage.default_disk_gb}GB disk
                        {selectedGoldenImage.base_image && ` • From: ${selectedGoldenImage.base_image.name}`}
                      </p>
                    )}
                  </div>
                )}

                {/* Snapshot Selector */}
                {vmSourceType === 'snapshot' && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Snapshot</label>
                    <select
                      required
                      value={vmForm.snapshot_id}
                      onChange={(e) => {
                        const snapshot = availableSnapshots.find(s => s.id === e.target.value)
                        const isWindows = snapshot?.os_type === 'windows'
                        setShowWindowsOptions(isWindows)
                        setShowLinuxISOOptions(snapshot?.vm_type === 'linux_vm')
                        setShowLinuxContainerOptions(snapshot?.vm_type === 'container' && !isWindows)
                        setLinuxContainerType(null)
                        setVmForm({
                          ...vmForm,
                          base_image_id: '',
                          golden_image_id: '',
                          snapshot_id: e.target.value,
                          template_id: '',
                          cpu: snapshot?.default_cpu || 2,
                          ram_mb: snapshot?.default_ram_mb || 4096,
                          disk_gb: snapshot?.default_disk_gb || 40,
                          display_type: (snapshot?.display_type as 'desktop' | 'server') || 'desktop'
                        })
                      }}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                    >
                      <option value="">Select a snapshot</option>
                      {availableSnapshots.map(s => (
                        <option key={s.id} value={s.id}>
                          {s.name} ({s.os_type || 'unknown'})
                          {s.golden_image && ` ← ${s.golden_image.name}`}
                        </option>
                      ))}
                    </select>
                    {selectedSnapshot && (
                      <p className="mt-1 text-xs text-gray-500">
                        Defaults: {selectedSnapshot.default_cpu} CPU, {(selectedSnapshot.default_ram_mb / 1024).toFixed(1)}GB RAM, {selectedSnapshot.default_disk_gb}GB disk
                        {selectedSnapshot.golden_image && ` • Fork of: ${selectedSnapshot.golden_image.name}`}
                      </p>
                    )}
                  </div>
                )}

                {imageRequiresEmulation && (
                  <EmulationWarning className="mt-2" />
                )}
                <div>
                  <label className="block text-sm font-medium text-gray-700">Network</label>
                  <select
                    required
                    value={vmForm.network_id}
                    onChange={(e) => handleNetworkSelectForVm(e.target.value)}
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
                    {loadingIps ? (
                      <div className="mt-1 flex items-center text-gray-500 text-sm">
                        <Loader2 className="animate-spin h-4 w-4 mr-2" />
                        Loading IPs...
                      </div>
                    ) : availableIps.length > 0 ? (
                      <select
                        required
                        value={vmForm.ip_address}
                        onChange={(e) => setVmForm({ ...vmForm, ip_address: e.target.value })}
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                      >
                        {availableIps.map(ip => (
                          <option key={ip} value={ip}>{ip}</option>
                        ))}
                      </select>
                    ) : (
                      <input
                        type="text"
                        required
                        value={vmForm.ip_address}
                        onChange={(e) => setVmForm({ ...vmForm, ip_address: e.target.value })}
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                        placeholder={vmForm.network_id ? 'No available IPs' : 'Select network first'}
                        disabled={!vmForm.network_id}
                      />
                    )}
                    {vmForm.network_id && availableIps.length > 0 && (
                      <p className="mt-1 text-xs text-gray-500">{availableIps.length} IPs available</p>
                    )}
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
                    {/* Boot Source Selection - Required for QEMU VMs */}
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                      <label className="block text-sm font-medium text-gray-900 mb-2">Boot Source (Required)</label>
                      <div className="space-y-2">
                        <label className="flex items-center">
                          <input
                            type="radio"
                            name="boot_source"
                            value="golden_image"
                            checked={vmForm.boot_source === 'golden_image'}
                            onChange={() => setVmForm({ ...vmForm, boot_source: 'golden_image' })}
                            className="mr-2 text-primary-600"
                          />
                          <span className="text-sm">Golden Image (Pre-configured, fast)</span>
                        </label>
                        <label className="flex items-center">
                          <input
                            type="radio"
                            name="boot_source"
                            value="fresh_install"
                            checked={vmForm.boot_source === 'fresh_install'}
                            onChange={() => setVmForm({ ...vmForm, boot_source: 'fresh_install' })}
                            className="mr-2 text-primary-600"
                          />
                          <span className="text-sm">Fresh Install (From cached ISO)</span>
                        </label>
                      </div>
                      <p className="mt-2 text-xs text-blue-700">
                        {vmForm.boot_source === 'golden_image'
                          ? 'Golden images deploy in seconds from pre-configured snapshots.'
                          : vmForm.boot_source === 'fresh_install'
                          ? 'Fresh installs boot from cached ISOs and require initial setup.'
                          : 'Select a boot source. Images must be cached before deployment.'}
                      </p>
                    </div>
                    {/* Architecture Selection - For fresh install only */}
                    {vmForm.boot_source === 'fresh_install' && (
                      <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
                        <label className="block text-sm font-medium text-gray-900 mb-2">Target Architecture</label>
                        <div className="space-y-2">
                          <label className="flex items-center">
                            <input
                              type="radio"
                              name="windows_arch"
                              value=""
                              checked={!vmForm.arch}
                              onChange={() => setVmForm({ ...vmForm, arch: undefined })}
                              className="mr-2 text-purple-600"
                            />
                            <span className="text-sm">Host Default (Recommended)</span>
                          </label>
                          <label className="flex items-center">
                            <input
                              type="radio"
                              name="windows_arch"
                              value="x86_64"
                              checked={vmForm.arch === 'x86_64'}
                              onChange={() => setVmForm({ ...vmForm, arch: 'x86_64' })}
                              className="mr-2 text-purple-600"
                            />
                            <span className="text-sm">x86_64 (Intel/AMD)</span>
                          </label>
                          <label className="flex items-center">
                            <input
                              type="radio"
                              name="windows_arch"
                              value="arm64"
                              checked={vmForm.arch === 'arm64'}
                              onChange={() => setVmForm({ ...vmForm, arch: 'arm64' })}
                              className="mr-2 text-purple-600"
                            />
                            <span className="text-sm">ARM64 (Apple Silicon/ARM)</span>
                          </label>
                        </div>
                        <p className="mt-2 text-xs text-purple-700">
                          {!vmForm.arch
                            ? 'Uses host architecture for native performance.'
                            : 'Cross-architecture VMs run via emulation (10-20x slower).'}
                        </p>
                      </div>
                    )}
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
                    {/* Boot Source Selection - Required for QEMU VMs */}
                    <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
                      <label className="block text-sm font-medium text-gray-900 mb-2">Boot Source (Required)</label>
                      <div className="space-y-2">
                        <label className="flex items-center">
                          <input
                            type="radio"
                            name="linux_boot_source"
                            value="golden_image"
                            checked={vmForm.boot_source === 'golden_image'}
                            onChange={() => setVmForm({ ...vmForm, boot_source: 'golden_image' })}
                            className="mr-2 text-orange-600"
                          />
                          <span className="text-sm">Golden Image (Pre-configured, fast)</span>
                        </label>
                        <label className="flex items-center">
                          <input
                            type="radio"
                            name="linux_boot_source"
                            value="fresh_install"
                            checked={vmForm.boot_source === 'fresh_install'}
                            onChange={() => setVmForm({ ...vmForm, boot_source: 'fresh_install' })}
                            className="mr-2 text-orange-600"
                          />
                          <span className="text-sm">Fresh Install (From cached ISO)</span>
                        </label>
                      </div>
                      <p className="mt-2 text-xs text-orange-700">
                        {vmForm.boot_source === 'golden_image'
                          ? 'Golden images deploy in seconds from pre-configured snapshots.'
                          : vmForm.boot_source === 'fresh_install'
                          ? 'Fresh installs boot from cached ISOs and require initial setup.'
                          : 'Select a boot source. Images must be cached before deployment.'}
                      </p>
                    </div>
                    {/* Architecture Selection - For fresh install only */}
                    {vmForm.boot_source === 'fresh_install' && (
                      <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
                        <label className="block text-sm font-medium text-gray-900 mb-2">Target Architecture</label>
                        <div className="space-y-2">
                          <label className="flex items-center">
                            <input
                              type="radio"
                              name="linux_arch"
                              value=""
                              checked={!vmForm.arch}
                              onChange={() => setVmForm({ ...vmForm, arch: undefined })}
                              className="mr-2 text-purple-600"
                            />
                            <span className="text-sm">Host Default (Recommended)</span>
                          </label>
                          <label className="flex items-center">
                            <input
                              type="radio"
                              name="linux_arch"
                              value="x86_64"
                              checked={vmForm.arch === 'x86_64'}
                              onChange={() => setVmForm({ ...vmForm, arch: 'x86_64' })}
                              className="mr-2 text-purple-600"
                            />
                            <span className="text-sm">x86_64 (Intel/AMD)</span>
                          </label>
                          <label className="flex items-center">
                            <input
                              type="radio"
                              name="linux_arch"
                              value="arm64"
                              checked={vmForm.arch === 'arm64'}
                              onChange={() => setVmForm({ ...vmForm, arch: 'arm64' })}
                              className="mr-2 text-purple-600"
                            />
                            <span className="text-sm">ARM64 (Apple Silicon/ARM)</span>
                          </label>
                        </div>
                        <p className="mt-2 text-xs text-purple-700">
                          {!vmForm.arch
                            ? 'Uses host architecture for native performance.'
                            : 'Cross-architecture VMs run via emulation (10-20x slower).'}
                        </p>
                      </div>
                    )}
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

      {/* Console Modal (VNC or Terminal) */}
      {consoleVm && token && (
        <div className="fixed inset-0 z-50 overflow-hidden">
          <div className="absolute inset-0 bg-gray-900/80" onClick={() => setConsoleVm(null)} />
          <div className="relative flex items-center justify-center h-full p-4">
            <div className={clsx(
              "h-[90vh]",
              consoleType === 'vnc' ? "w-full max-w-6xl" : "w-full max-w-4xl"
            )}>
              {consoleType === 'vnc' ? (
                <VncConsole
                  vmId={consoleVm.id}
                  vmHostname={consoleVm.hostname}
                  token={token}
                  onClose={() => setConsoleVm(null)}
                />
              ) : (
                <VMConsole
                  vmId={consoleVm.id}
                  vmHostname={consoleVm.hostname}
                  token={token}
                  onClose={() => setConsoleVm(null)}
                />
              )}
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

      {/* Save Blueprint Modal */}
      {showSaveBlueprintModal && range && (
        <SaveBlueprintModal
          rangeId={range.id}
          rangeName={range.name}
          suggestedPrefix={suggestedPrefix}
          onClose={() => setShowSaveBlueprintModal(false)}
          onSuccess={() => {}}
        />
      )}

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        isOpen={deleteConfirm.type !== null}
        title={
          deleteConfirm.type === 'network' ? 'Delete Network' :
          deleteConfirm.type === 'range' ? 'Delete Range' :
          'Delete VM'
        }
        message={
          deleteConfirm.type === 'network'
            ? `Are you sure you want to delete "${(deleteConfirm.item as Network)?.name}"? This action cannot be undone.`
            : deleteConfirm.type === 'range'
            ? `Are you sure you want to delete "${(deleteConfirm.item as Range)?.name}"? This will delete all networks, VMs, and associated data. This action cannot be undone.`
            : `Are you sure you want to delete "${(deleteConfirm.item as VM)?.hostname}"? This action cannot be undone.`
        }
        confirmLabel="Delete"
        variant="danger"
        onConfirm={
          deleteConfirm.type === 'network' ? confirmDeleteNetwork :
          deleteConfirm.type === 'range' ? confirmDeleteRange :
          confirmDeleteVm
        }
        onCancel={() => setDeleteConfirm({ type: null, item: null, isLoading: false })}
        isLoading={deleteConfirm.isLoading}
      />

      {/* Create Snapshot Modal */}
      <CreateSnapshotModal
        vmId={snapshotVm?.id || ''}
        hostname={snapshotVm?.hostname || ''}
        isOpen={snapshotVm !== null}
        onClose={() => setSnapshotVm(null)}
        onSuccess={() => {
          setSnapshotVm(null)
          // Optionally refresh data if needed
        }}
      />

      {/* Scenario Picker Modal */}
      {showScenarioPicker && (
        <ScenarioPickerModal
          onSelect={handleScenarioSelect}
          onClose={() => setShowScenarioPicker(false)}
        />
      )}

      {/* VM Mapping Modal for selected scenario */}
      {selectedScenario && (
        <VMMappingModal
          scenario={selectedScenario}
          vms={vms}
          onApply={handleApplyScenario}
          onBack={() => {
            setSelectedScenario(null)
            setShowScenarioPicker(true)
          }}
          onClose={() => setSelectedScenario(null)}
        />
      )}
    </div>
  )
}
