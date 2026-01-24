// frontend/src/stores/notificationStore.ts
/**
 * Global notification store with localStorage persistence.
 * Manages notification state, unread counts, and filtering.
 */
import { create } from 'zustand'
import { RealtimeEvent } from '../types'

export type NotificationSeverity = 'info' | 'warning' | 'error'
export type NotificationFilter = 'all' | 'info' | 'warning' | 'error'

export interface Notification {
  id: string
  event_type: string
  message: string
  severity: NotificationSeverity
  timestamp: string
  read: boolean
  range_id?: string
  vm_id?: string
  data?: Record<string, unknown>
}

interface NotificationState {
  notifications: Notification[]
  filter: NotificationFilter
  unreadCount: number
}

interface NotificationActions {
  addNotification: (event: RealtimeEvent) => void
  markAsRead: (id: string) => void
  markAllAsRead: () => void
  clearAll: () => void
  setFilter: (filter: NotificationFilter) => void
  loadFromStorage: () => void
}

type NotificationStore = NotificationState & NotificationActions

const STORAGE_KEY = 'cyroid_notifications'
const MAX_NOTIFICATIONS = 50

/**
 * Derive severity from event type string.
 */
export function getSeverity(eventType: string): NotificationSeverity {
  const lower = eventType.toLowerCase()
  if (lower.includes('failed') || lower.includes('error')) return 'error'
  if (lower.includes('step') || lower.includes('stopped') || lower.includes('stopping')) return 'warning'
  return 'info'
}

/**
 * Load notifications from localStorage.
 */
function loadNotifications(): Notification[] {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      const parsed = JSON.parse(stored)
      if (Array.isArray(parsed)) {
        return parsed
      }
    }
  } catch (e) {
    console.error('Failed to load notifications from storage:', e)
  }
  return []
}

/**
 * Save notifications to localStorage.
 */
function saveNotifications(notifications: Notification[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(notifications))
  } catch (e) {
    console.error('Failed to save notifications to storage:', e)
  }
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
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
}

export const useNotificationStore = create<NotificationStore>((set) => ({
  notifications: [],
  filter: 'all',
  unreadCount: 0,

  addNotification: (event: RealtimeEvent) => {
    const notification: Notification = {
      id: generateId(),
      event_type: event.event_type,
      message: event.message,
      severity: getSeverity(event.event_type),
      timestamp: event.timestamp || new Date().toISOString(),
      read: false,
      range_id: event.range_id ?? undefined,
      vm_id: event.vm_id ?? undefined,
      data: event.data ?? undefined,
    }

    set(state => {
      // Add new notification at the beginning
      let updated = [notification, ...state.notifications]

      // Trim to max notifications
      if (updated.length > MAX_NOTIFICATIONS) {
        updated = updated.slice(0, MAX_NOTIFICATIONS)
      }

      saveNotifications(updated)

      return {
        notifications: updated,
        unreadCount: countUnread(updated),
      }
    })
  },

  markAsRead: (id: string) => {
    set(state => {
      const updated = state.notifications.map(n =>
        n.id === id ? { ...n, read: true } : n
      )
      saveNotifications(updated)
      return {
        notifications: updated,
        unreadCount: countUnread(updated),
      }
    })
  },

  markAllAsRead: () => {
    set(state => {
      const updated = state.notifications.map(n => ({ ...n, read: true }))
      saveNotifications(updated)
      return {
        notifications: updated,
        unreadCount: 0,
      }
    })
  },

  clearAll: () => {
    saveNotifications([])
    set({
      notifications: [],
      unreadCount: 0,
    })
  },

  setFilter: (filter: NotificationFilter) => {
    set({ filter })
  },

  loadFromStorage: () => {
    const notifications = loadNotifications()
    set({
      notifications,
      unreadCount: countUnread(notifications),
    })
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
