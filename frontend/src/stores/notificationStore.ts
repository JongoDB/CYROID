// frontend/src/stores/notificationStore.ts
/**
 * Global notification store with server sync.
 * Manages notification state, unread counts, and filtering.
 * Syncs with backend API for persistent notifications.
 */
import { create } from 'zustand'
import { notificationsApi, UserNotification, NotificationSeverity as ApiSeverity } from '../services/api'
import { RealtimeEvent } from '../types'

export type NotificationSeverity = 'info' | 'warning' | 'error' | 'success'
export type NotificationFilter = 'all' | 'info' | 'warning' | 'error' | 'success'

export interface Notification {
  id: string
  event_type: string
  title: string
  message: string
  severity: NotificationSeverity
  timestamp: string
  read: boolean
  range_id?: string
  vm_id?: string
  resource_type?: string
  resource_id?: string
  data?: Record<string, unknown>
  // Server notification fields
  isServerNotification?: boolean
}

interface NotificationState {
  notifications: Notification[]
  filter: NotificationFilter
  unreadCount: number
  isLoading: boolean
  lastFetchTime: number | null
}

interface NotificationActions {
  addNotification: (event: RealtimeEvent) => void
  addServerNotification: (notification: UserNotification) => void
  markAsRead: (id: string) => void
  markAllAsRead: () => void
  clearAll: () => void
  setFilter: (filter: NotificationFilter) => void
  loadFromServer: () => Promise<void>
  syncWithServer: () => Promise<void>
}

type NotificationStore = NotificationState & NotificationActions

const MAX_NOTIFICATIONS = 100

/**
 * Derive severity from event type string.
 */
export function getSeverity(eventType: string): NotificationSeverity {
  const lower = eventType.toLowerCase()
  if (lower.includes('failed') || lower.includes('error')) return 'error'
  if (lower.includes('step') || lower.includes('stopped') || lower.includes('stopping')) return 'warning'
  if (lower.includes('success') || lower.includes('completed') || lower.includes('deployed')) return 'success'
  return 'info'
}

/**
 * Map API severity to local severity.
 */
function mapApiSeverity(severity: ApiSeverity): NotificationSeverity {
  return severity as NotificationSeverity
}

/**
 * Calculate unread count from notifications.
 */
function countUnread(notifications: Notification[]): number {
  return notifications.filter(n => !n.read).length
}

/**
 * Generate unique ID for notification.
 */
