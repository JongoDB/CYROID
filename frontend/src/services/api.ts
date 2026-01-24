// frontend/src/services/api.ts
import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'

const API_BASE_URL = '/api/v1'

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add auth token to requests
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem('token')
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Handle 401 responses
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// Version API
export interface VersionInfo {
  version: string
  commit: string
  build_date: string
  api_version: string
  app_name: string
}

export const versionApi = {
  get: () => api.get<VersionInfo>('/version'),
}

// Auth API
export interface LoginRequest {
  username: string
  password: string
}

export interface RegisterRequest {
  username: string
  email: string
  password: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  password_reset_required: boolean
}

export interface User {
  id: string
  username: string
  email: string
  role: string           // Legacy single role
  roles: string[]        // ABAC: multiple roles
  tags: string[]         // ABAC: user tags
  is_active: boolean
  is_approved: boolean
  password_reset_required: boolean
  created_at: string
}

export interface UserAttribute {
  id: string
  attribute_type: 'role' | 'tag'
  attribute_value: string
  created_at: string
}

export interface UserAttributeCreate {
  attribute_type: 'role' | 'tag'
  attribute_value: string
}

export interface PasswordChangeRequest {
  current_password: string
  new_password: string
}

export interface PasswordChangeResponse {
  message: string
}

export const authApi = {
  login: (data: LoginRequest) =>
    api.post<TokenResponse>('/auth/login', data),

  register: (data: RegisterRequest) =>
    api.post<User>('/auth/register', data),

  me: () =>
    api.get<User>('/auth/me'),

  changePassword: (data: PasswordChangeRequest) =>
    api.post<PasswordChangeResponse>('/auth/change-password', data),
}

// User Management API (admin-only)
export type UserRole = 'admin' | 'engineer' | 'student' | 'evaluator'

export interface UserUpdate {
  email?: string
  is_active?: boolean
  is_approved?: boolean
}

export interface AdminCreateUser {
  username: string
  email: string
  password: string
  roles?: string[]
  tags?: string[]
  is_approved?: boolean
}

export interface RoleInfo {
  value: UserRole
  label: string
  description: string
}

export const usersApi = {
  list: () => api.get<User[]>('/users'),
  listPending: () => api.get<User[]>('/users/pending'),
  get: (userId: string) => api.get<User>(`/users/${userId}`),
  create: (data: AdminCreateUser) => api.post<User>('/users', data),
  update: (userId: string, data: UserUpdate) => api.patch<User>(`/users/${userId}`, data),
  delete: (userId: string) => api.delete(`/users/${userId}`),
  getAvailableRoles: () => api.get<RoleInfo[]>('/users/roles/available'),
  getAllTags: () => api.get<string[]>('/users/tags/all'),

  // User approval
  approve: (userId: string) => api.post<User>(`/users/${userId}/approve`),
  deny: (userId: string) => api.post(`/users/${userId}/deny`),

  // Admin password reset
  resetPassword: (userId: string) => api.post<User>(`/users/${userId}/reset-password`),

  // Attribute management
  getAttributes: (userId: string) => api.get<UserAttribute[]>(`/users/${userId}/attributes`),
  addAttribute: (userId: string, data: UserAttributeCreate) =>
    api.post<UserAttribute>(`/users/${userId}/attributes`, data),
  removeAttribute: (userId: string, attributeId: string) =>
    api.delete(`/users/${userId}/attributes/${attributeId}`),
}

import type { Range, Network, VM, EventLog, EventLogList, VMStatsResponse, VMLogsResponse, Walkthrough, WalkthroughProgress, DeploymentStatusResponse, ScenarioDetail, ScenariosListResponse, ScenarioUpload, ApplyScenarioRequest, ApplyScenarioResponse } from '../types'

// Ranges API
export interface RangeCreate {
  name: string
  description?: string
}

export interface SyncRangeResponse {
  status: 'synced' | 'no_changes'
  message: string
  networks_synced: number
  vms_synced: number
  details?: {
    range_id: string
    networks_created: number
    vms_created: number
    images_pulled: number
    network_details: Array<{ name: string; subnet: string; docker_id: string }>
    vm_details: Array<{ hostname: string; container_id: string; vnc_port: number }>
  }
}

// VNC Status and Repair types
export interface VncVmStatus {
  vm_id: string
  hostname: string
  vm_status: string
  container_id: string | null
  ip_address: string | null
  has_db_mapping: boolean
  vnc_url: string | null
  proxy_port: number | null
  proxy_host: string | null
  original_port: number | null
  issues: string[]
}

export interface VncStatusResponse {
  range_id: string
  range_name: string
  is_dind: boolean
  dind_container_id: string | null
  dind_docker_url: string | null
  dind_mgmt_ip: string | null
  vnc_mappings_count: number
  traefik_routes_exist: boolean
  traefik_route_file: string
  socat_processes: string[]
  network_interfaces: string[]
  vms: VncVmStatus[]
  summary: {
    total_vms: number
    vms_with_vnc: number
    vms_with_issues: number
  }
}

export interface VncRepairResponse {
  status: 'repaired'
  message: string
  vnc_mappings: Record<string, {
    proxy_port: number
    proxy_host: string
    original_port: number
  }>
  traefik_route_file: string | null
}

import type {
  ExportRequest,
  ExportJobStatus,
  ImportValidationResult,
  ImportResult,
  LoadImagesResult,
} from '../types'

// Range Console types (DinD diagnostics)
export interface RangeConsoleContainer {
  id: string
  name: string
  status: string
  image: string
}

export interface RangeConsoleNetwork {
  id: string
  name: string
  driver: string
  scope: string
}

export interface RangeConsoleStats {
  container_count: number
  network_count: number
}

export interface RangeConsoleIptables {
  iptables_nat: string
}

export interface RangeConsoleRoutes {
  routes: string
}

