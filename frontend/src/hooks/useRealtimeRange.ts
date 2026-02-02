// frontend/src/hooks/useRealtimeRange.ts
/**
 * React hook for real-time range updates via WebSocket.
 *
 * Provides:
 * - Automatic WebSocket connection management
 * - Subscription to range-specific events
 * - Automatic reconnection with exponential backoff
 * - Event callbacks for UI updates
 */
import { useEffect, useRef, useState, useCallback } from 'react'
import { useAuthStore } from '../stores/authStore'
import { RealtimeEvent, WebSocketConnectionState } from '../types'

const WS_BASE_URL = (import.meta as unknown as { env: Record<string, string> }).env?.VITE_WS_URL || `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`
const MAX_RECONNECT_ATTEMPTS = 5
const INITIAL_RECONNECT_DELAY = 1000

interface UseRealtimeRangeOptions {
  onEvent?: (event: RealtimeEvent) => void
  onStatusChange?: (rangeStatus: string, vmStatuses: Record<string, string>) => void
  onVmStatusChange?: (vmId: string, status: string) => void
  onDeploymentProgress?: (step: string, message: string) => void
  onError?: (error: string) => void
  enabled?: boolean
}

interface UseRealtimeRangeReturn {
  connectionState: WebSocketConnectionState
  lastEvent: RealtimeEvent | null
  subscribe: (rangeId: string) => void
  unsubscribe: (rangeId: string) => void
  subscribeToVm: (vmId: string) => void
}

export function useRealtimeRange(
  rangeId: string | null,
  options: UseRealtimeRangeOptions = {}
): UseRealtimeRangeReturn {
  const {
    onEvent,
    onStatusChange,
    onVmStatusChange,
    onDeploymentProgress,
    onError,
    enabled = true,
  } = options

  const token = useAuthStore((state) => state.token)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectAttemptsRef = useRef(0)
  const mountedRef = useRef(true)

  const [connectionState, setConnectionState] = useState<WebSocketConnectionState>('disconnected')
  const [lastEvent, setLastEvent] = useState<RealtimeEvent | null>(null)

  // Callback refs to avoid reconnection on callback changes
  const callbacksRef = useRef({ onEvent, onStatusChange, onVmStatusChange, onDeploymentProgress, onError })
  useEffect(() => {
    callbacksRef.current = { onEvent, onStatusChange, onVmStatusChange, onDeploymentProgress, onError }
  }, [onEvent, onStatusChange, onVmStatusChange, onDeploymentProgress, onError])

  const connect = useCallback(() => {
    if (!token || !rangeId || !enabled) return

    // Prevent rapid reconnection - wait for previous close to complete
    if (wsRef.current && wsRef.current.readyState === WebSocket.CONNECTING) {
      console.log('[WebSocket] Connection already in progress, skipping')
      return
    }

    // Close existing connection cleanly
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.close(1000, 'Reconnecting')
      wsRef.current = null
    }

    setConnectionState('connecting')

    // Build WebSocket URL with token and optional range_id
    const wsUrl = `${WS_BASE_URL}/api/v1/ws/events?token=${encodeURIComponent(token)}&range_id=${encodeURIComponent(rangeId)}`

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      console.log('[WebSocket] Connected to real-time events')
      setConnectionState('connected')
      reconnectAttemptsRef.current = 0
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)

        // Handle different message types
        if (data.type === 'ping') {
          // Respond to keepalive ping
          ws.send(JSON.stringify({ action: 'ping' }))
          return
        }

        if (data.type === 'connected') {
          console.log('[WebSocket] Subscription confirmed:', data.subscriptions)
          return
        }

        if (data.type === 'status_update') {
          // Handle status update from /ws/status endpoint format
          callbacksRef.current.onStatusChange?.(data.range_status, data.vms || {})
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

          setLastEvent(realtimeEvent)
          callbacksRef.current.onEvent?.(realtimeEvent)

          // Route to specific handlers based on event type
          if (data.event_type.startsWith('vm_') || data.event_type === 'vm.status_changed') {
            const vmStatus = data.data?.status as string
            if (data.vm_id && vmStatus) {
              callbacksRef.current.onVmStatusChange?.(data.vm_id, vmStatus)
            }
          }

          if (data.event_type.startsWith('deployment_') || data.event_type === 'deployment_step') {
            callbacksRef.current.onDeploymentProgress?.(
              data.data?.step as string || data.event_type,
              data.message
            )
          }
        }
      } catch (err) {
        console.error('[WebSocket] Failed to parse message:', err)
      }
    }

    ws.onerror = (error) => {
      console.error('[WebSocket] Error:', error)
      setConnectionState('error')
      callbacksRef.current.onError?.('WebSocket connection error')
    }

    ws.onclose = (event) => {
      console.log('[WebSocket] Disconnected:', event.code, event.reason)
      setConnectionState('disconnected')
      wsRef.current = null

      // Don't reconnect if unmounted or clean close
      if (!mountedRef.current) return

      // Attempt reconnection if not a clean close and we haven't exceeded attempts
      if (event.code !== 1000 && reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS && enabled) {
        const delay = INITIAL_RECONNECT_DELAY * Math.pow(2, reconnectAttemptsRef.current)
        console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current + 1})`)

        reconnectTimeoutRef.current = setTimeout(() => {
          if (mountedRef.current) {
            reconnectAttemptsRef.current++
            connect()
          }
        }, delay)
      }
    }
  }, [token, rangeId, enabled])

  // Subscribe to additional range
  const subscribe = useCallback((targetRangeId: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        action: 'subscribe',
        range_id: targetRangeId,
      }))
    }
  }, [])

  // Unsubscribe from range
  const unsubscribe = useCallback((targetRangeId: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        action: 'unsubscribe',
        range_id: targetRangeId,
      }))
    }
  }, [])

  // Subscribe to VM events
  const subscribeToVm = useCallback((vmId: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        action: 'subscribe_vm',
        vm_id: vmId,
      }))
    }
  }, [])

  // Connect on mount and when dependencies change
  useEffect(() => {
    mountedRef.current = true
    let connectTimeout: ReturnType<typeof setTimeout> | null = null

    if (enabled && rangeId && token) {
      // Small delay to avoid React 18 Strict Mode double-render race condition
      connectTimeout = setTimeout(() => {
        if (mountedRef.current) {
          connect()
        }
      }, 100)
    }

    return () => {
      // Cleanup on unmount
      mountedRef.current = false
      if (connectTimeout) {
        clearTimeout(connectTimeout)
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close(1000, 'Component unmounted')
        wsRef.current = null
      }
    }
  }, [connect, enabled, rangeId, token])

  return {
    connectionState,
    lastEvent,
    subscribe,
    unsubscribe,
    subscribeToVm,
  }
}

/**
 * Hook for listening to system-wide events (not range-specific).
 * Useful for dashboard-level notifications.
 */
export function useRealtimeEvents(options: Omit<UseRealtimeRangeOptions, 'onStatusChange'> = {}) {
  return useRealtimeRange(null, {
    ...options,
    enabled: options.enabled ?? true,
  })
}