function generateId(): string {
  return `local-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
}

/**
 * Convert server notification to local format.
 */
function serverToLocal(n: UserNotification): Notification {
  return {
    id: n.id,
    event_type: n.notification_type,
    title: n.title,
    message: n.message,
    severity: mapApiSeverity(n.severity),
    timestamp: n.created_at,
    read: !!n.read_at,
    resource_type: n.resource_type,
    resource_id: n.resource_id,
    isServerNotification: true,
  }
}

export const useNotificationStore = create<NotificationStore>((set, get) => ({
  notifications: [],
  filter: 'all',
  unreadCount: 0,
  isLoading: false,
  lastFetchTime: null,

  addNotification: (event: RealtimeEvent) => {
    // Handle WebSocket "notification" events specially
    if (event.event_type === 'notification' && event.data) {
      const data = event.data as Record<string, unknown>
      const notification: Notification = {
        id: (data.notification_id as string) || generateId(),
        event_type: (data.notification_type as string) || 'info',
        title: (data.title as string) || 'Notification',
        message: event.message || (data.message as string) || '',
        severity: mapApiSeverity((data.severity as ApiSeverity) || 'info'),
        timestamp: event.timestamp || new Date().toISOString(),
        read: false,
        resource_type: data.resource_type as string | undefined,
        resource_id: data.resource_id as string | undefined,
        isServerNotification: true,
      }

      set(state => {
        // Avoid duplicates
        if (state.notifications.some(n => n.id === notification.id)) {
          return state
        }

        let updated = [notification, ...state.notifications]
        if (updated.length > MAX_NOTIFICATIONS) {
          updated = updated.slice(0, MAX_NOTIFICATIONS)
        }

        return {
          notifications: updated,
          unreadCount: countUnread(updated),
        }
      })
      return
    }

    // Handle regular WebSocket events (legacy compatibility)
    const notification: Notification = {
      id: generateId(),
      event_type: event.event_type,
      title: event.event_type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
      message: event.message,
      severity: getSeverity(event.event_type),
      timestamp: event.timestamp || new Date().toISOString(),
      read: false,
      range_id: event.range_id ?? undefined,
      vm_id: event.vm_id ?? undefined,
      data: event.data ?? undefined,
    }

    set(state => {
      let updated = [notification, ...state.notifications]
      if (updated.length > MAX_NOTIFICATIONS) {
        updated = updated.slice(0, MAX_NOTIFICATIONS)
      }

      return {
        notifications: updated,
        unreadCount: countUnread(updated),
      }
    })
  },

  addServerNotification: (notification: UserNotification) => {
    const local = serverToLocal(notification)

    set(state => {
      // Avoid duplicates
      if (state.notifications.some(n => n.id === local.id)) {
        return state
      }

      let updated = [local, ...state.notifications]
      if (updated.length > MAX_NOTIFICATIONS) {
        updated = updated.slice(0, MAX_NOTIFICATIONS)
      }

      return {
        notifications: updated,
        unreadCount: countUnread(updated),
      }
    })
  },

  markAsRead: async (id: string) => {
    const notification = get().notifications.find(n => n.id === id)

    // Optimistically update UI
    set(state => {
      const updated = state.notifications.map(n =>
        n.id === id ? { ...n, read: true } : n
      )
      return {
        notifications: updated,
        unreadCount: countUnread(updated),
      }
    })

    // If it's a server notification, sync with backend
    if (notification?.isServerNotification) {
      try {
        await notificationsApi.markAsRead([id])
      } catch (e) {
        console.error('Failed to sync notification read status:', e)
      }
    }
  },

  markAllAsRead: async () => {
    const serverNotificationIds = get().notifications
      .filter(n => n.isServerNotification && !n.read)
      .map(n => n.id)

    // Optimistically update UI
    set(state => {
      const updated = state.notifications.map(n => ({ ...n, read: true }))
      return {
        notifications: updated,
        unreadCount: 0,
      }
    })

    // Sync with backend if there are server notifications
    if (serverNotificationIds.length > 0) {
      try {
        await notificationsApi.markAllAsRead()
      } catch (e) {
        console.error('Failed to sync mark all as read:', e)
      }
    }
  },

  clearAll: () => {
    set({
      notifications: [],
      unreadCount: 0,
    })
  },

  setFilter: (filter: NotificationFilter) => {
    set({ filter })
  },

  loadFromServer: async () => {
    set({ isLoading: true })
    try {
      const response = await notificationsApi.list({ limit: 50 })
      const serverNotifications = response.data.notifications.map(serverToLocal)

      set(state => {
        // Merge server notifications with any local ones
        const localNotifications = state.notifications.filter(n => !n.isServerNotification)
        const merged = [...serverNotifications, ...localNotifications]
          .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
          .slice(0, MAX_NOTIFICATIONS)

        return {
          notifications: merged,
          unreadCount: response.data.unread_count + localNotifications.filter(n => !n.read).length,
          isLoading: false,
          lastFetchTime: Date.now(),
        }
      })
    } catch (e) {
      console.error('Failed to load notifications from server:', e)
      set({ isLoading: false })
    }
  },

  syncWithServer: async () => {
    const state = get()
    // Only sync if we haven't fetched recently (within last 30 seconds)
    if (state.lastFetchTime && Date.now() - state.lastFetchTime < 30000) {
      return
    }
    await get().loadFromServer()
  },
}))

/**
 * Get filtered notifications based on current filter.
 */
export function getFilteredNotifications(
  notifications: Notification[],
  filter: NotificationFilter
): Notification[] {
  if (filter === 'all') return notifications
  return notifications.filter(n => n.severity === filter)
}
