// frontend/src/stores/authStore.ts
import { create } from 'zustand'
import { authApi, User, LoginRequest, RegisterRequest, PasswordChangeRequest } from '../services/api'
import { getHighestRole, UserRole } from '../utils/roleUtils'

interface AuthState {
  user: User | null
  token: string | null
  isLoading: boolean
  error: string | null
  passwordResetRequired: boolean
  activeRole: string | null  // Current perspective role (persisted to localStorage)

  // Actions
  login: (data: LoginRequest) => Promise<void>
  register: (data: RegisterRequest) => Promise<void>
  logout: () => void
  checkAuth: () => Promise<void>
  clearError: () => void
  changePassword: (data: PasswordChangeRequest) => Promise<void>
  clearPasswordResetRequired: () => void
  setActiveRole: (role: string) => void
  getEffectiveRole: () => UserRole | null
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  token: localStorage.getItem('token'),
  isLoading: false,
  error: null,
  passwordResetRequired: false,
  activeRole: localStorage.getItem('activeRole'),

  login: async (data: LoginRequest) => {
    set({ isLoading: true, error: null })
    try {
      const response = await authApi.login(data)
      const { access_token, password_reset_required } = response.data
      localStorage.setItem('token', access_token)
      set({ token: access_token, passwordResetRequired: password_reset_required })

      // Fetch user info
      const userResponse = await authApi.me()
      const user = userResponse.data
      set({ user, isLoading: false })

      // Initialize activeRole if not set or if stored role is not in user's roles
      const storedRole = localStorage.getItem('activeRole')
      if (!storedRole || !user.roles?.includes(storedRole)) {
        const highestRole = getHighestRole(user.roles || [])
        if (highestRole) {
          localStorage.setItem('activeRole', highestRole)
          set({ activeRole: highestRole })
        }
      }
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
    localStorage.removeItem('activeRole')
    set({ user: null, token: null, activeRole: null })
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
      const user = response.data

      // Initialize activeRole if not set or invalid
      const storedRole = localStorage.getItem('activeRole')
      let activeRole = storedRole
      if (!storedRole || !user.roles?.includes(storedRole)) {
        activeRole = getHighestRole(user.roles || [])
        if (activeRole) {
          localStorage.setItem('activeRole', activeRole)
        }
      }

      set({
        user,
        token,
        isLoading: false,
        passwordResetRequired: user.password_reset_required,
        activeRole,
      })
    } catch {
      localStorage.removeItem('token')
      localStorage.removeItem('activeRole')
      set({ user: null, token: null, isLoading: false, activeRole: null })
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

  setActiveRole: (role: string) => {
    localStorage.setItem('activeRole', role)
    set({ activeRole: role })
  },

  getEffectiveRole: (): UserRole | null => {
    const state = get()
    // If activeRole is set and user has that role, use it
    if (state.activeRole && state.user?.roles?.includes(state.activeRole)) {
      return state.activeRole as UserRole
    }
    // Otherwise return highest role from user's roles
    return getHighestRole(state.user?.roles || [])
  },
}))
