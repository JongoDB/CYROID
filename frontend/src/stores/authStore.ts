// frontend/src/stores/authStore.ts
import { create } from 'zustand'
import { authApi, User, LoginRequest, RegisterRequest, PasswordChangeRequest } from '../services/api'

interface AuthState {
  user: User | null
  token: string | null
  isLoading: boolean
  error: string | null
  passwordResetRequired: boolean

  // Actions
  login: (data: LoginRequest) => Promise<void>
  register: (data: RegisterRequest) => Promise<void>
  logout: () => void
  checkAuth: () => Promise<void>
  clearError: () => void
  changePassword: (data: PasswordChangeRequest) => Promise<void>
  clearPasswordResetRequired: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: localStorage.getItem('token'),
  isLoading: false,
  error: null,
  passwordResetRequired: false,

  login: async (data: LoginRequest) => {
    set({ isLoading: true, error: null })
    try {
      const response = await authApi.login(data)
      const { access_token, password_reset_required } = response.data
      localStorage.setItem('token', access_token)
      set({ token: access_token, passwordResetRequired: password_reset_required })

      // Fetch user info
      const userResponse = await authApi.me()
      set({ user: userResponse.data, isLoading: false })
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Login failed'
      set({ error: message, isLoading: false })
      throw error
    }
  },

  register: async (data: RegisterRequest) => {
    set({ isLoading: true, error: null })
    try {
      await authApi.register(data)
      set({ isLoading: false })
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Registration failed'
      set({ error: message, isLoading: false })
      throw error
    }
  },

  logout: () => {
    localStorage.removeItem('token')
    set({ user: null, token: null })
  },

  checkAuth: async () => {
    const token = localStorage.getItem('token')
    if (!token) {
      set({ user: null, token: null })
      return
    }

    set({ isLoading: true })
    try {
      const response = await authApi.me()
      set({
        user: response.data,
        token,
        isLoading: false,
        passwordResetRequired: response.data.password_reset_required
      })
    } catch {
      localStorage.removeItem('token')
      set({ user: null, token: null, isLoading: false })
    }
  },

  clearError: () => set({ error: null }),

  changePassword: async (data: PasswordChangeRequest) => {
    set({ isLoading: true, error: null })
    try {
      await authApi.changePassword(data)
      // Clear password reset flag after successful change
      set({ passwordResetRequired: false, isLoading: false })
      // Refresh user data
      const userResponse = await authApi.me()
      set({ user: userResponse.data })
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Password change failed'
      set({ error: message, isLoading: false })
      throw error
    }
  },

  clearPasswordResetRequired: () => set({ passwordResetRequired: false }),
}))
