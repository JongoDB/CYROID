// frontend/src/components/execution/EventLog.tsx
import { useEffect, useState, useRef } from 'react'
import { EventLog as EventLogType, EventType } from '../../types'
import { eventsApi } from '../../services/api'
import {
  Play, Square, RotateCcw, AlertCircle,
  Download, Upload, Plug, Activity, Rocket,
  CheckCircle, XCircle, Router, Network, Server, Loader2
} from 'lucide-react'

interface Props {
  rangeId: string
  maxHeight?: string
}

const eventIcons: Record<EventType, React.ReactNode> = {
  // Deployment progress events
  deployment_started: <Rocket className="w-4 h-4 text-blue-500" />,
  deployment_step: <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />,
  deployment_completed: <CheckCircle className="w-4 h-4 text-green-500" />,
  deployment_failed: <XCircle className="w-4 h-4 text-red-600" />,
  router_creating: <Router className="w-4 h-4 text-yellow-500" />,
  router_created: <Router className="w-4 h-4 text-green-500" />,
  network_creating: <Network className="w-4 h-4 text-yellow-500" />,
  network_created: <Network className="w-4 h-4 text-green-500" />,
  vm_creating: <Server className="w-4 h-4 text-yellow-500" />,
  // Range lifecycle events
  range_deployed: <Activity className="w-4 h-4 text-green-500" />,
  range_started: <Play className="w-4 h-4 text-green-500" />,
  range_stopped: <Square className="w-4 h-4 text-gray-500" />,
  range_teardown: <AlertCircle className="w-4 h-4 text-red-500" />,
  // VM lifecycle events
  vm_created: <Activity className="w-4 h-4 text-blue-500" />,
  vm_started: <Play className="w-4 h-4 text-green-500" />,
  vm_stopped: <Square className="w-4 h-4 text-red-500" />,
  vm_restarted: <RotateCcw className="w-4 h-4 text-blue-500" />,
  vm_error: <AlertCircle className="w-4 h-4 text-red-600" />,
  // Other events
  snapshot_created: <Download className="w-4 h-4 text-purple-500" />,
  snapshot_restored: <Upload className="w-4 h-4 text-purple-500" />,
  artifact_placed: <Download className="w-4 h-4 text-orange-500" />,
  inject_executed: <Activity className="w-4 h-4 text-yellow-500" />,
  inject_failed: <AlertCircle className="w-4 h-4 text-red-500" />,
  connection_established: <Plug className="w-4 h-4 text-green-500" />,
  connection_closed: <Plug className="w-4 h-4 text-gray-500" />,
}

export function EventLogComponent({ rangeId, maxHeight = '400px' }: Props) {
  const [events, setEvents] = useState<EventLogType[]>([])
  const [loading, setLoading] = useState(true)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    loadEvents()
    const interval = setInterval(loadEvents, 5000)
    return () => clearInterval(interval)
  }, [rangeId])

  const loadEvents = async () => {
    try {
      const response = await eventsApi.getEvents(rangeId, { limit: 100 })
      setEvents(response.data.events)
    } catch (error) {
      console.error('Failed to load events:', error)
    } finally {
      setLoading(false)
    }
  }

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString()
  }

  if (loading) {
    return <div className="animate-pulse bg-gray-100 h-32 rounded" />
  }

  return (
    <div
      ref={containerRef}
      className="bg-gray-900 rounded-lg overflow-hidden"
      style={{ maxHeight }}
    >
      <div className="px-4 py-2 bg-gray-800 border-b border-gray-700">
        <h3 className="text-sm font-medium text-gray-200">Event Log</h3>
      </div>
      <div className="overflow-y-auto p-2 space-y-1" style={{ maxHeight: `calc(${maxHeight} - 40px)` }}>
        {events.length === 0 ? (
          <p className="text-gray-500 text-sm p-2">No events yet</p>
        ) : (
          events.map((event) => (
            <div
              key={event.id}
              className="flex items-start gap-2 px-2 py-1 hover:bg-gray-800 rounded text-sm"
            >
              <span className="text-gray-500 font-mono text-xs">
                {formatTime(event.created_at)}
              </span>
              {eventIcons[event.event_type] || <Activity className="w-4 h-4" />}
              <span className="text-gray-300">{event.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
