// frontend/src/types/index.ts

export interface User {
  id: string
  username: string
  email: string
  role: string
  is_active: boolean
  created_at: string
}

// Resource tags for ABAC visibility control
export interface ResourceTagsResponse {
  resource_type: string
  resource_id: string
  tags: string[]
}

export interface VMTemplate {
  id: string
  name: string
  description: string | null
  os_type: 'windows' | 'linux'
  os_variant: string
  base_image: string
  default_cpu: number
  default_ram_mb: number
  default_disk_gb: number
  config_script: string | null
  tags: string[]
  created_by: string
  created_at: string
  updated_at: string
}

export interface Range {
  id: string
  name: string
  description: string | null
  status: 'draft' | 'deploying' | 'running' | 'stopped' | 'archived' | 'error'
  created_by: string
  created_at: string
  updated_at: string
  networks?: Network[]
  vms?: VM[]
}

export interface Network {
  id: string
  range_id: string
  name: string
  subnet: string
  gateway: string
  dns_servers: string | null
  isolation_level: 'complete' | 'controlled' | 'open'
  docker_network_id: string | null
  created_at: string
  updated_at: string
}

export interface VM {
  id: string
  range_id: string
  network_id: string
  template_id: string
  hostname: string
  ip_address: string
  cpu: number
  ram_mb: number
  disk_gb: number
  status: 'pending' | 'creating' | 'running' | 'stopped' | 'error'
  container_id: string | null
  // Windows-specific settings (for dockur/windows VMs)
  windows_version: string | null
  windows_username: string | null
  iso_url: string | null
  iso_path: string | null
  display_type: 'desktop' | 'server' | null
  // Extended dockur/windows configuration
  use_dhcp: boolean
  disk2_gb: number | null
  disk3_gb: number | null
  enable_shared_folder: boolean
  enable_global_shared: boolean
  language: string | null
  keyboard: string | null
  region: string | null
  manual_install: boolean
  position_x: number
  position_y: number
  created_at: string
  updated_at: string
}

export interface Artifact {
  id: string
  name: string
  description: string | null
  file_path: string
  sha256_hash: string
  file_size: number
  artifact_type: 'executable' | 'script' | 'document' | 'archive' | 'config' | 'other'
  malicious_indicator: 'safe' | 'suspicious' | 'malicious'
  ttps: string[]
  tags: string[]
  uploaded_by: string
  created_at: string
  updated_at: string
}

export interface Snapshot {
  id: string
  vm_id: string
  name: string
  description: string | null
  docker_image_id: string | null
  created_at: string
  updated_at: string
}

export type EventType =
  | 'range_deployed'
  | 'range_started'
  | 'range_stopped'
  | 'range_teardown'
  | 'vm_created'
  | 'vm_started'
  | 'vm_stopped'
  | 'vm_restarted'
  | 'vm_error'
  | 'snapshot_created'
  | 'snapshot_restored'
  | 'artifact_placed'
  | 'inject_executed'
  | 'inject_failed'
  | 'connection_established'
  | 'connection_closed'

export interface EventLog {
  id: string
  range_id: string
  vm_id: string | null
  event_type: EventType
  message: string
  extra_data: string | null
  created_at: string
}

export interface EventLogList {
  events: EventLog[]
  total: number
}

export interface VMStats {
  cpu_percent: number
  memory_mb: number
  memory_limit_mb: number
  memory_percent: number
  network_rx_bytes: number
  network_tx_bytes: number
}

export interface VMStatsResponse {
  vm_id: string
  hostname?: string
  status: string
  stats: VMStats | null
}

// MSEL Types
export type InjectStatus = 'pending' | 'executing' | 'completed' | 'failed' | 'skipped'

export interface InjectAction {
  type: 'place_file' | 'run_command'
  target_vm: string
  path?: string
  artifact_id?: string
  command?: string
}

export interface Inject {
  id: string
  sequence_number: number
  inject_time_minutes: number
  title: string
  description: string | null
  actions: InjectAction[]
  status: InjectStatus
  executed_at: string | null
}

export interface MSEL {
  id: string
  name: string
  range_id: string
  content: string | null
  injects: Inject[]
}

export interface InjectExecutionResult {
  success: boolean
  inject_id: string
  status: string
  results: unknown[]
}

// Connection Types
export type ConnectionProtocol = 'tcp' | 'udp' | 'icmp'
export type ConnectionState = 'established' | 'closed' | 'timeout' | 'reset'

