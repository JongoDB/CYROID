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
export type UserRole = 'admin' | 'engineer' | 'facilitator' | 'evaluator'

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

// Templates API
import type { VMTemplate, Range, Network, VM, EventLog, EventLogList, VMStatsResponse, VMLogsResponse, ResourceTagsResponse, Walkthrough, WalkthroughProgress, DeploymentStatusResponse } from '../types'

export interface VMTemplateCreate {
  name: string
  description?: string
  os_type: 'windows' | 'linux' | 'custom'
  os_variant: string
  base_image: string
  default_cpu?: number
  default_ram_mb?: number
  default_disk_gb?: number
  config_script?: string
  tags?: string[]
  cached_iso_path?: string  // For custom ISOs
}

export const templatesApi = {
  list: () => api.get<VMTemplate[]>('/templates'),
  get: (id: string) => api.get<VMTemplate>(`/templates/${id}`),
  create: (data: VMTemplateCreate) => api.post<VMTemplate>('/templates', data),
  update: (id: string, data: Partial<VMTemplateCreate>) => api.put<VMTemplate>(`/templates/${id}`, data),
  delete: (id: string) => api.delete(`/templates/${id}`),
  clone: (id: string) => api.post<VMTemplate>(`/templates/${id}/clone`),
  // Visibility tag management (ABAC)
  getTags: (id: string) => api.get<ResourceTagsResponse>(`/templates/${id}/tags`),
  addTag: (id: string, tag: string) => api.post(`/templates/${id}/tags`, { tag }),
  removeTag: (id: string, tag: string) => api.delete(`/templates/${id}/tags/${encodeURIComponent(tag)}`),
}

// Ranges API
export interface RangeCreate {
  name: string
  description?: string
}

import type {
  ExportRequest,
  ExportJobStatus,
  ImportValidationResult,
  ImportResult,
  LoadImagesResult,
} from '../types'

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
  getDeploymentStatus: (rangeId: string) =>
    api.get<DeploymentStatusResponse>(`/ranges/${rangeId}/deployment-status`),

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
  template_id: string
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
  // Linux user configuration (for cloud-init in qemus/qemu, env vars in KasmVNC/LinuxServer)
  linux_username?: string
  linux_password?: string
  linux_user_sudo?: boolean
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
import type { CachedImage, ISOCacheStatus, GoldenImagesStatus, CacheStats, RecommendedImages, WindowsVersionsResponse, LinuxVersionsResponse, LinuxISODownloadResponse, LinuxISODownloadStatus, CustomISOList, CustomISODownloadResponse, CustomISOStatusResponse, ISOUploadResponse, WindowsISODownloadResponse, WindowsISODownloadStatus, AllSnapshotsStatus, SnapshotResponse } from '../types'

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

  // Windows versions (auto-downloaded by dockur/windows)
  getWindowsVersions: () => api.get<WindowsVersionsResponse>('/cache/windows-versions'),
  getISOStatus: () => api.get<ISOCacheStatus>('/cache/isos'),

  // Linux versions (auto-downloaded by qemus/qemu)
  getLinuxVersions: () => api.get<LinuxVersionsResponse>('/cache/linux-versions'),
  getLinuxISOStatus: () => api.get<ISOCacheStatus>('/cache/linux-isos'),

  // Linux ISO Downloads
  downloadLinuxISO: (version: string, url?: string) =>
    api.post<LinuxISODownloadResponse>('/cache/linux-isos/download', { version, url }),
  getLinuxISODownloadStatus: (version: string) =>
    api.get<LinuxISODownloadStatus>(`/cache/linux-isos/download/${encodeURIComponent(version)}/status`),
  cancelLinuxISODownload: (version: string) =>
    api.post(`/cache/linux-isos/download/${encodeURIComponent(version)}/cancel`),
  deleteLinuxISO: (version: string) =>
    api.delete(`/cache/linux-isos/${encodeURIComponent(version)}`),

  // Windows ISO Downloads
  downloadWindowsISO: (version: string, url?: string) =>
    api.post<WindowsISODownloadResponse>('/cache/isos/download', { version, url }),
  getWindowsISODownloadStatus: (version: string) =>
    api.get<WindowsISODownloadStatus>(`/cache/isos/download/${encodeURIComponent(version)}/status`),
  cancelWindowsISODownload: (version: string) =>
    api.post(`/cache/isos/download/${encodeURIComponent(version)}/cancel`),

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

  // ISO Uploads
  uploadWindowsISO: (file: File, version: string) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('version', version)
    return api.post<ISOUploadResponse>('/cache/isos/upload', formData, {
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
  deleteWindowsISO: (version: string) =>
    api.delete(`/cache/isos/${encodeURIComponent(version)}`),

  // Stats and info
  getStats: () => api.get<CacheStats>('/cache/stats'),
  getRecommendedImages: () => api.get<RecommendedImages>('/cache/recommended-images'),
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
import type { Snapshot } from '../types'

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
};

export const instancesApi = {
  get: (id: string) => api.get<Instance>(`/instances/${id}`),
  reset: (id: string) => api.post<Instance>(`/instances/${id}/reset`),
  redeploy: (id: string) => api.post<Instance>(`/instances/${id}/redeploy`),
  clone: (id: string) => api.post<Instance>(`/instances/${id}/clone`),
  delete: (id: string) => api.delete(`/instances/${id}`),
};

export default api
