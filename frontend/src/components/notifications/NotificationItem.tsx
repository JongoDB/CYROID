// frontend/src/components/notifications/NotificationItem.tsx
/**
 * Single notification item in the dropdown list.
 * Shows title, message, timestamp, severity indicator, and read state.
 */
import { CheckCircle, AlertTriangle, XCircle, Info } from 'lucide-react'
import { Notification } from '../../stores/notificationStore'

interface NotificationItemProps {
  notification: Notification
  onClick?: (notification: Notification) => void
}

const severityConfig = {
  info: {
    icon: Info,
    iconColor: 'text-blue-500',
    dotColor: 'bg-blue-500',
  },
  success: {
    icon: CheckCircle,
    iconColor: 'text-green-500',
    dotColor: 'bg-green-500',
  },
  warning: {
    icon: AlertTriangle,
    iconColor: 'text-yellow-500',
    dotColor: 'bg-yellow-500',
  },
  error: {
    icon: XCircle,
    iconColor: 'text-red-500',
    dotColor: 'bg-red-500',
  },
}

/**
 * Format timestamp to relative time (e.g., "2 minutes ago")
 */
function formatRelativeTime(timestamp: string): string {
  const now = new Date()
  const time = new Date(timestamp)
  const diffMs = now.getTime() - time.getTime()
  const diffSec = Math.floor(diffMs / 1000)
  const diffMin = Math.floor(diffSec / 60)
  const diffHour = Math.floor(diffMin / 60)
  const diffDay = Math.floor(diffHour / 24)

  if (diffSec < 60) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  if (diffHour < 24) return `${diffHour}h ago`
  if (diffDay < 7) return `${diffDay}d ago`
  return time.toLocaleDateString()
}

export function NotificationItem({ notification, onClick }: NotificationItemProps) {
  const config = severityConfig[notification.severity] || severityConfig.info
  const Icon = config.icon

  return (
    <button
      onClick={() => onClick?.(notification)}
      className={`
        w-full flex items-start gap-3 p-3 text-left
        hover:bg-gray-700/50 transition-colors
        ${notification.read ? 'opacity-60' : ''}
      `}
    >
      {/* Severity icon */}
      <div className={`flex-shrink-0 mt-0.5 ${config.iconColor}`}>
        <Icon className="w-4 h-4" />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        {notification.title && (
          <p className="text-sm font-medium text-gray-100 break-words">
            {notification.title}
          </p>
        )}
        <p className={`text-sm text-gray-300 break-words ${notification.title ? 'mt-0.5' : ''}`}>
          {notification.message}
        </p>
        <p className="text-xs text-gray-500 mt-1">
          {formatRelativeTime(notification.timestamp)}
        </p>
      </div>

      {/* Unread indicator */}
      {!notification.read && (
        <div className={`flex-shrink-0 w-2 h-2 rounded-full mt-2 ${config.dotColor}`} />
      )}
    </button>
  )
}
