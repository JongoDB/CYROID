// frontend/src/types/index.ts

export interface User {
  id: string
  username: string
  email: string
  role: string
  is_active: boolean
  created_at: string
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
