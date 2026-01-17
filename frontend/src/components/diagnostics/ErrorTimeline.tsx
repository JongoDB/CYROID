// frontend/src/components/diagnostics/ErrorTimeline.tsx
import { useState, useEffect } from 'react'
import { AlertTriangle, RefreshCw, FileText, Clock } from 'lucide-react'
import { eventsApi } from '../../services/api'
import type { EventLog, VM } from '../../types'
import clsx from 'clsx'

interface ErrorTimelineProps {
  rangeId: string
  vms: VM[]
  onViewLogs: (vm: VM) => void
}

const ERROR_EVENT_TYPES = ['vm_error', 'deployment_failed', 'inject_failed']

export function ErrorTimeline({ rangeId, vms, onViewLogs }: ErrorTimelineProps) {
  const [events, setEvents] = useState<EventLog[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<string>('all')

  const fetchEvents = async () => {
    setLoading(true)
    try {
      const response = await eventsApi.getEvents(rangeId, {
        limit: 50,
        offset: 0,
        event_types: ERROR_EVENT_TYPES
      })
      setEvents(response.data.events)
    } catch (err) {
      console.error('Failed to fetch events:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchEvents()
  }, [rangeId])

  const filteredEvents = filter === 'all'
    ? events
    : events.filter(e => e.event_type === filter)

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp)
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  }

  const getVmForEvent = (event: EventLog): VM | undefined => {
    if (event.vm_id) {
      return vms.find(vm => vm.id === event.vm_id)
    }
    return undefined
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
      <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-900">Error Timeline</h3>
        <div className="flex items-center gap-2">
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="text-xs border border-gray-300 rounded px-2 py-1"
          >
            <option value="all">All Errors</option>
            <option value="vm_error">VM Errors</option>
            <option value="deployment_failed">Deployment</option>
            <option value="inject_failed">Inject Failed</option>
          </select>
          <button
            onClick={fetchEvents}
            disabled={loading}
            className="p-1 text-gray-400 hover:text-gray-600 disabled:opacity-50"
            title="Refresh"
          >
            <RefreshCw className={clsx("w-4 h-4", loading && "animate-spin")} />
          </button>
        </div>
      </div>

      <div className="max-h-80 overflow-y-auto">
        {loading && events.length === 0 ? (
          <div className="p-4 text-center text-gray-500">
            <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2" />
            Loading events...
          </div>
        ) : filteredEvents.length === 0 ? (
          <div className="p-4 text-center text-gray-500">
            <AlertTriangle className="w-5 h-5 mx-auto mb-2 text-gray-400" />
            No error events found
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {filteredEvents.map(event => {
              const vm = getVmForEvent(event)
              return (
                <div key={event.id} className="px-4 py-3 hover:bg-gray-50">
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 mt-0.5">
                      <AlertTriangle className="w-4 h-4 text-red-500" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 text-xs text-gray-500 mb-1">
                        <Clock className="w-3 h-3" />
                        <span>{formatTime(event.created_at)}</span>
                        <span className="px-1.5 py-0.5 bg-red-100 text-red-700 rounded">
                          {event.event_type.replace('_', ' ')}
                        </span>
                      </div>
                      <p className="text-sm text-gray-700 break-words">
                        {event.message}
                      </p>
                      {vm && (
                        <button
                          onClick={() => onViewLogs(vm)}
                          className="mt-2 inline-flex items-center gap-1 text-xs text-primary-600 hover:text-primary-700"
                        >
                          <FileText className="w-3 h-3" />
                          View Logs ({vm.hostname})
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
