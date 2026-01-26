// frontend/src/components/notifications/Toast.tsx
/**
 * Individual toast notification component.
 * Auto-dismisses after a timeout, can be manually dismissed.
 */
import { useEffect, useState } from 'react'
import { X, CheckCircle, AlertTriangle, XCircle, Info } from 'lucide-react'
import { NotificationSeverity } from '../../stores/notificationStore'

interface ToastProps {
  id: string
  message: string
  severity: NotificationSeverity
  onDismiss: (id: string) => void
  duration?: number
}

const severityConfig = {
  info: {
    icon: Info,
    borderColor: 'border-l-blue-500',
    iconColor: 'text-blue-500',
    bgColor: 'bg-blue-500/10',
  },
  success: {
    icon: CheckCircle,
    borderColor: 'border-l-green-500',
    iconColor: 'text-green-500',
    bgColor: 'bg-green-500/10',
  },
  warning: {
    icon: AlertTriangle,
    borderColor: 'border-l-yellow-500',
    iconColor: 'text-yellow-500',
    bgColor: 'bg-yellow-500/10',
  },
  error: {
    icon: XCircle,
    borderColor: 'border-l-red-500',
    iconColor: 'text-red-500',
    bgColor: 'bg-red-500/10',
  },
}

export function Toast({ id, message, severity, onDismiss, duration = 5000 }: ToastProps) {
  const [isExiting, setIsExiting] = useState(false)
  const config = severityConfig[severity]
  const Icon = config.icon

  useEffect(() => {
    const timer = setTimeout(() => {
      setIsExiting(true)
      setTimeout(() => onDismiss(id), 300) // Wait for exit animation
    }, duration)

    return () => clearTimeout(timer)
  }, [id, duration, onDismiss])

  const handleDismiss = () => {
    setIsExiting(true)
    setTimeout(() => onDismiss(id), 300)
  }

  return (
    <div
      className={`
        flex items-start gap-3 p-4 rounded-lg shadow-lg border-l-4
        bg-gray-800 ${config.borderColor}
        transform transition-all duration-300 ease-in-out
        ${isExiting ? 'opacity-0 translate-x-full' : 'opacity-100 translate-x-0'}
      `}
      role="alert"
    >
      <div className={`flex-shrink-0 ${config.iconColor}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-gray-200 break-words">{message}</p>
      </div>
      <button
        onClick={handleDismiss}
        className="flex-shrink-0 text-gray-400 hover:text-gray-200 transition-colors"
        aria-label="Dismiss notification"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  )
}
