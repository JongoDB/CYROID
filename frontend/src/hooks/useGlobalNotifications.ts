// frontend/src/hooks/useGlobalNotifications.ts
/**
 * Hook for subscribing to global system notifications via WebSocket.
 * Connects without a range_id to receive all system events.
 */
import { useEffect, useRef, useState, useCallback } from 'react'
import { useAuthStore } from '../stores/authStore'
import { useNotificationStore } from '../stores/notificationStore'
import { RealtimeEvent } from '../types'

const WS_BASE_URL = (import.meta as unknown as { env: Record<string, string> }).env?.VITE_WS_URL || `ws://${window.location.host}`
const MAX_RECONNECT_ATTEMPTS = 10
const INITIAL_RECONNECT_DELAY = 1000

export type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'error'

interface UseGlobalNotificationsOptions {
  enabled?: boolean
  onNotification?: (event: RealtimeEvent) => void
}

interface UseGlobalNotificationsReturn {
  connectionState: ConnectionState
  isConnected: boolean
}

export function useGlobalNotifications(
  options: UseGlobalNotificationsOptions = {}
): UseGlobalNotificationsReturn {
  const { enabled = true, onNotification } = options

  const token = useAuthStore((state) => state.token)
  const addNotification = useNotificationStore((state) => state.addNotification)

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectAttemptsRef = useRef(0)

  const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected')

  // Callback ref to avoid reconnection on callback changes
  const onNotificationRef = useRef(onNotification)
  useEffect(() => {
    onNotificationRef.current = onNotification
  }, [onNotification])

  const connect = useCallback(() => {
    if (!token || !enabled) return

    // Close existing connection
    if (wsRef.current) {
      wsRef.current.close()
    }

    setConnectionState('connecting')

    // Connect without range_id to get all global events
    const wsUrl = `${WS_BASE_URL}/api/v1/ws/events?token=${encodeURIComponent(token)}`

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      console.log('[GlobalNotifications] Connected')
      setConnectionState('connected')
      reconnectAttemptsRef.current = 0
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)

        // Handle keepalive ping
        if (data.type === 'ping') {
          ws.send(JSON.stringify({ action: 'ping' }))
          return
        }

        // Handle connection confirmation
        if (data.type === 'connected') {
          console.log('[GlobalNotifications] Subscription confirmed')
          return
        }

        // Handle real-time event
        if (data.event_type) {
          const realtimeEvent: RealtimeEvent = {
            event_type: data.event_type,
            range_id: data.range_id,
            vm_id: data.vm_id,
            message: data.message,
            data: data.data,
            timestamp: data.timestamp,
          }

          // Add to notification store
          addNotification(realtimeEvent)

          // Call optional callback (for toast triggering)
          onNotificationRef.current?.(realtimeEvent)
        }
      } catch (err) {
        console.error('[GlobalNotifications] Failed to parse message:', err)
      }
    }

    ws.onerror = (error) => {
      console.error('[GlobalNotifications] Error:', error)
      setConnectionState('error')
    }

    ws.onclose = (event) => {
      console.log('[GlobalNotifications] Disconnected:', event.code, event.reason)
      setConnectionState('disconnected')
      wsRef.current = null

      // Attempt reconnection if not a clean close
      if (event.code !== 1000 && reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS && enabled) {
        const delay = Math.min(
          INITIAL_RECONNECT_DELAY * Math.pow(2, reconnectAttemptsRef.current),
          30000 // Max 30 seconds
        )
        console.log(`[GlobalNotifications] Reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current + 1})`)

        reconnectTimeoutRef.current = setTimeout(() => {
          reconnectAttemptsRef.current++
          connect()
        }, delay)
      }
    }
  }, [token, enabled, addNotification])

  // Connect on mount and when dependencies change
  useEffect(() => {
    if (enabled && token) {
      connect()
    }

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close(1000, 'Hook cleanup')
      }
    }
  }, [connect, enabled, token])

  return {
    connectionState,
    isConnected: connectionState === 'connected',
  }
}
