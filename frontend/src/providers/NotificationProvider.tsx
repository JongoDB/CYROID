// frontend/src/providers/NotificationProvider.tsx
/**
 * Provider component that initializes global notifications.
 * Handles WebSocket connection, server sync, and toast display.
 */
import { useEffect, createContext, useContext, ReactNode } from 'react'
import { useGlobalNotifications, ConnectionState } from '../hooks/useGlobalNotifications'
import { useNotificationStore, getSeverity } from '../stores/notificationStore'
import { ToastContainer, useToasts } from '../components/notifications/ToastContainer'
import { useAuthStore } from '../stores/authStore'
import { RealtimeEvent } from '../types'

interface NotificationContextValue {
  connectionState: ConnectionState
  isConnected: boolean
}

const NotificationContext = createContext<NotificationContextValue>({
  connectionState: 'disconnected',
  isConnected: false,
})

export function useNotificationContext() {
  return useContext(NotificationContext)
}

interface NotificationProviderProps {
  children: ReactNode
}

export function NotificationProvider({ children }: NotificationProviderProps) {
  const isAuthenticated = useAuthStore((s) => !!s.token)
  const loadFromServer = useNotificationStore((s) => s.loadFromServer)
  const clearAll = useNotificationStore((s) => s.clearAll)
  const { toasts, addToast, dismissToast, clearAllToasts } = useToasts()

  // Load notifications from server on mount when authenticated
  // Clear notifications when logged out
  useEffect(() => {
    if (isAuthenticated) {
      loadFromServer()
    } else {
      // Clear all toasts and notifications when logged out
      clearAllToasts()
      clearAll()
    }
  }, [isAuthenticated, loadFromServer, clearAllToasts, clearAll])

  // Handle new notifications - show toast (only when authenticated)
  const handleNotification = (event: RealtimeEvent) => {
    if (!isAuthenticated) return
    const severity = getSeverity(event.event_type)
    addToast(event.message, severity)
  }

  // Connect to global notifications WebSocket
  const { connectionState, isConnected } = useGlobalNotifications({
    enabled: isAuthenticated,
    onNotification: handleNotification,
  })

  return (
    <NotificationContext.Provider value={{ connectionState, isConnected }}>
      {children}
      {/* Only show toasts when authenticated */}
      {isAuthenticated && <ToastContainer toasts={toasts} onDismiss={dismissToast} />}
    </NotificationContext.Provider>
  )
}
