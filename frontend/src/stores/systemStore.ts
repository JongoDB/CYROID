// frontend/src/stores/systemStore.ts
import { create } from 'zustand'
import { api } from '../services/api'

interface SystemInfo {
  host_arch: 'x86_64' | 'arm64'
  is_arm: boolean
  is_x86: boolean
  emulation_available: boolean
  platform: string
  machine: string
}

interface SystemState {
  info: SystemInfo | null
  isLoading: boolean
  error: string | null

  // Actions
  fetchSystemInfo: () => Promise<void>
}

export const useSystemStore = create<SystemState>((set) => ({
  info: null,
  isLoading: false,
  error: null,

  fetchSystemInfo: async () => {
    set({ isLoading: true, error: null })
    try {
      const response = await api.get<SystemInfo>('/system/info')
      set({ info: response.data, isLoading: false })
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to fetch system info'
      set({ error: message, isLoading: false })
      // Don't throw - system info is not critical for app function
      console.warn('System info fetch failed:', message)
    }
  },
}))

// Convenience hooks
export const useIsArmHost = () => useSystemStore((state) => state.info?.is_arm ?? false)
export const useHostArch = () => useSystemStore((state) => state.info?.host_arch ?? 'x86_64')
