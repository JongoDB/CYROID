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
  os_type: 'windows' | 'linux' | 'custom' | 'network'
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
  // OS family grouping for wizard version selection
  os_family?: string   // e.g., "windows-server", "ubuntu-server"
  os_version?: string  // e.g., "2022", "22.04"
}

export interface Range {
  id: string
  name: string
  description: string | null
  status: 'draft' | 'deploying' | 'running' | 'stopped' | 'archived' | 'error'
  error_message: string | null
  created_by: string
  created_at: string
  updated_at: string
  deployed_at: string | null
  started_at: string | null
  stopped_at: string | null
  network_count: number
  vm_count: number
  networks?: Network[]
  vms?: VM[]
  router?: RangeRouter | null
}

export interface Network {
  id: string
  range_id: string
  name: string
  subnet: string
  gateway: string
  dns_servers: string | null
  dns_search: string | null
  docker_network_id: string | null
  is_isolated: boolean
  internet_enabled: boolean
  dhcp_enabled: boolean
  vyos_interface: string | null
  created_at: string
  updated_at: string
}

export interface RangeRouter {
  id: string
  range_id: string
  container_id: string | null
  management_ip: string | null
  status: 'pending' | 'creating' | 'running' | 'stopped' | 'error'
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface VM {
  id: string
  range_id: string
  network_id: string
  // Image Library source fields (one of these will be set)
  base_image_id?: string | null
  golden_image_id?: string | null
  template_id?: string | null  // Legacy, deprecated
  // Image Library relationships
  base_image?: {
    id: string
    name: string
    image_type: 'container' | 'iso'
    os_type: string
  } | null
  golden_image?: {
    id: string
    name: string
    source: 'snapshot' | 'import'
    os_type: string
  } | null
  template?: {
    id: string
    name: string
    os_type: string
    os_variant?: string
  } | null  // Legacy, deprecated
  hostname: string
  ip_address: string
  cpu: number
  ram_mb: number
  disk_gb: number
  status: 'pending' | 'creating' | 'running' | 'stopped' | 'error'
  error_message: string | null
  container_id: string | null
  // Windows-specific settings (for dockur/windows VMs)
  windows_version: string | null
  windows_username: string | null
  iso_url: string | null
  iso_path: string | null
  display_type: 'desktop' | 'server' | 'headless' | null
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
  // Linux user configuration
  linux_username: string | null
  linux_user_sudo: boolean
  // Boot source for QEMU VMs (Windows/Linux via dockur/qemux)
  boot_source: 'golden_image' | 'fresh_install' | null
  // Target architecture for QEMU VMs
  arch: 'x86_64' | 'arm64' | null
  position_x: number
  position_y: number
  created_at: string
  updated_at: string
  // Emulation fields (for cross-architecture support)
  emulated?: boolean
  emulation_warning?: string | null
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
  vm_id: string | null
  name: string
  description: string | null
  docker_image_id: string | null
  docker_image_tag: string | null
  os_type: string | null
  vm_type: string | null
  default_cpu: number
  default_ram_mb: number
  default_disk_gb: number
  display_type: string | null
  is_global: boolean
  tags: string[]
  created_at: string
  updated_at: string
}

export type EventType =
  // Deployment progress events
  | 'deployment_started'
  | 'deployment_step'
  | 'deployment_completed'
  | 'deployment_failed'
  | 'router_creating'
  | 'router_created'
  | 'network_creating'
  | 'network_created'
  | 'vm_creating'
  // Range lifecycle events
  | 'range_deployed'
  | 'range_started'
  | 'range_stopped'
  | 'range_teardown'
  // VM lifecycle events
  | 'vm_created'
  | 'vm_started'
  | 'vm_stopped'
  | 'vm_restarted'
  | 'vm_error'
  // Other events
  | 'snapshot_created'
  | 'snapshot_restored'
  | 'artifact_placed'
  | 'inject_executed'
  | 'inject_failed'
  | 'connection_established'
  | 'connection_closed'

export interface UserBasic {
  id: string
  username: string
  email: string
}

export interface EventLog {
  id: string
  range_id: string
  vm_id: string | null
  network_id: string | null
  user_id: string | null
  user: UserBasic | null
  event_type: EventType
  message: string
  extra_data: string | null
  created_at: string
}

export interface EventLogList {
  events: EventLog[]
  total: number
}

// Deployment Status Types
export interface ResourceStatus {
  id?: string
  name: string
  status: 'pending' | 'creating' | 'starting' | 'running' | 'created' | 'stopped' | 'failed'
  statusDetail?: string
  durationMs?: number
}

export interface NetworkStatus extends ResourceStatus {
  subnet: string
}

export interface VMStatus extends ResourceStatus {
  hostname: string
  ip?: string
}

export interface DeploymentSummary {
  total: number
  completed: number
  inProgress: number
  failed: number
  pending: number
}

export interface DeploymentStatusResponse {
  status: string
  elapsedSeconds: number
  startedAt?: string
  summary: DeploymentSummary
  router?: ResourceStatus
  networks: NetworkStatus[]
  vms: VMStatus[]
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

// Linux VM (qemux/qemu) Types
export interface LinuxVersion {
  version: string
  name: string
  size_gb: number
  category: 'desktop' | 'server' | 'security'
  description: string
  download_url: string | null
  download_note?: string
  cached?: boolean
  // Architecture-specific fields
  cached_x86_64?: boolean
  cached_arm64?: boolean
  arm64_available?: boolean
  arm64_url?: string | null
}

export interface LinuxVersionsResponse {
  desktop: LinuxVersion[]
  server: LinuxVersion[]
  security: LinuxVersion[]
  all: LinuxVersion[]
  cache_dir: string
  cached_count: number
  total_count: number
  note: string
  host_arch?: 'x86_64' | 'arm64'
  arm64_supported_distros?: string[]
}

export interface LinuxISODownloadResponse {
  status: 'downloading' | 'no_direct_download'
  version: string
  name: string
  filename?: string
  destination?: string
  source_url?: string
  expected_size_gb?: number
  message: string
  instructions?: string
}

export interface LinuxISODownloadStatus {
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

export interface RecommendedImage {
  name?: string  // Human-readable title
  image?: string
  version?: string
  description: string
  category?: 'desktop' | 'server' | 'services'
  access?: 'web' | 'vnc' | 'rdp'  // Access method for desktop images
  cached?: boolean
}

export interface RecommendedImages {
  desktop: RecommendedImage[]
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
  status: 'downloading' | 'completed' | 'failed' | 'not_found' | 'cancelled'
  filename: string
  name?: string
  path?: string
  size_bytes?: number
  size_gb?: number
  progress_bytes?: number
  progress_gb?: number
  total_bytes?: number
  total_gb?: number
  progress_percent?: number
  error?: string
  message?: string
  downloaded_at?: string
}

// Range Export/Import Types
export interface ExportRequest {
  include_templates: boolean
  include_msel: boolean
  include_artifacts: boolean
  include_snapshots: boolean
  include_docker_images: boolean
  encrypt_passwords: boolean
}

export interface ExportJobStatus {
  job_id: string
  status: 'pending' | 'in_progress' | 'completed' | 'failed'
  progress_percent: number
  current_step: string
  download_url?: string
  error_message?: string
  file_size_bytes?: number
  created_at: string
  completed_at?: string
}

export interface TemplateConflict {
  template_name: string
  existing_template_id: string
  action: 'use_existing' | 'create_new' | 'skip'
}

export interface NetworkConflict {
  network_name: string
  subnet: string
  overlapping_range_name: string
  overlapping_network_name: string
}

export interface ImportConflicts {
  template_conflicts: TemplateConflict[]
  network_conflicts: NetworkConflict[]
  name_conflict: boolean
}

export interface ImportSummary {
  range_name: string
  networks_count: number
  vms_count: number
  templates_to_create: number
  templates_existing: number
  artifacts_count: number
  artifact_placements_count: number
  injects_count: number
  estimated_size_mb?: number
}

export interface ImportValidationResult {
  valid: boolean
  warnings: string[]
  errors: string[]
  conflicts: ImportConflicts
  summary: ImportSummary
}

export interface ImportOptions {
  name_override?: string
  template_conflict_action: 'use_existing' | 'create_new' | 'skip'
  skip_artifacts: boolean
  skip_msel: boolean
  dry_run: boolean
}

export interface ImportResult {
  success: boolean
  range_id?: string
  range_name?: string
  networks_created: number
  vms_created: number
  templates_created: number
  artifacts_imported: number
  errors: string[]
  warnings: string[]
}

export interface LoadImagesResult {
  success: boolean
  images_loaded: string[]
  count: number
}

// Real-time WebSocket Event Types
export interface RealtimeEvent {
  event_type: string
  range_id: string | null
  vm_id: string | null
  message: string
  data: Record<string, unknown> | null
  timestamp: string
}

export interface WebSocketMessage {
  type: 'connected' | 'subscribed' | 'unsubscribed' | 'ping' | 'pong' | 'status_update'
  message?: string
  subscriptions?: string[]
  channel?: string
  range_id?: string
  range_status?: string
  vms?: Record<string, string>
}

export type WebSocketConnectionState = 'connecting' | 'connected' | 'disconnected' | 'error'

export interface VMLogsResponse {
  vm_id: string
  hostname: string
  container_id: string
  tail: number
  lines: string[]
  note: string
}

// Walkthrough Types
export interface WalkthroughStep {
  id: string
  title: string
  content: string
  vm?: string
}

export interface WalkthroughPhase {
  id: string
  name: string
  steps: WalkthroughStep[]
}

export interface Walkthrough {
  title: string
  phases: WalkthroughPhase[]
}

export interface WalkthroughProgress {
  range_id: string
  user_id: string
  completed_steps: string[]
  current_phase: string | null
  current_step: string | null
  updated_at: string
}

// Training Scenarios (filesystem-based)
export interface ScenarioEvent {
  sequence: number
  delay_minutes: number
  title: string
  description?: string
  target_role: string
  actions: Array<{
    type: string
    [key: string]: any
  }>
}

export interface Scenario {
  id: string
  name: string
  description: string
  category: 'red-team' | 'blue-team' | 'insider-threat'
  difficulty: 'beginner' | 'intermediate' | 'advanced'
  duration_minutes: number
  event_count: number
  required_roles: string[]
  modified_at: string
}

export interface ScenarioDetail extends Scenario {
  events: ScenarioEvent[]
}

export interface ScenariosListResponse {
  scenarios: Scenario[]
  scenarios_dir: string
  total: number
}

export interface ScenarioUpload {
  name: string
  description: string
  category: 'red-team' | 'blue-team' | 'insider-threat'
  difficulty: 'beginner' | 'intermediate' | 'advanced'
  duration_minutes: number
  required_roles: string[]
  events: ScenarioEvent[]
}

export interface ApplyScenarioRequest {
  scenario_id: string
  role_mapping: Record<string, string>  // role -> VM ID
}

export interface ApplyScenarioResponse {
  msel_id: string
  inject_count: number
  status: string
}

// ============================================================================
// Image Library Types
// ============================================================================

export type ImageLibraryImageType = 'container' | 'iso'
export type GoldenImageSource = 'snapshot' | 'import'

/**
 * Base Image - Foundation layer of the Image Library.
 * Contains container images (from Docker pulls) and cached ISOs.
 */
export interface BaseImage {
  id: string
  name: string
  description: string | null
  image_type: ImageLibraryImageType
  // Container-specific
  docker_image_id: string | null
  docker_image_tag: string | null
  // ISO-specific
  iso_path: string | null
  iso_source: string | null
  iso_version: string | null
  // Metadata
  os_type: 'windows' | 'linux' | 'network' | 'custom'
  vm_type: 'container' | 'linux_vm' | 'windows_vm'
  native_arch: string
  // Resource defaults
  default_cpu: number
  default_ram_mb: number
  default_disk_gb: number
  // Size and visibility
  size_bytes: number | null
  is_global: boolean
  created_by: string | null
  tags: string[]
  created_at: string
  updated_at: string
}

export interface BaseImageCreate {
  name: string
  description?: string | null
  image_type: ImageLibraryImageType
  docker_image_id?: string | null
  docker_image_tag?: string | null
  iso_path?: string | null
  iso_source?: string | null
  iso_version?: string | null
  os_type: 'windows' | 'linux' | 'network' | 'custom'
  vm_type: 'container' | 'linux_vm' | 'windows_vm'
  native_arch?: string
  default_cpu?: number
  default_ram_mb?: number
  default_disk_gb?: number
  size_bytes?: number | null
  tags?: string[]
}

export interface BaseImageBrief {
  id: string
  name: string
  image_type: ImageLibraryImageType
  os_type: string
}

/**
 * Golden Image - Second tier of the Image Library.
 * Created from first snapshot of a VM OR imported from OVA/QCOW2/VMDK.
 * Tracks lineage back to base image.
 */
export interface GoldenImageLibrary {
  id: string
  name: string
  description: string | null
  // Source tracking (lineage)
  source: GoldenImageSource
  base_image_id: string | null
  base_image: BaseImageBrief | null  // Populated for lineage display
  source_vm_id: string | null
  // Storage
  docker_image_id: string | null
  docker_image_tag: string | null
  disk_image_path: string | null
  import_format: string | null  // ova, qcow2, vmdk
  // Metadata
  os_type: 'windows' | 'linux' | 'network' | 'custom'
  vm_type: 'container' | 'linux_vm' | 'windows_vm'
  native_arch: string
  // Resource defaults
  default_cpu: number
  default_ram_mb: number
  default_disk_gb: number
  // Display/console settings
  display_type: 'desktop' | 'server' | 'headless' | null
  vnc_port: number | null
  // Size and visibility
  size_bytes: number | null
  is_global: boolean
  created_by: string | null
  tags: string[]
  created_at: string
  updated_at: string
}

export interface GoldenImageCreate {
  name: string
  description?: string | null
  source: GoldenImageSource
  base_image_id?: string | null
  os_type: 'windows' | 'linux' | 'network' | 'custom'
  vm_type: 'container' | 'linux_vm' | 'windows_vm'
  native_arch?: string
  default_cpu?: number
  default_ram_mb?: number
  default_disk_gb?: number
  display_type?: 'desktop' | 'server' | 'headless' | null
  vnc_port?: number | null
  tags?: string[]
}

export interface GoldenImageBrief {
  id: string
  name: string
  source: GoldenImageSource
  os_type: string
}

/**
 * Snapshot with lineage - Third tier of the Image Library.
 * Fork snapshots linked to their parent Golden Image.
 */
export interface SnapshotWithLineage extends Snapshot {
  golden_image_id: string | null
  golden_image: GoldenImageBrief | null  // Populated for lineage display
  parent_snapshot_id: string | null
}

/**
 * Unified view of any image in the library.
 */
export interface LibraryImage {
  id: string
  name: string
  category: 'base' | 'golden' | 'snapshot'
  image_type: ImageLibraryImageType | null  // For base images
  source: GoldenImageSource | null  // For golden images
  os_type: string
  vm_type: string
  native_arch: string
  default_cpu: number
  default_ram_mb: number
  default_disk_gb: number
  size_bytes: number | null
  lineage: string | null  // e.g., "From: Ubuntu 22.04" or "Fork of: DC01 Golden"
}

/**
 * Statistics about the Image Library.
 */
export interface LibraryStats {
  base_images_count: number
  golden_images_count: number
  snapshots_count: number
  total_size_bytes: number
}

/**
 * Result of syncing cache to Image Library.
 */
export interface SyncResult {
  docker_images_synced: number
  windows_isos_synced: number
  linux_isos_synced: number
  custom_isos_synced: number
  total_synced: number
}

/**
 * VM Create with Image Library sources.
 * Exactly one source must be provided.
 */
export interface VMCreateWithImageLibrary {
  range_id: string
  network_id: string
  hostname: string
  ip_address: string
  cpu?: number
  ram_mb?: number
  disk_gb?: number
  // Image source - exactly one required
  base_image_id?: string | null
  golden_image_id?: string | null
  snapshot_id?: string | null
  template_id?: string | null  // Deprecated, for backward compat
  // Other VM settings
  display_type?: 'desktop' | 'server' | 'headless' | null
  boot_source?: 'golden_image' | 'fresh_install' | null
  // Target architecture for QEMU VMs
  arch?: 'x86_64' | 'arm64' | null
}
