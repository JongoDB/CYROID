// frontend/src/components/notifications/NotificationBell.tsx
/**
 * Notification bell icon with unread badge and dropdown.
 * Shows notification history with filtering by severity.
 */
import { useState, useRef, useEffect } from 'react'
import { Bell, Check, Trash2 } from 'lucide-react'
import {
  useNotificationStore,
  getFilteredNotifications,
  NotificationFilter,
} from '../../stores/notificationStore'
import { NotificationItem } from './NotificationItem'

const filterTabs: { label: string; value: NotificationFilter }[] = [
  { label: 'All', value: 'all' },
  { label: 'Info', value: 'info' },
  { label: 'Warn', value: 'warning' },
  { label: 'Err', value: 'error' },
]

export function NotificationBell() {
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const notifications = useNotificationStore((s) => s.notifications)
  const unreadCount = useNotificationStore((s) => s.unreadCount)
  const filter = useNotificationStore((s) => s.filter)
  const setFilter = useNotificationStore((s) => s.setFilter)
  const markAsRead = useNotificationStore((s) => s.markAsRead)
  const markAllAsRead = useNotificationStore((s) => s.markAllAsRead)
  const clearAll = useNotificationStore((s) => s.clearAll)

  const filteredNotifications = getFilteredNotifications(notifications, filter)

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])

  // Close on escape key
  useEffect(() => {
    function handleEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setIsOpen(false)
      }
    }

    if (isOpen) {
      document.addEventListener('keydown', handleEscape)
      return () => document.removeEventListener('keydown', handleEscape)
    }
  }, [isOpen])

  const handleNotificationClick = (notification: { id: string }) => {
    markAsRead(notification.id)
  }

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Bell button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 text-gray-400 hover:text-gray-200 transition-colors"
        aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ''}`}
        aria-expanded={isOpen}
        aria-haspopup="true"
      >
        <Bell className="w-5 h-5" />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 flex items-center justify-center min-w-[18px] h-[18px] px-1 text-xs font-medium text-white bg-red-500 rounded-full">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown - position right on mobile (top bar), left on desktop (sidebar extends into content) */}
      {isOpen && (
        <div className="absolute right-0 lg:left-0 lg:right-auto mt-2 w-80 max-w-[calc(100vw-2rem)] bg-gray-800 border border-gray-700 rounded-lg shadow-xl z-[9999] overflow-hidden">
          {/* Header */}
          <div className="px-4 py-3 border-b border-gray-700">
            <h3 className="text-sm font-medium text-gray-200">Notifications</h3>
          </div>

          {/* Filter tabs */}
          <div className="flex border-b border-gray-700">
            {filterTabs.map((tab) => (
              <button
                key={tab.value}
                onClick={() => setFilter(tab.value)}
                className={`
                  flex-1 px-3 py-2 text-xs font-medium transition-colors
                  ${filter === tab.value
                    ? 'text-blue-400 border-b-2 border-blue-400 bg-gray-700/50'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-gray-700/30'
                  }
                `}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Notification list */}
          <div className="max-h-80 overflow-y-auto">
            {filteredNotifications.length === 0 ? (
              <div className="px-4 py-8 text-center text-gray-500 text-sm">
                No notifications
              </div>
            ) : (
              <div className="divide-y divide-gray-700/50">
                {filteredNotifications.map((notification) => (
                  <NotificationItem
                    key={notification.id}
                    notification={notification}
                    onClick={handleNotificationClick}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Footer actions */}
          {notifications.length > 0 && (
            <div className="flex border-t border-gray-700">
              <button
                onClick={markAllAsRead}
                className="flex-1 flex items-center justify-center gap-2 px-3 py-2 text-xs text-gray-400 hover:text-gray-200 hover:bg-gray-700/50 transition-colors"
              >
                <Check className="w-3 h-3" />
                Mark all read
              </button>
              <div className="w-px bg-gray-700" />
              <button
                onClick={clearAll}
                className="flex-1 flex items-center justify-center gap-2 px-3 py-2 text-xs text-gray-400 hover:text-red-400 hover:bg-gray-700/50 transition-colors"
              >
                <Trash2 className="w-3 h-3" />
                Clear all
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