export const rangesApi = {
  list: () => api.get<Range[]>('/ranges'),
  get: (id: string) => api.get<Range>(`/ranges/${id}`),
  create: (data: RangeCreate) => api.post<Range>('/ranges', data),
  update: (id: string, data: Partial<RangeCreate>) => api.put<Range>(`/ranges/${id}`, data),
  delete: (id: string) => api.delete(`/ranges/${id}`),
  deploy: (id: string) => api.post<Range>(`/ranges/${id}/deploy`),
  start: (id: string) => api.post<Range>(`/ranges/${id}/start`),
  stop: (id: string) => api.post<Range>(`/ranges/${id}/stop`),
  teardown: (id: string) => api.post<Range>(`/ranges/${id}/teardown`),
  sync: (id: string) => api.post<SyncRangeResponse>(`/ranges/${id}/sync`),
  getDeploymentStatus: (rangeId: string) =>
    api.get<DeploymentStatusResponse>(`/ranges/${rangeId}/deployment-status`),

  // VNC diagnostics and repair
  getVncStatus: (rangeId: string) =>
    api.get<VncStatusResponse>(`/ranges/${rangeId}/vnc-status`),
  repairVnc: (rangeId: string) =>
    api.post<VncRepairResponse>(`/ranges/${rangeId}/repair-vnc`),

  // Apply training scenario
  applyScenario: (rangeId: string, data: ApplyScenarioRequest) =>
    api.post<ApplyScenarioResponse>(`/ranges/${rangeId}/scenario`, data),

  // Comprehensive Export/Import (v2.0)
  exportFull: async (id: string, options: ExportRequest) => {
    if (options.include_docker_images) {
      // Offline export returns job status
      return api.post<ExportJobStatus>(`/ranges/${id}/export/full`, options)
    } else {
      // Online export returns file blob
      const response = await api.post(`/ranges/${id}/export/full`, options, {
        responseType: 'blob',
      })
      return response
    }
  },
  getExportJobStatus: (jobId: string) =>
    api.get<ExportJobStatus>(`/ranges/export/jobs/${jobId}`),
  downloadExport: (jobId: string) =>
    api.get(`/ranges/export/jobs/${jobId}/download`, { responseType: 'blob' }),

  validateImport: async (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<ImportValidationResult>('/ranges/import/validate', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  executeImport: async (
    file: File,
    options: {
      name_override?: string
      template_conflict_action?: 'use_existing' | 'create_new' | 'skip'
      skip_artifacts?: boolean
      skip_msel?: boolean
    } = {}
  ) => {
    const formData = new FormData()
    formData.append('file', file)
    const params = new URLSearchParams()
    if (options.name_override) params.append('name_override', options.name_override)
    if (options.template_conflict_action) params.append('template_conflict_action', options.template_conflict_action)
    if (options.skip_artifacts) params.append('skip_artifacts', 'true')
    if (options.skip_msel) params.append('skip_msel', 'true')
    const queryString = params.toString()
    const url = queryString ? `/ranges/import/execute?${queryString}` : '/ranges/import/execute'
    return api.post<ImportResult>(url, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  loadDockerImages: async (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<LoadImagesResult>('/ranges/import/load-images', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  // Range Console (DinD diagnostics)
  getConsoleContainers: (rangeId: string) =>
    api.get<RangeConsoleContainer[]>(`/ranges/${rangeId}/console/containers`),
  getConsoleNetworks: (rangeId: string) =>
    api.get<RangeConsoleNetwork[]>(`/ranges/${rangeId}/console/networks`),
  getConsoleStats: (rangeId: string) =>
    api.get<RangeConsoleStats>(`/ranges/${rangeId}/console/stats`),
  getConsoleIptables: (rangeId: string) =>
    api.get<RangeConsoleIptables>(`/ranges/${rangeId}/console/iptables`),
  getConsoleRoutes: (rangeId: string) =>
    api.get<RangeConsoleRoutes>(`/ranges/${rangeId}/console/routes`),

  // Training content
  setStudentGuide: (rangeId: string, studentGuideId: string | null) =>
    api.patch<{ student_guide_id: string | null; student_guide_title: string | null }>(
      `/ranges/${rangeId}/student-guide`,
      { student_guide_id: studentGuideId }
    ),
}

// Networks API
export interface NetworkCreate {
  range_id: string
  name: string
  subnet: string
  gateway: string
  dns_servers?: string
  dns_search?: string
  is_isolated?: boolean
  internet_enabled?: boolean
  dhcp_enabled?: boolean
}

export interface NetworkUpdate {
  name?: string
  dns_servers?: string
  dns_search?: string
  is_isolated?: boolean
  internet_enabled?: boolean
  dhcp_enabled?: boolean
}

export const networksApi = {
  list: (rangeId: string) => api.get<Network[]>(`/networks?range_id=${rangeId}`),
  get: (id: string) => api.get<Network>(`/networks/${id}`),
  create: (data: NetworkCreate) => api.post<Network>('/networks', data),
  update: (id: string, data: NetworkUpdate) => api.put<Network>(`/networks/${id}`, data),
  delete: (id: string) => api.delete(`/networks/${id}`),
  provision: (id: string) => api.post<Network>(`/networks/${id}/provision`),
  teardown: (id: string) => api.post<Network>(`/networks/${id}/teardown`),
  toggleIsolation: (id: string) => api.post<Network>(`/networks/${id}/toggle-isolation`),
  toggleInternet: (id: string) => api.post<Network>(`/networks/${id}/toggle-internet`),
  toggleDhcp: (id: string) => api.post<Network>(`/networks/${id}/toggle-dhcp`),
}

// VMs API
export interface VMCreate {
  range_id: string
  network_id: string
  // Image Library source fields (exactly one required)
  base_image_id?: string    // Fresh container or ISO install
  golden_image_id?: string  // Pre-configured image from snapshot or import
  snapshot_id?: string      // Point-in-time fork of a golden image
  template_id?: string      // Legacy: deprecated, use base_image_id instead
  hostname: string
  ip_address: string
  cpu: number
  ram_mb: number
  disk_gb: number
  position_x?: number
  position_y?: number
  // Windows-specific settings (for dockur/windows VMs)
  // Version codes: 11, 11l, 11e, 10, 10l, 10e, 8e, 7u, vu, xp, 2k, 2025, 2022, 2019, 2016, 2012, 2008, 2003
  windows_version?: string
  windows_username?: string
  windows_password?: string
  iso_url?: string
  iso_path?: string
  display_type?: 'desktop' | 'server'
  // Network configuration
  use_dhcp?: boolean
  gateway?: string
  dns_servers?: string
  // Extended configuration
  disk2_gb?: number | null
  disk3_gb?: number | null
  enable_shared_folder?: boolean
  enable_global_shared?: boolean
  language?: string | null
  keyboard?: string | null
  region?: string | null
  manual_install?: boolean
  // Linux user configuration (for cloud-init in qemux/qemu, env vars in KasmVNC/LinuxServer)
  linux_username?: string
  linux_password?: string
  linux_user_sudo?: boolean
  // Boot source for QEMU VMs (Windows/Linux via dockur/qemux)
  boot_source?: 'golden_image' | 'fresh_install'
  // Target architecture for QEMU VMs
  arch?: 'x86_64' | 'arm64'
}

// Network interface types
export interface NetworkInterface {
  network_id: string
  network_name: string
  ip_address: string
  mac_address: string
  gateway: string
  is_management: boolean
  cyroid_network_id?: string
  cyroid_network_name?: string
  subnet?: string
}

export interface VMNetworkInfo {
  vm_id: string
  hostname: string
  status: string
  interfaces: NetworkInterface[]
}

export interface RangeNetworkInfo {
  range_id: string
  vms: VMNetworkInfo[]
}

export interface AddNetworkResponse {
  success: boolean
  message: string
  interfaces: NetworkInterface[]
}

export interface AvailableIpsResponse {
  network_id: string
  network_name: string
  subnet: string
  gateway: string
  available_ips: string[]
  count: number
}

export const vmsApi = {
  list: (rangeId: string) => api.get<VM[]>(`/vms?range_id=${rangeId}`),
  get: (id: string) => api.get<VM>(`/vms/${id}`),
  create: (data: VMCreate) => api.post<VM>('/vms', data),
  update: (id: string, data: Partial<VMCreate>) => api.put<VM>(`/vms/${id}`, data),
  delete: (id: string) => api.delete(`/vms/${id}`),
  start: (id: string) => api.post<VM>(`/vms/${id}/start`),
  stop: (id: string) => api.post<VM>(`/vms/${id}/stop`),
  restart: (id: string) => api.post<VM>(`/vms/${id}/restart`),
  getStats: (id: string) => api.get<VMStatsResponse>(`/vms/${id}/stats`),
  getVmLogs: async (vmId: string, tail: number = 100) => {
    const response = await api.get<VMLogsResponse>(`/vms/${vmId}/logs`, {
      params: { tail }
    })
    return response.data
  },
  // Network interface management
  getNetworks: (id: string) => api.get<VMNetworkInfo>(`/vms/${id}/networks`),
  getRangeNetworks: (rangeId: string) => api.get<RangeNetworkInfo>(`/vms/range/${rangeId}/networks`),
  addNetwork: (vmId: string, networkId: string, ipAddress?: string) =>
    api.post<AddNetworkResponse>(`/vms/${vmId}/networks/${networkId}`, null, {
      params: ipAddress ? { ip_address: ipAddress } : undefined
    }),
  removeNetwork: (vmId: string, networkId: string) =>
    api.delete<AddNetworkResponse>(`/vms/${vmId}/networks/${networkId}`),
  // Get available IP addresses in a network subnet
  getAvailableIps: async (networkId: string, limit: number = 20): Promise<AvailableIpsResponse> => {
    const response = await api.get<AvailableIpsResponse>(`/vms/network/${networkId}/available-ips`, {
      params: { limit }
    })
    return response.data
  },
}

// Events API
export interface EventsQueryParams {
  limit?: number
  offset?: number
  event_types?: string[]
}

export const eventsApi = {
  getEvents: (rangeId: string, params: EventsQueryParams = {}) =>
    api.get<EventLogList>(`/events/${rangeId}`, {
      params: {
        limit: params.limit ?? 100,
        offset: params.offset ?? 0,
        event_types: params.event_types
      },
      paramsSerializer: {
        indexes: null // Use repeated params for arrays: event_types=a&event_types=b
      }
    }),
  getVMEvents: (vmId: string, limit = 50) =>
    api.get<EventLog[]>(`/events/vm/${vmId}`, { params: { limit } }),
}

// MSEL API
import type { MSEL, InjectExecutionResult, ConnectionList, Connection } from '../types'

export interface MSELImport {
  name: string
  content: string
}

export const mselApi = {
  import: (rangeId: string, data: MSELImport) =>
    api.post<MSEL>(`/msel/${rangeId}/import`, data),
  get: (rangeId: string) =>
    api.get<MSEL>(`/msel/${rangeId}`),
  delete: (rangeId: string) =>
    api.delete(`/msel/${rangeId}`),
  executeInject: (injectId: string) =>
    api.post<InjectExecutionResult>(`/msel/inject/${injectId}/execute`),
  skipInject: (injectId: string) =>
    api.post<{ status: string; inject_id: string }>(`/msel/inject/${injectId}/skip`),
}

// Connections API
export const connectionsApi = {
  getRangeConnections: (rangeId: string, limit = 100, offset = 0, activeOnly = false) =>
    api.get<ConnectionList>(`/connections/${rangeId}`, { params: { limit, offset, active_only: activeOnly } }),
  getVMConnections: (vmId: string, direction: 'both' | 'incoming' | 'outgoing' = 'both', limit = 50) =>
    api.get<Connection[]>(`/connections/vm/${vmId}`, { params: { direction, limit } }),
}

// Cache API
import type { CachedImage, ISOCacheStatus, GoldenImagesStatus, CacheStats, PruneResult, RecommendedImages, WindowsVersionsResponse, LinuxVersionsResponse, LinuxISODownloadResponse, LinuxISODownloadStatus, CustomISOList, CustomISODownloadResponse, CustomISOStatusResponse, ISOUploadResponse, WindowsISODownloadResponse, WindowsISODownloadStatus, AllSnapshotsStatus, SnapshotResponse, MacOSVersionsResponse, MacOSISODownloadResponse, MacOSISODownloadStatus } from '../types'

export interface DockerPullStatus {
  status: 'pulling' | 'completed' | 'failed' | 'cancelled' | 'not_found' | 'already_cached' | 'already_pulling'
  image?: string
  progress_percent?: number
  layers_total?: number
  layers_completed?: number
  error?: string
  image_id?: string
  size_bytes?: number
  message?: string
}

export interface DockerPullResponse {
  status: string
  image: string
  message: string
  image_id?: string
}

// Docker image build types
export interface BuildableImage {
  name: string
  path: string
  has_dockerfile: boolean
  has_readme: boolean
  description?: string
}

export interface BuildableImagesResponse {
  images: BuildableImage[]
  images_dir: string
  exists: boolean
}

export interface DockerBuildRequest {
  image_name: string
  tag?: string
  no_cache?: boolean
}

export interface DockerBuildResponse {
  status: string
  image_name: string
  tag: string
  build_key: string
  message: string
}

export interface DockerBuildStatus {
  status: 'building' | 'completed' | 'failed' | 'cancelled' | 'not_found' | 'already_building'
  build_key?: string
  image_name?: string
  tag?: string
  full_tag?: string
  progress_percent?: number
  current_step?: number
  total_steps?: number
  current_step_name?: string
  error?: string
  image_id?: string
  logs?: string[]
  message?: string
}

export const cacheApi = {
  // Docker images
  listImages: () => api.get<CachedImage[]>('/cache/images'),
  cacheImage: (image: string) => api.post<CachedImage>('/cache/images', { image }),
  cacheBatchImages: (images: string[]) => api.post<{ status: string; message: string }>('/cache/images/batch', images),
  removeImage: (imageId: string) => api.delete(`/cache/images/${encodeURIComponent(imageId)}`),

  // Docker image pull with progress tracking
  pullImage: (image: string) =>
    api.post<DockerPullResponse>('/cache/images/pull', { image }),
  getPullStatus: (imageKey: string) =>
    api.get<DockerPullStatus>(`/cache/images/pull/${encodeURIComponent(imageKey)}/status`),
  cancelPull: (imageKey: string) =>
    api.post(`/cache/images/pull/${encodeURIComponent(imageKey)}/cancel`),
  getActivePulls: () =>
    api.get<{ pulls: DockerPullStatus[] }>('/cache/images/pulls/active'),

  // Docker image build with progress tracking
  listBuildableImages: () =>
    api.get<BuildableImagesResponse>('/cache/images/buildable'),
  buildImage: (request: DockerBuildRequest) =>
    api.post<DockerBuildResponse>('/cache/images/build', request),
  getBuildStatus: (buildKey: string) =>
    api.get<DockerBuildStatus>(`/cache/images/build/${encodeURIComponent(buildKey)}/status`),
  cancelBuild: (buildKey: string) =>
    api.post(`/cache/images/build/${encodeURIComponent(buildKey)}/cancel`),
  getActiveBuilds: () =>
    api.get<{ builds: DockerBuildStatus[] }>('/cache/images/builds/active'),

  // Windows versions (auto-downloaded by dockur/windows)
  getWindowsVersions: () => api.get<WindowsVersionsResponse>('/cache/windows-versions'),
  getISOStatus: () => api.get<ISOCacheStatus>('/cache/isos'),

  // Linux versions (auto-downloaded by qemux/qemu)
  getLinuxVersions: () => api.get<LinuxVersionsResponse>('/cache/linux-versions'),
  getLinuxISOStatus: () => api.get<ISOCacheStatus>('/cache/linux-isos'),

  // Linux ISO Downloads
  downloadLinuxISO: (version: string, url?: string, arch?: string) =>
    api.post<LinuxISODownloadResponse>('/cache/linux-isos/download', { version, url, arch }),
  getLinuxISODownloadStatus: (version: string, arch?: string) =>
    api.get<LinuxISODownloadStatus>(`/cache/linux-isos/download/${encodeURIComponent(version)}/status${arch ? `?arch=${arch}` : ''}`),
  cancelLinuxISODownload: (version: string, arch?: string) =>
    api.post(`/cache/linux-isos/download/${encodeURIComponent(version)}/cancel${arch ? `?arch=${arch}` : ''}`),
  deleteLinuxISO: (version: string, arch?: string) =>
    api.delete(`/cache/linux-isos/${encodeURIComponent(version)}${arch ? `?arch=${arch}` : ''}`),

  // macOS ISOs (dockur/macos) - x86_64 ONLY
  getMacOSVersions: () => api.get<MacOSVersionsResponse>('/cache/macos-versions'),
  downloadMacOSISO: (version: string, url?: string) =>
    api.post<MacOSISODownloadResponse>('/cache/macos-isos/download', { version, url }),
  getMacOSISODownloadStatus: (version: string) =>
    api.get<MacOSISODownloadStatus>(`/cache/macos-isos/download/${encodeURIComponent(version)}/status`),
  cancelMacOSISODownload: (version: string) =>
    api.post(`/cache/macos-isos/download/${encodeURIComponent(version)}/cancel`),
  deleteMacOSISO: (version: string) =>
    api.delete(`/cache/macos-isos/${encodeURIComponent(version)}`),

  // Windows ISO Downloads
  downloadWindowsISO: (version: string, url?: string, arch?: 'x86_64' | 'arm64') =>
    api.post<WindowsISODownloadResponse>('/cache/isos/download', { version, url, arch: arch || 'x86_64' }),
  getWindowsISODownloadStatus: (version: string, arch?: 'x86_64' | 'arm64') =>
    api.get<WindowsISODownloadStatus>(`/cache/isos/download/${encodeURIComponent(version)}/status${arch === 'arm64' ? '?arch=arm64' : ''}`),
  cancelWindowsISODownload: (version: string, arch?: 'x86_64' | 'arm64') =>
    api.post(`/cache/isos/download/${encodeURIComponent(version)}/cancel${arch === 'arm64' ? '?arch=arm64' : ''}`),

  // Snapshots (unified API for both Windows golden images and Docker snapshots)
  getAllSnapshots: () => api.get<AllSnapshotsStatus>('/cache/snapshots'),
  createSnapshot: (containerId: string, name: string, snapshotType: 'auto' | 'windows' | 'docker' = 'auto') =>
    api.post<SnapshotResponse>('/cache/snapshots', { container_id: containerId, name, snapshot_type: snapshotType }),
  deleteSnapshot: (snapshotType: 'windows' | 'docker', name: string) =>
    api.delete(`/cache/snapshots/${snapshotType}/${encodeURIComponent(name)}`),

  // Golden images (Windows-specific, kept for backwards compatibility)
  getGoldenImages: () => api.get<GoldenImagesStatus>('/cache/golden-images'),
  createGoldenImage: (containerId: string, name: string) =>
    api.post<{ name: string; path: string; size_bytes: number; size_gb: number }>('/cache/golden-images', { container_id: containerId, name }),
  deleteGoldenImage: (name: string) => api.delete(`/cache/golden-images/${encodeURIComponent(name)}`),

  // Custom ISOs
  listCustomISOs: () => api.get<CustomISOList>('/cache/custom-isos'),
  downloadCustomISO: (name: string, url: string) =>
    api.post<CustomISODownloadResponse>('/cache/custom-isos', { name, url }),
  getCustomISOStatus: (filename: string) =>
    api.get<CustomISOStatusResponse>(`/cache/custom-isos/${encodeURIComponent(filename)}/status`),
  cancelCustomISODownload: (filename: string) =>
    api.post(`/cache/custom-isos/${encodeURIComponent(filename)}/cancel`),
  deleteCustomISO: (filename: string) =>
    api.delete(`/cache/custom-isos/${encodeURIComponent(filename)}`),

  // ISO Uploads (legacy - specific version)
  uploadWindowsISO: (file: File, version: string) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('version', version)
    return api.post<ISOUploadResponse>('/cache/isos/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  uploadLinuxISO: (file: File, distro: string) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('distro', distro)
    return api.post<ISOUploadResponse>('/cache/linux-isos/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  uploadMacOSISO: (file: File, version: string) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('version', version)
    return api.post<ISOUploadResponse>('/cache/macos-isos/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  // ISO Uploads (custom - category + name)
  uploadWindowsISOCustom: (file: File, category: string, name: string) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('category', category)
    formData.append('name', name)
    return api.post<ISOUploadResponse>('/cache/isos/upload-custom', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  uploadLinuxISOCustom: (file: File, category: string, name: string) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('category', category)
    formData.append('name', name)
    return api.post<ISOUploadResponse>('/cache/linux-isos/upload-custom', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  uploadMacOSISOCustom: (file: File, name: string) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('name', name)
    return api.post<ISOUploadResponse>('/cache/macos-isos/upload-custom', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  uploadCustomISO: (file: File, name: string) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('name', name)
    return api.post<ISOUploadResponse>('/cache/custom-isos/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  uploadDockerImage: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<{
      status: string
      images: string[]
      count: number
      size_bytes: number
      size_gb: number
    }>('/cache/docker-images/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  deleteWindowsISO: (version: string, arch?: 'x86_64' | 'arm64') =>
    api.delete(`/cache/isos/${encodeURIComponent(version)}${arch ? `?arch=${arch}` : ''}`),

  // Stats and info
  getStats: () => api.get<CacheStats>('/cache/stats'),
  getRecommendedImages: () => api.get<RecommendedImages>('/cache/recommended-images'),

  // Maintenance
  pruneImages: () => api.post<PruneResult>('/cache/prune'),
}

// Walkthrough API
export interface WalkthroughResponse {
  walkthrough: Walkthrough | null
}

export interface WalkthroughProgressUpdate {
  completed_steps: string[]
  current_phase?: string
  current_step?: string
}

export const walkthroughApi = {
  get: (rangeId: string) =>
    api.get<WalkthroughResponse>(`/ranges/${rangeId}/walkthrough`),

  getProgress: (rangeId: string) =>
    api.get<WalkthroughProgress | null>(`/ranges/${rangeId}/walkthrough/progress`),

  updateProgress: (rangeId: string, data: WalkthroughProgressUpdate) =>
    api.put<WalkthroughProgress>(`/ranges/${rangeId}/walkthrough/progress`, data),
}

// Snapshots API (for creating snapshots from VMs)
import type { Snapshot, BaseImage, GoldenImageLibrary, SnapshotWithLineage, LibraryImage, LibraryStats, SyncResult, ContainerConfig } from '../types'

export interface SnapshotCreate {
  vm_id: string
  name: string
  description?: string
}

export const snapshotsApi = {
  create: (data: SnapshotCreate) =>
    api.post<Snapshot>('/snapshots', data),

  list: (vmId?: string) =>
    api.get<Snapshot[]>('/snapshots', { params: vmId ? { vm_id: vmId } : {} }),

  get: (id: string) =>
    api.get<Snapshot>(`/snapshots/${id}`),

  restore: (id: string) =>
    api.post<Snapshot>(`/snapshots/${id}/restore`),

  delete: (id: string) =>
    api.delete(`/snapshots/${id}`),
}

// ============ Image Library API ============
// Three-tier image management: Base Images → Golden Images → Snapshots

export interface BaseImageCreate {
  name: string
  description?: string
  image_type: 'container' | 'iso'
  docker_image_id?: string
  docker_image_tag?: string
  iso_path?: string
  iso_source?: string
  iso_version?: string
  os_type: 'windows' | 'linux' | 'network' | 'custom'
  vm_type: 'container' | 'linux_vm' | 'windows_vm'
  native_arch?: string
  default_cpu?: number
  default_ram_mb?: number
  default_disk_gb?: number
  size_bytes?: number
  tags?: string[]
}

export interface BaseImageUpdate {
  name?: string
  description?: string
  default_cpu?: number
  default_ram_mb?: number
  default_disk_gb?: number
  tags?: string[]
  container_config?: ContainerConfig | null
}

export interface GoldenImageCreate {
  name: string
  description?: string
  source: 'snapshot' | 'import'
  base_image_id?: string
  os_type: 'windows' | 'linux' | 'network' | 'custom'
  vm_type: 'container' | 'linux_vm' | 'windows_vm'
  native_arch?: string
  default_cpu?: number
  default_ram_mb?: number
  default_disk_gb?: number
  display_type?: 'desktop' | 'server' | 'headless'
  vnc_port?: number
  tags?: string[]
}

export interface GoldenImageUpdate {
  name?: string
  description?: string
  default_cpu?: number
  default_ram_mb?: number
  default_disk_gb?: number
  display_type?: 'desktop' | 'server' | 'headless'
  vnc_port?: number
  tags?: string[]
}

export const imagesApi = {
  // Library Statistics
  getLibraryStats: () =>
    api.get<LibraryStats>('/images/library/stats'),

  // Unified Library View
  listLibrary: (params?: { category?: 'base' | 'golden' | 'snapshot'; os_type?: string }) =>
    api.get<LibraryImage[]>('/images/library', { params }),

  // Base Images
  listBaseImages: (params?: { image_type?: string; os_type?: string }) =>
    api.get<BaseImage[]>('/images/base', { params }),

  getBaseImage: (id: string) =>
    api.get<BaseImage>(`/images/base/${id}`),

  createBaseImage: (data: BaseImageCreate) =>
    api.post<BaseImage>('/images/base', data),

  updateBaseImage: (id: string, data: BaseImageUpdate) =>
    api.patch<BaseImage>(`/images/base/${id}`, data),

  deleteBaseImage: (id: string) =>
    api.delete(`/images/base/${id}`),

  // Golden Images
  listGoldenImages: (params?: { source?: string; os_type?: string }) =>
    api.get<GoldenImageLibrary[]>('/images/golden', { params }),

  getGoldenImage: (id: string) =>
    api.get<GoldenImageLibrary>(`/images/golden/${id}`),

  createGoldenImage: (data: GoldenImageCreate) =>
    api.post<GoldenImageLibrary>('/images/golden', data),

  updateGoldenImage: (id: string, data: GoldenImageUpdate) =>
    api.patch<GoldenImageLibrary>(`/images/golden/${id}`, data),

  deleteGoldenImage: (id: string) =>
    api.delete(`/images/golden/${id}`),

  // Golden Image Import (OVA/QCOW2/VMDK)
  importGoldenImage: (
    file: File,
    metadata: {
      name: string
      description?: string
      os_type: string
      vm_type: string
      native_arch?: string
      default_cpu?: number
      default_ram_mb?: number
      default_disk_gb?: number
    }
  ) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('name', metadata.name)
    if (metadata.description) formData.append('description', metadata.description)
    formData.append('os_type', metadata.os_type)
    formData.append('vm_type', metadata.vm_type)
    if (metadata.native_arch) formData.append('native_arch', metadata.native_arch)
    if (metadata.default_cpu) formData.append('default_cpu', String(metadata.default_cpu))
    if (metadata.default_ram_mb) formData.append('default_ram_mb', String(metadata.default_ram_mb))
    if (metadata.default_disk_gb) formData.append('default_disk_gb', String(metadata.default_disk_gb))
    return api.post<GoldenImageLibrary>('/images/golden/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  // Library Snapshots (global snapshots only)
  listLibrarySnapshots: (params?: { os_type?: string }) =>
    api.get<SnapshotWithLineage[]>('/images/snapshots', { params }),

  // Sync from Cache - creates BaseImage records for cached images/ISOs
  syncFromCache: () =>
    api.post<SyncResult>('/images/sync-from-cache'),
}

// ============ Blueprint Types ============

export interface NetworkConfig {
  name: string;
  subnet: string;
  gateway: string;
  is_isolated: boolean;
}

export interface VMConfig {
  hostname: string;
  ip_address: string;
  network_name: string;
  template_name: string;
  cpu: number;
  ram_mb: number;
  disk_gb: number;
  position_x?: number;
  position_y?: number;
}

export interface BlueprintConfig {
  networks: NetworkConfig[];
  vms: VMConfig[];
  router?: { enabled: boolean; dhcp_enabled: boolean };
  msel?: { content?: string; format: string };
}

export interface Blueprint {
  id: string;
  name: string;
  description?: string;
  version: number;
  base_subnet_prefix: string;
  next_offset: number;
  created_by: string;
  created_at: string;
  updated_at: string;
  network_count: number;
  vm_count: number;
  instance_count: number;
  has_msel?: boolean;
  has_walkthrough?: boolean;
}

export interface BlueprintDetail extends Blueprint {
  config: BlueprintConfig;
  created_by_username?: string;
}

export interface BlueprintCreate {
  range_id: string;
  name: string;
  description?: string;
  base_subnet_prefix: string;
}

export interface Instance {
  id: string;
  name: string;
  blueprint_id: string;
  blueprint_version: number;
  subnet_offset: number;
  instructor_id: string;
  range_id: string;
  created_at: string;
  range_name?: string;
  range_status?: string;
  instructor_username?: string;
}

export interface InstanceDeploy {
  name: string;
  auto_deploy?: boolean;
}

// Blueprint Import/Export Types
export interface BlueprintImportValidation {
  valid: boolean;
  blueprint_name: string;
  errors: string[];
  warnings: string[];
  conflicts: string[];
  missing_templates: string[];
  included_templates: string[];
}

export interface BlueprintImportOptions {
  template_conflict_strategy?: 'skip' | 'update' | 'error';
  new_name?: string;
}

export interface BlueprintImportResult {
  success: boolean;
  blueprint_id?: string;
  blueprint_name?: string;
  templates_created: string[];
  templates_skipped: string[];
  errors: string[];
  warnings: string[];
}

// ============ Blueprint API ============

export const blueprintsApi = {
  list: () => api.get<Blueprint[]>('/blueprints'),
  get: (id: string) => api.get<BlueprintDetail>(`/blueprints/${id}`),
  create: (data: BlueprintCreate) => api.post<BlueprintDetail>('/blueprints', data),
  update: (id: string, data: { name?: string; description?: string }) =>
    api.put<BlueprintDetail>(`/blueprints/${id}`, data),
  delete: (id: string) => api.delete(`/blueprints/${id}`),
  deploy: (id: string, data: InstanceDeploy) =>
    api.post<Instance>(`/blueprints/${id}/deploy`, data),
  listInstances: (id: string) => api.get<Instance[]>(`/blueprints/${id}/instances`),

  // Export/Import
  export: async (id: string): Promise<Blob> => {
    const response = await api.get(`/blueprints/${id}/export`, {
      responseType: 'blob',
    });
    return response.data;
  },
  validateImport: async (file: File): Promise<BlueprintImportValidation> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post<BlueprintImportValidation>(
      '/blueprints/import/validate',
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    );
    return response.data;
  },
  import: async (
    file: File,
    options: BlueprintImportOptions = {}
  ): Promise<BlueprintImportResult> => {
    const formData = new FormData();
    formData.append('file', file);
    const params = new URLSearchParams();
    if (options.template_conflict_strategy) {
      params.append('template_conflict_strategy', options.template_conflict_strategy);
    }
    if (options.new_name) {
      params.append('new_name', options.new_name);
    }
    const queryString = params.toString();
    const url = queryString ? `/blueprints/import?${queryString}` : '/blueprints/import';
    const response = await api.post<BlueprintImportResult>(url, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },
};

export const instancesApi = {
  get: (id: string) => api.get<Instance>(`/instances/${id}`),
  reset: (id: string) => api.post<Instance>(`/instances/${id}/reset`),
  redeploy: (id: string) => api.post<Instance>(`/instances/${id}/redeploy`),
  clone: (id: string) => api.post<Instance>(`/instances/${id}/clone`),
  delete: (id: string) => api.delete(`/instances/${id}`),
};

// Scenarios API (filesystem-based)
export const scenariosApi = {
  list: (category?: string, difficulty?: string) => {
    const params = new URLSearchParams()
    if (category) params.append('category', category)
    if (difficulty) params.append('difficulty', difficulty)
    const query = params.toString()
    return api.get<ScenariosListResponse>(`/scenarios${query ? `?${query}` : ''}`)
  },
  get: (id: string) => api.get<ScenarioDetail>(`/scenarios/${id}`),
  create: (data: ScenarioUpload, scenarioId?: string) => {
    const params = scenarioId ? `?scenario_id=${scenarioId}` : ''
    return api.post<ScenarioDetail>(`/scenarios${params}`, data)
  },
  update: (id: string, data: ScenarioUpload) =>
    api.put<ScenarioDetail>(`/scenarios/${id}`, data),
  delete: (id: string) => api.delete(`/scenarios/${id}`),
  upload: (file: File, overwrite: boolean = false) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('overwrite', String(overwrite))
    return api.post<ScenarioDetail>('/scenarios/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  refresh: () => api.post<{ message: string; total: number; scenarios: string[] }>('/scenarios/refresh'),
}

// ============ Admin API ============

export type CleanupMode = 'reset_to_draft' | 'purge_ranges'

export interface CleanupRequest {
  mode?: CleanupMode
  // Legacy fields for backwards compatibility
  clean_database?: boolean
  delete_database_records?: boolean
  force?: boolean
}

export interface CleanupResult {
  ranges_cleaned: number
  dind_containers_removed: number
  containers_removed: number
  networks_removed: number
  database_records_updated: number
  database_records_deleted: number
  errors: string[]
  orphaned_resources_cleaned: number
}

export interface DockerContainerInfo {
  name: string
  status: string
  range_id?: string
  vm_id?: string
}

export interface DockerNetworkInfo {
  name: string
  id: string
}

export interface DockerStatusResponse {
  containers: DockerContainerInfo[]
  container_count: number
  networks: DockerNetworkInfo[]
  network_count: number
  system_info: Record<string, unknown>
}

export const adminApi = {
  cleanupAll: (options?: CleanupRequest) =>
    api.post<CleanupResult>('/admin/cleanup-all', options || {}),
  getDockerStatus: () =>
    api.get<DockerStatusResponse>('/admin/docker-status'),
}

// ============ Infrastructure Observability API ============

export interface ServiceHealth {
  name: string
  display_name: string
  status: 'healthy' | 'unhealthy' | 'degraded' | 'unknown'
  container_id?: string
  container_status?: string
  uptime_seconds?: number
  uptime_human?: string
  cpu_percent?: number
  memory_mb?: number
  memory_limit_mb?: number
  memory_percent?: number
  ports: string[]
  health_check_output?: string
  last_checked: string
}

export interface InfrastructureServicesResponse {
  services: ServiceHealth[]
  overall_status: 'healthy' | 'degraded' | 'unhealthy'
  checked_at: string
}

export interface LogEntry {
  timestamp?: string
  level?: string
  message: string
  raw: string
}

export interface ServiceLogsResponse {
  service: string
  logs: LogEntry[]
  total_lines: number
  has_more: boolean
  filters_applied: Record<string, unknown>
}

export interface InfraDockerContainer {
  id: string
  name: string
  image: string
  status: string
  state: string
  created?: string
  ports: string[]
  labels: Record<string, string>
  is_cyroid_infra: boolean
  is_cyroid_vm: boolean
}

export interface InfraDockerNetwork {
  id: string
  name: string
  driver: string
  scope: string
  internal: boolean
  subnet?: string
  gateway?: string
  container_count: number
  is_cyroid_range: boolean
}

export interface InfraDockerVolume {
  name: string
  driver: string
  mountpoint: string
  created?: string
  size_bytes?: number
  labels: Record<string, string>
}

export interface InfraDockerImage {
  id: string
  tags: string[]
  size_bytes: number
  size_human: string
  created?: string
  is_cyroid_related: boolean
}

export interface DockerSummary {
  total_containers: number
  running_containers: number
  stopped_containers: number
  cyroid_vms: number
  cyroid_infra: number
  total_networks: number
  cyroid_networks: number
  total_volumes: number
  total_images: number
}

export interface DockerOverviewResponse {
  containers: InfraDockerContainer[]
  networks: InfraDockerNetwork[]
  volumes: InfraDockerVolume[]
  images: InfraDockerImage[]
  summary: DockerSummary
}

export interface HostMetrics {
  cpu_count: number
  cpu_percent: number
  memory_total_mb: number
  memory_used_mb: number
  memory_available_mb: number
  memory_percent: number
  disk_total_gb: number
  disk_used_gb: number
  disk_free_gb: number
  disk_percent: number
  load_average?: number[]
}

export interface DatabaseMetrics {
  connection_count: number
  active_connections: number
  idle_connections: number
  database_size_mb: number
  database_size_human: string
  table_count: number
  largest_tables: Array<{ name: string; size_bytes: number; size_human: string }>
}

export interface TaskQueueMetrics {
  queue_length: number
  workers_active: number
  messages_total: number
  delayed_messages: number
}

export interface StorageMetrics {
  minio_bucket_count: number
  minio_total_objects: number
  minio_total_size_mb: number
  iso_cache_size_mb: number
  iso_cache_files: number
  template_storage_size_mb: number
  template_storage_files: number
  vm_storage_size_mb: number
  vm_storage_dirs: number
}

export interface InfrastructureMetricsResponse {
  host: HostMetrics
  database: DatabaseMetrics
  task_queue: TaskQueueMetrics
  storage: StorageMetrics
  collected_at: string
}

export interface MigrationInfo {
  revision: string
  description: string
  applied: boolean
}

export interface ConfigItem {
  key: string
  value: string
  source: string
}

export interface SystemInfoResponse {
  version: string
  commit: string
  build_date: string
  app_name: string
  python_version: string
  docker_version?: string
  architecture: string
  is_arm: boolean
  database_revision?: string
  migrations: MigrationInfo[]
  config: ConfigItem[]
}

export interface LogsQueryParams {
  service: string
  level?: string
  search?: string
  since?: string
  until?: string
  limit?: number
  offset?: number
}

// Range Debug Types
export interface VMDebugInfo {
  id: string
  hostname: string
  status: string
  container_id: string | null
  ip_address: string | null
  base_image: string | null
  error_message: string | null
}

export interface RangeDebugInfo {
  id: string
  name: string
  status: string
  dind_container_id: string | null
  dind_container_name: string | null
  dind_docker_url: string | null
  dind_mgmt_ip: string | null
  vnc_proxy_mappings: Record<string, { proxy_port: number; proxy_host: string; original_port: number }> | null
  vms: VMDebugInfo[]
  network_count: number
  router_container_id: string | null
  router_status: string | null
}

export interface RangeDebugResponse {
  ranges: RangeDebugInfo[]
  total_count: number
  dind_containers_in_docker: string[]
}

export const infrastructureApi = {
  getServices: () =>
    api.get<InfrastructureServicesResponse>('/admin/infrastructure/services'),
  getLogs: (params: LogsQueryParams) =>
    api.get<ServiceLogsResponse>('/admin/infrastructure/logs', { params }),
  getDocker: () =>
    api.get<DockerOverviewResponse>('/admin/infrastructure/docker'),
  getMetrics: () =>
    api.get<InfrastructureMetricsResponse>('/admin/infrastructure/metrics'),
  getSystem: () =>
    api.get<SystemInfoResponse>('/admin/infrastructure/system'),
  getRangeDebug: () =>
    api.get<RangeDebugResponse>('/admin/infrastructure/ranges'),
}

// ============ Files API ============

export interface FileInfo {
  name: string
  path: string
  is_dir: boolean
  size?: number
  modified?: string
  is_text: boolean
  locked_by?: string
}

export interface FileListResponse {
  path: string
  files: FileInfo[]
  parent?: string
}

export interface FileContentResponse {
  path: string
  content: string
  size: number
  modified: string
  locked_by?: string
  lock_token?: string
}

export const filesApi = {
  listFiles: (path: string) =>
    api.get<FileListResponse>('/files', { params: { path } }),
  readFile: (path: string) =>
    api.get<FileContentResponse>('/files/content', { params: { path } }),
  createFile: (path: string, content: string) =>
    api.post<FileContentResponse>('/files', { path, content }),
  updateFile: (path: string, content: string, lockToken?: string) =>
    api.put('/files/content', { path, content, lock_token: lockToken }),
  renameFile: (oldPath: string, newPath: string) =>
    api.put('/files/rename', { old_path: oldPath, new_path: newPath }),
  deleteFile: (path: string) =>
    api.delete('/files', { params: { path } }),
  acquireLock: (path: string) =>
    api.post('/files/lock', null, { params: { path } }),
  releaseLock: (path: string) =>
    api.delete('/files/lock', { params: { path } }),
  heartbeatLock: (path: string, lockToken: string) =>
    api.post('/files/lock/heartbeat', null, { params: { path, lock_token: lockToken } }),
}

// ============ Content API ============

export type ContentType = 'student_guide' | 'msel' | 'curriculum' | 'instructor_notes' | 'reference_material' | 'custom'

export interface ContentAsset {
  id: string
  content_id: string
  filename: string
  file_path: string
  mime_type: string
  file_size: number
  sha256_hash?: string
  created_at: string
}

export interface Content {
  id: string
  title: string
  description?: string
  content_type: ContentType
  body_markdown: string
  body_html?: string
  walkthrough_data?: Walkthrough | null
  version: string
  tags: string[]
  is_published: boolean
  organization?: string
  created_by_id: string
  created_at: string
  updated_at: string
  assets: ContentAsset[]
}

export interface ContentListItem {
  id: string
  title: string
  description?: string
  content_type: ContentType
  version: string
  tags: string[]
  is_published: boolean
  created_by_id: string
  created_at: string
  updated_at: string
}

export interface ContentCreate {
  title: string
  description?: string
  content_type?: ContentType
  body_markdown?: string
  walkthrough_data?: Walkthrough | null
  tags?: string[]
  organization?: string
}

export interface ContentUpdate {
  title?: string
  description?: string
  content_type?: ContentType
  body_markdown?: string
  walkthrough_data?: Walkthrough | null
  tags?: string[]
  organization?: string
  is_published?: boolean
}

export interface ContentExport {
  title: string
  description?: string
  content_type: ContentType
  body_markdown: string
  version: string
  tags: string[]
  organization?: string
  exported_at: string
  export_format: string
}

export interface ContentImport {
  title: string
  description?: string
  content_type?: ContentType
  body_markdown: string
  version?: string
  tags?: string[]
  organization?: string
}

export interface ContentTypeOption {
  value: ContentType
  label: string
}

export const contentApi = {
  list: (params?: {
    content_type?: ContentType
    tag?: string
    search?: string
    published_only?: boolean
    limit?: number
    offset?: number
  }) =>
    api.get<ContentListItem[]>('/content', { params }),

  get: (id: string) =>
    api.get<Content>(`/content/${id}`),

  create: (data: ContentCreate) =>
    api.post<Content>('/content', data),

  update: (id: string, data: ContentUpdate) =>
    api.put<Content>(`/content/${id}`, data),

  delete: (id: string) =>
    api.delete(`/content/${id}`),

  publish: (id: string) =>
    api.post<Content>(`/content/${id}/publish`),

  unpublish: (id: string) =>
    api.post<Content>(`/content/${id}/unpublish`),

  createVersion: (id: string, newVersion: string) =>
    api.post<Content>(`/content/${id}/version`, null, { params: { new_version: newVersion } }),

  exportContent: (id: string, format: 'json' | 'md' | 'html' = 'json') =>
    api.get<ContentExport | Blob>(`/content/${id}/export`, {
      params: { format },
      ...(format !== 'json' ? { responseType: 'blob' } : {}),
    }),

  importContent: (data: ContentImport) =>
    api.post<Content>('/content/import', data),

  uploadAsset: (contentId: string, file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<ContentAsset>(`/content/${contentId}/assets`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  deleteAsset: (contentId: string, assetId: string) =>
    api.delete(`/content/${contentId}/assets/${assetId}`),

  getTypes: () =>
    api.get<ContentTypeOption[]>('/content/types/available'),

  // Student guides for range assignment
  listStudentGuides: () =>
    api.get<ContentListItem[]>('/content/student-guides/available'),
}

// ============ Training Events API ============

export type EventStatus = 'draft' | 'scheduled' | 'running' | 'completed' | 'cancelled'

export interface EventParticipant {
  id: string
  event_id: string
  user_id: string
  role: string
  is_confirmed: boolean
  created_at: string
  username?: string
}

export interface TrainingEvent {
  id: string
  name: string
  description?: string
  start_datetime: string
  end_datetime?: string
  is_all_day: boolean
  timezone: string
  organization?: string
  location?: string
  blueprint_id?: string
  content_ids: string[]
  status: EventStatus
  allowed_roles: string[]
  tags: string[]
  created_by_id: string
  range_id?: string
  created_at: string
  updated_at: string
  participant_count: number
  blueprint_name?: string
  created_by_username?: string
}

export interface TrainingEventDetail extends TrainingEvent {
  participants: EventParticipant[]
}

export interface TrainingEventListItem {
  id: string
  name: string
  description?: string
  start_datetime: string
  end_datetime?: string
  is_all_day: boolean
  timezone: string
  organization?: string
  location?: string
  status: EventStatus
  tags: string[]
  allowed_roles: string[]
  participant_count: number
  has_blueprint: boolean
  created_by_id: string
  created_at: string
}

export interface EventCreate {
  name: string
  description?: string
  start_datetime: string
  end_datetime?: string
  is_all_day?: boolean
  timezone?: string
  organization?: string
  location?: string
  blueprint_id?: string
  content_ids?: string[]
  allowed_roles?: string[]
  tags?: string[]
}

export interface EventUpdate {
  name?: string
  description?: string
  start_datetime?: string
  end_datetime?: string
  is_all_day?: boolean
  timezone?: string
  organization?: string
  location?: string
  blueprint_id?: string
  content_ids?: string[]
  allowed_roles?: string[]
  tags?: string[]
  status?: EventStatus
}

export interface EventContentItem {
  id: string
  title: string
  description?: string
  content_type: string
  body_html?: string
  version: string
}

export interface EventBriefing {
  event_id: string
  event_name: string
  user_role: string
  content_items: EventContentItem[]
  range_id?: string
  range_status?: string
}

export const trainingEventsApi = {
  list: (params?: {
    status?: EventStatus
    start_after?: string
    start_before?: string
    my_events?: boolean
    tag?: string
    search?: string
    limit?: number
    offset?: number
  }) =>
    api.get<TrainingEventListItem[]>('/training-events', { params }),

  get: (id: string) =>
    api.get<TrainingEventDetail>(`/training-events/${id}`),

  create: (data: EventCreate) =>
    api.post<TrainingEvent>('/training-events', data),

  update: (id: string, data: EventUpdate) =>
    api.put<TrainingEvent>(`/training-events/${id}`, data),

  delete: (id: string) =>
    api.delete(`/training-events/${id}`),

  publish: (id: string) =>
    api.post<TrainingEvent>(`/training-events/${id}/publish`),

  start: (id: string, autoDeploy = false) =>
    api.post<TrainingEvent>(`/training-events/${id}/start`, null, { params: { auto_deploy: autoDeploy } }),

  complete: (id: string) =>
    api.post<TrainingEvent>(`/training-events/${id}/complete`),

  cancel: (id: string) =>
    api.post<TrainingEvent>(`/training-events/${id}/cancel`),

  // Participants
  listParticipants: (eventId: string) =>
    api.get<EventParticipant[]>(`/training-events/${eventId}/participants`),

  addParticipant: (eventId: string, userId: string, role = 'student') =>
    api.post<EventParticipant>(`/training-events/${eventId}/participants`, { user_id: userId, role }),

  join: (eventId: string, role = 'student') =>
    api.post<EventParticipant>(`/training-events/${eventId}/join`, null, { params: { role } }),

  removeParticipant: (eventId: string, userId: string) =>
    api.delete(`/training-events/${eventId}/participants/${userId}`),

  // Briefing (role-based content)
  getBriefing: (eventId: string) =>
    api.get<EventBriefing>(`/training-events/${eventId}/briefing`),
}

export default api
