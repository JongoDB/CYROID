import { useState, useEffect } from 'react'
import { eventsApi } from '../../services/api'
import type { EventLog } from '../../types'
import {
  Rocket, Play, Square, Server, Network, AlertCircle,
  Loader2, Activity, Router, CheckCircle, XCircle
} from 'lucide-react'

interface Props {
  rangeId: string
}

const eventIcons: Record<string, React.ElementType> = {
  deployment_started: Rocket,
  deployment_completed: CheckCircle,
  deployment_failed: XCircle,
  deployment_step: Activity,
  router_creating: Router,
  router_created: Router,
  range_started: Play,
  range_stopped: Square,
  vm_creating: Server,
  vm_started: Server,
  vm_stopped: Server,
  vm_error: AlertCircle,
  network_creating: Network,
  network_created: Network,
}

const eventColors: Record<string, string> = {
  deployment_started: 'text-blue-500',
  deployment_completed: 'text-green-500',
  deployment_failed: 'text-red-500',
  deployment_step: 'text-blue-400',
  router_creating: 'text-yellow-500',
  router_created: 'text-green-500',
  range_started: 'text-green-500',
  range_stopped: 'text-gray-500',
  vm_creating: 'text-yellow-500',
  vm_started: 'text-green-500',
  vm_stopped: 'text-gray-500',
  vm_error: 'text-red-500',
  network_creating: 'text-yellow-500',
  network_created: 'text-blue-500',
}

function groupEventsByDay(events: EventLog[]): Map<string, EventLog[]> {
  const groups = new Map<string, EventLog[]>()
  const today = new Date().toDateString()
  const yesterday = new Date(Date.now() - 86400000).toDateString()

  for (const event of events) {
    const date = new Date(event.created_at).toDateString()
    let label = date
    if (date === today) label = 'Today'
    else if (date === yesterday) label = 'Yesterday'

    if (!groups.has(label)) groups.set(label, [])
    groups.get(label)!.push(event)
  }
  return groups
}

export function ActivityTab({ rangeId }: Props) {
  const [events, setEvents] = useState<EventLog[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    eventsApi.getEvents(rangeId, { limit: 100 })
      .then((res) => setEvents(res.data.events))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [rangeId])

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
      </div>
    )
  }

  const grouped = groupEventsByDay(events)

  return (
    <div className="p-6">
      <h2 className="text-lg font-semibold mb-4">Activity</h2>

      {events.length === 0 ? (
        <p className="text-gray-500">No activity recorded yet.</p>
      ) : (
        <div className="space-y-6">
          {Array.from(grouped.entries()).map(([day, dayEvents]) => (
            <div key={day}>
              <h3 className="text-sm font-medium text-gray-500 mb-2 border-b border-gray-100 pb-1">{day}</h3>
              <div className="space-y-1">
                {dayEvents.map(event => {
                  const Icon = eventIcons[event.event_type] || Activity
                  const colorClass = eventColors[event.event_type] || 'text-gray-500'
                  const time = new Date(event.created_at).toLocaleTimeString([], {
                    hour: '2-digit',
                    minute: '2-digit'
                  })
                  const username = event.user?.username || event.user?.email || 'System'

                  return (
                    <div key={event.id} className="flex items-start gap-3 py-2 hover:bg-gray-50 rounded px-2 -mx-2">
                      <Icon className={`w-5 h-5 mt-0.5 flex-shrink-0 ${colorClass}`} />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900">
                          {event.message}
                        </p>
                        <p className="text-xs text-gray-500">
                          by {username}
                        </p>
                      </div>
                      <span className="text-xs text-gray-400 whitespace-nowrap">
                        {time}
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