export interface Connection {
  id: string
  range_id: string
  src_vm_id: string | null
  src_ip: string
  src_port: number
  dst_vm_id: string | null
  dst_ip: string
  dst_port: number
  protocol: ConnectionProtocol
  state: ConnectionState
  bytes_sent: number
  bytes_received: number
  started_at: string
  ended_at: string | null
}

export interface ConnectionList {
  connections: Connection[]
  total: number
}

// Cache Types
export interface CachedImage {
  id: string
  tags: string[]
  size_bytes: number
  size_gb: number
  created: string | null
}

export interface CachedISO {
  filename: string
  path: string
  size_bytes: number
  size_gb: number
}

export interface ISOCacheStatus {
  cache_dir: string
  total_count: number
  isos: CachedISO[]
}

export interface GoldenImage {
  name: string
  path: string
  size_bytes: number
  size_gb: number
  type?: 'windows'
}

export interface GoldenImagesStatus {
  template_dir: string
  total_count: number
  golden_images: GoldenImage[]
}

// Docker container snapshots
export interface DockerSnapshot {
  id: string
  short_id: string
  tags: string[]
  size_bytes: number
  size_gb: number
  created: string | null
  type: 'docker'
}

// Combined snapshots response
export interface AllSnapshotsStatus {
  windows_golden_images: GoldenImage[]
  docker_snapshots: DockerSnapshot[]
  total_windows: number
  total_docker: number
  template_dir: string
}

export interface CreateSnapshotRequest {
  container_id: string
  name: string
  snapshot_type?: 'auto' | 'windows' | 'docker'
}

export interface SnapshotResponse {
  name: string
  id?: string
  short_id?: string
  path?: string
  size_bytes: number
  size_gb: number
  type: 'windows' | 'docker'
}

export interface CacheStats {
  docker_images: {
    count: number
    total_size_bytes: number
    total_size_gb: number
  }
  windows_isos: {
    count: number
    total_size_bytes: number
    total_size_gb: number
    cache_dir: string
  }
  golden_images: {
    count: number
    total_size_bytes: number
    total_size_gb: number
    storage_dir: string
  }
  total_cache_size_gb: number
}

export interface RecommendedImage {
  image?: string
  version?: string
  description: string
}

export interface WindowsVersion {
  version: string
  name: string
  size_gb: number
  category: 'desktop' | 'server' | 'legacy'
  cached?: boolean
  download_url: string  // All versions now have direct download URLs
}

export interface WindowsISODownloadResponse {
  status: 'downloading' | 'no_direct_download'
  version: string
  name: string
  filename?: string
  destination?: string
  source_url?: string
  expected_size_gb?: number
  message: string
  download_page?: string
  instructions?: string
}

export interface WindowsISODownloadStatus {
  status: 'downloading' | 'completed' | 'failed' | 'not_found'
  version: string
  filename?: string
  path?: string
  progress_bytes?: number
  progress_gb?: number
  total_bytes?: number
  total_gb?: number
  progress_percent?: number
  size_bytes?: number
  size_gb?: number
  error?: string
  message?: string
}

export interface WindowsVersionsResponse {
  desktop: WindowsVersion[]
  server: WindowsVersion[]
  legacy: WindowsVersion[]
  all: WindowsVersion[]
  cache_dir: string
  cached_count: number
  total_count: number
  note: string
}

export interface RecommendedImage {
  image?: string
  version?: string
  description: string
  category?: 'desktop' | 'workstation' | 'server' | 'services'
  access?: 'web' | 'vnc' | 'rdp'  // Access method for desktop images
  cached?: boolean
}

export interface RecommendedImages {
  desktop: RecommendedImage[]
  workstation: RecommendedImage[]
  server: RecommendedImage[]
  services: RecommendedImage[]
  linux: RecommendedImage[]
  windows: WindowsVersion[]
}

export interface ISOUploadResponse {
  status: string
  version?: string
  name?: string
  filename: string
  path: string
  size_bytes: number
  size_gb: number
}

// Custom ISO Types
export interface CustomISO {
  name: string
  filename: string
  path: string
  url: string
  size_bytes: number
  size_gb: number
  downloaded_at: string
}

export interface CustomISOList {
  cache_dir: string
  total_count: number
  isos: CustomISO[]
}

export interface CustomISODownloadResponse {
  status: string
  message: string
  filename: string
  destination: string
}

export interface CustomISOStatusResponse {
  status: 'downloading' | 'completed'
  filename: string
  name?: string
  path?: string
  size_bytes?: number
  size_gb?: number
  current_size_bytes?: number
  current_size_gb?: number
  downloaded_at?: string
}
