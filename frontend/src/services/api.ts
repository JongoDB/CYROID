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
}

export interface User {
  id: string
  username: string
  email: string
  role: string
  is_active: boolean
  created_at: string
}

export const authApi = {
  login: (data: LoginRequest) =>
    api.post<TokenResponse>('/auth/login', data),

  register: (data: RegisterRequest) =>
    api.post<User>('/auth/register', data),

  me: () =>
    api.get<User>('/auth/me'),
}

// Templates API
import type { VMTemplate, Range, Network, VM } from '../types'

export interface VMTemplateCreate {
  name: string
  description?: string
  os_type: 'windows' | 'linux'
  os_variant: string
  base_image: string
  default_cpu?: number
  default_ram_mb?: number
  default_disk_gb?: number
  config_script?: string
  tags?: string[]
}

export const templatesApi = {
  list: () => api.get<VMTemplate[]>('/templates'),
  get: (id: string) => api.get<VMTemplate>(`/templates/${id}`),
  create: (data: VMTemplateCreate) => api.post<VMTemplate>('/templates', data),
  update: (id: string, data: Partial<VMTemplateCreate>) => api.put<VMTemplate>(`/templates/${id}`, data),
  delete: (id: string) => api.delete(`/templates/${id}`),
  clone: (id: string) => api.post<VMTemplate>(`/templates/${id}/clone`),
}

// Ranges API
export interface RangeCreate {
  name: string
  description?: string
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
}

// Networks API
export interface NetworkCreate {
  range_id: string
  name: string
  subnet: string
  gateway: string
  dns_servers?: string
  isolation_level?: 'complete' | 'controlled' | 'open'
}

export const networksApi = {
  list: (rangeId: string) => api.get<Network[]>(`/networks?range_id=${rangeId}`),
  get: (id: string) => api.get<Network>(`/networks/${id}`),
  create: (data: NetworkCreate) => api.post<Network>('/networks', data),
  update: (id: string, data: Partial<NetworkCreate>) => api.put<Network>(`/networks/${id}`, data),
  delete: (id: string) => api.delete(`/networks/${id}`),
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
}

export default api
