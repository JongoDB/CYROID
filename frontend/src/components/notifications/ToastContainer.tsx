// frontend/src/components/notifications/ToastContainer.tsx
/**
 * Container for toast notifications.
 * Positioned fixed in the bottom-right corner.
 * Manages toast queue and limits visible toasts.
 */
import { useState, useCallback } from 'react'
import { Toast } from './Toast'
import { NotificationSeverity } from '../../stores/notificationStore'

export interface ToastData {
  id: string
  message: string
  severity: NotificationSeverity
}

interface ToastContainerProps {
  toasts: ToastData[]
  onDismiss: (id: string) => void
  maxVisible?: number
}

export function ToastContainer({ toasts, onDismiss, maxVisible = 3 }: ToastContainerProps) {
  // Only show the most recent N toasts
  const visibleToasts = toasts.slice(0, maxVisible)

  return (
    <div
      className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-80 max-w-[calc(100vw-2rem)]"
      aria-live="polite"
      aria-label="Notifications"
    >
      {visibleToasts.map((toast) => (
        <Toast
          key={toast.id}
          id={toast.id}
          message={toast.message}
          severity={toast.severity}
          onDismiss={onDismiss}
        />
      ))}
    </div>
  )
}

/**
 * Hook for managing toast state.
 * Returns toast list and functions to add/dismiss toasts.
 */
export function useToasts() {
  const [toasts, setToasts] = useState<ToastData[]>([])

  const addToast = useCallback((message: string, severity: NotificationSeverity) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
    setToasts((prev) => [...prev, { id, message, severity }])
    return id
  }, [])

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const clearAllToasts = useCallback(() => {
    setToasts([])
  }, [])

  return {
    toasts,
    addToast,
    dismissToast,
    clearAllToasts,
  }
}
