// frontend/src/pages/TrainingEvents.tsx
import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Plus,
  Search,
  Filter,
  Calendar,
  Clock,
  MapPin,
  Users,
  Play,
  Rocket,
  CheckCircle,
  XCircle,
  MoreVertical,
  Edit,
  Trash2,
  CalendarCheck,
} from 'lucide-react'
import { trainingEventsApi, TrainingEventListItem, EventStatus } from '../services/api'
import { useAuthStore } from '../stores/authStore'
import { format, formatDistanceToNow, parseISO, isAfter, isBefore } from 'date-fns'

const STATUS_INFO: Record<EventStatus, { label: string; color: string; icon: typeof Calendar }> = {
  draft: { label: 'Draft', color: 'bg-gray-100 text-gray-800', icon: Calendar },
  scheduled: { label: 'Scheduled', color: 'bg-blue-100 text-blue-800', icon: CalendarCheck },
  running: { label: 'Running', color: 'bg-green-100 text-green-800', icon: Play },
  completed: { label: 'Completed', color: 'bg-purple-100 text-purple-800', icon: CheckCircle },
  cancelled: { label: 'Cancelled', color: 'bg-red-100 text-red-800', icon: XCircle },
}

export default function TrainingEvents() {
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const [events, setEvents] = useState<TrainingEventListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<EventStatus | ''>('')
  const [myEventsOnly, setMyEventsOnly] = useState(false)
  const [showFilters, setShowFilters] = useState(false)
  const [activeMenu, setActiveMenu] = useState<string | null>(null)

  const isInstructor = user?.roles?.includes('admin') || user?.roles?.includes('engineer')

  useEffect(() => {
    loadEvents()
  }, [statusFilter, myEventsOnly])

  async function loadEvents() {
    setLoading(true)
    setError(null)
    try {
      const params: Record<string, unknown> = {}
      if (statusFilter) params.status = statusFilter
      if (myEventsOnly) params.my_events = true
      const response = await trainingEventsApi.list(params as { status?: EventStatus; my_events?: boolean })
      setEvents(response.data)
    } catch (err) {
      setError('Failed to load events')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const filteredEvents = events.filter((event) => {
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      return (
        event.name.toLowerCase().includes(query) ||
        event.description?.toLowerCase().includes(query) ||
        event.tags.some((tag) => tag.toLowerCase().includes(query))
      )
    }
    return true
  })

  async function handleDelete(id: string) {
    if (!confirm('Are you sure you want to delete this event? All associated student labs will be permanently deleted.')) return
    try {
      await trainingEventsApi.delete(id)
      setEvents(events.filter((e) => e.id !== id))
    } catch (err) {
      console.error('Failed to delete:', err)
    }
    setActiveMenu(null)
  }

  async function handleStatusChange(id: string, action: 'publish' | 'start' | 'complete' | 'cancel') {
    // Confirm destructive actions
    if (action === 'complete') {
      if (!confirm('Are you sure you want to complete this event? All associated student labs will be permanently deleted.')) {
        setActiveMenu(null)
        return
      }
    } else if (action === 'cancel') {
      if (!confirm('Are you sure you want to cancel this event? Student labs will remain until the event is deleted.')) {
        setActiveMenu(null)
        return
      }
    }

    try {
      switch (action) {
        case 'publish':
          await trainingEventsApi.publish(id)
          break
        case 'start':
          // Always deploy labs when starting
          await trainingEventsApi.start(id, true)
          break
        case 'complete':
          await trainingEventsApi.complete(id)
          break
        case 'cancel':
          await trainingEventsApi.cancel(id)
          break
      }
      loadEvents()
    } catch (err) {
      console.error(`Failed to ${action}:`, err)
    }
    setActiveMenu(null)
  }

  async function handleJoin(eventId: string) {
    try {
      await trainingEventsApi.join(eventId)
      loadEvents()
    } catch (err) {
      console.error('Failed to join:', err)
    }
  }

  function getEventTimeInfo(event: TrainingEventListItem) {
    const start = parseISO(event.start_datetime)
    const now = new Date()

    if (event.is_all_day) {
      return format(start, 'MMM d, yyyy')
    }

    if (isBefore(start, now)) {
      if (event.status === 'running') {
        return `Started ${formatDistanceToNow(start, { addSuffix: true })}`
      }
      return format(start, 'MMM d, yyyy h:mm a')
    }

    if (isAfter(start, now)) {
      return `Starts ${formatDistanceToNow(start, { addSuffix: true })}`
    }

    return format(start, 'MMM d, yyyy h:mm a')
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Training Events</h1>
          <p className="text-sm text-gray-500 mt-1">
            Schedule and manage training exercises
          </p>
        </div>
        {isInstructor && (
          <Link
            to="/events/new"
            className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700"
          >
            <Plus className="h-4 w-4 mr-2" />
            New Event
          </Link>
        )}
      </div>

      {/* Search and Filters */}
      <div className="bg-white shadow rounded-lg p-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
            <input
              type="text"
              placeholder="Search events..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500"
            />
          </div>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`inline-flex items-center px-3 py-2 border rounded-md text-sm font-medium ${
              showFilters || statusFilter || myEventsOnly
                ? 'border-primary-500 text-primary-700 bg-primary-50'
                : 'border-gray-300 text-gray-700 bg-white'
            }`}
          >
            <Filter className="h-4 w-4 mr-2" />
            Filters
          </button>
        </div>

        {showFilters && (
          <div className="mt-4 pt-4 border-t border-gray-200 grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as EventStatus | '')}
                className="w-full border border-gray-300 rounded-md py-2 px-3 focus:ring-primary-500 focus:border-primary-500"
              >
                <option value="">All Statuses</option>
                {Object.entries(STATUS_INFO).map(([value, info]) => (
                  <option key={value} value={value}>
                    {info.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-end">
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={myEventsOnly}
                  onChange={(e) => setMyEventsOnly(e.target.checked)}
                  className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                />
                <span className="ml-2 text-sm text-gray-700">My events only</span>
              </label>
            </div>
          </div>
        )}
      </div>

      {/* Events List */}
      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
        </div>
      ) : error ? (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">{error}</div>
      ) : filteredEvents.length === 0 ? (
        <div className="bg-white shadow rounded-lg p-12 text-center">
          <Calendar className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-lg font-medium text-gray-900">No events found</h3>
          <p className="mt-1 text-sm text-gray-500">
            {searchQuery || statusFilter
              ? 'Try adjusting your filters'
              : 'Get started by creating your first training event'}
          </p>
          {isInstructor && !searchQuery && !statusFilter && (
            <Link
              to="/events/new"
              className="mt-4 inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700"
            >
              <Plus className="h-4 w-4 mr-2" />
              Create Event
            </Link>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          {filteredEvents.map((event) => {
            const statusInfo = STATUS_INFO[event.status]
            const StatusIcon = statusInfo.icon
            const canManage = user?.id === event.created_by_id || user?.roles?.includes('admin')

            return (
              <div
                key={event.id}
                className="bg-white shadow rounded-lg hover:shadow-md transition-shadow"
              >
                <div className="p-4 sm:p-6">
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${statusInfo.color}`}>
                          <StatusIcon className="h-3 w-3 mr-1" />
                          {statusInfo.label}
                        </span>
                        {event.has_blueprint && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-indigo-100 text-indigo-700">
                            Has Blueprint
                          </span>
                        )}
                        {event.tags.slice(0, 2).map((tag) => (
                          <span
                            key={tag}
                            className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-600"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                      <Link to={`/events/${event.id}`} className="block mt-2">
                        <h3 className="text-lg font-medium text-gray-900 hover:text-primary-600 truncate">
                          {event.name}
                        </h3>
                      </Link>
                      {event.description && (
                        <p className="mt-1 text-sm text-gray-500 line-clamp-2">{event.description}</p>
                      )}
                      <div className="mt-3 flex items-center flex-wrap gap-4 text-sm text-gray-500">
                        <div className="flex items-center">
                          <Clock className="h-4 w-4 mr-1" />
                          {getEventTimeInfo(event)}
                        </div>
                        {event.location && (
                          <div className="flex items-center">
                            <MapPin className="h-4 w-4 mr-1" />
                            {event.location}
                          </div>
                        )}
                        <div className="flex items-center">
                          <Users className="h-4 w-4 mr-1" />
                          {event.participant_count} participant{event.participant_count !== 1 ? 's' : ''}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2 ml-4">
                      {/* Join button for non-managers */}
                      {!canManage && event.status === 'scheduled' && (
                        <button
                          onClick={() => handleJoin(event.id)}
                          className="inline-flex items-center px-3 py-1 border border-primary-300 text-sm font-medium rounded text-primary-700 bg-primary-50 hover:bg-primary-100"
                        >
                          Join
                        </button>
                      )}
                      {canManage && (
                        <div className="relative">
                          <button
                            onClick={() => setActiveMenu(activeMenu === event.id ? null : event.id)}
                            className="p-2 rounded-full hover:bg-gray-100"
                          >
                            <MoreVertical className="h-5 w-5 text-gray-400" />
                          </button>
                          {activeMenu === event.id && (
                            <div className="absolute right-0 mt-2 w-48 bg-white rounded-md shadow-lg ring-1 ring-black ring-opacity-5 z-50">
                              <div className="py-1">
                                <button
                                  onClick={() => { navigate(`/events/${event.id}`); setActiveMenu(null); }}
                                  className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                                >
                                  <Edit className="h-4 w-4 mr-3" />
                                  Edit
                                </button>
                                {event.status === 'draft' && (
                                  <button
                                    onClick={() => handleStatusChange(event.id, 'publish')}
                                    className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                                  >
                                    <CalendarCheck className="h-4 w-4 mr-3" />
                                    Publish
                                  </button>
                                )}
                                {(event.status === 'draft' || event.status === 'scheduled') && (
                                  <button
                                    onClick={() => handleStatusChange(event.id, 'start')}
                                    className="flex items-center w-full px-4 py-2 text-sm text-green-700 hover:bg-green-50"
                                  >
                                    <Rocket className="h-4 w-4 mr-3" />
                                    Start & Deploy Labs
                                  </button>
                                )}
                                {event.status === 'running' && (
                                  <button
                                    onClick={() => handleStatusChange(event.id, 'complete')}
                                    className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                                  >
                                    <CheckCircle className="h-4 w-4 mr-3" />
                                    Complete
                                  </button>
                                )}
                                {event.status !== 'completed' && event.status !== 'cancelled' && (
                                  <button
                                    onClick={() => handleStatusChange(event.id, 'cancel')}
                                    className="flex items-center w-full px-4 py-2 text-sm text-red-700 hover:bg-red-50"
                                  >
                                    <XCircle className="h-4 w-4 mr-3" />
                                    Cancel
                                  </button>
                                )}
                                <div className="border-t border-gray-100">
                                  <button
                                    onClick={() => handleDelete(event.id)}
                                    className="flex items-center w-full px-4 py-2 text-sm text-red-700 hover:bg-red-50"
                                  >
                                    <Trash2 className="h-4 w-4 mr-3" />
                                    Delete
                                  </button>
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
