// frontend/src/pages/StudentPortal.tsx
import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import { trainingEventsApi, TrainingEventListItem } from '../services/api'
import { BookOpen, Calendar, MapPin, Play, Users } from 'lucide-react'
import clsx from 'clsx'

export default function StudentPortal() {
  const { user } = useAuthStore()
  const [events, setEvents] = useState<TrainingEventListItem[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadMyEvents()
  }, [])

  const loadMyEvents = async () => {
    setIsLoading(true)
    setError(null)
    try {
      // Use dedicated my-events endpoint for events where user is a participant
      const response = await trainingEventsApi.getMyEvents()
      // Filter to show only scheduled or running events for students
      const activeEvents = response.data.filter(
        e => e.status === 'scheduled' || e.status === 'running'
      )
      setEvents(activeEvents)
    } catch (err) {
      setError('Failed to load your training events')
      console.error('Error loading events:', err)
    } finally {
      setIsLoading(false)
    }
  }

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleDateString('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
  }

  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
    })
  }

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      scheduled: 'bg-blue-100 text-blue-800',
      running: 'bg-green-100 text-green-800',
      draft: 'bg-gray-100 text-gray-800',
      completed: 'bg-purple-100 text-purple-800',
      cancelled: 'bg-red-100 text-red-800',
    }
    return (
      <span className={clsx('px-2 py-1 text-xs font-medium rounded-full', styles[status] || styles.draft)}>
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </span>
    )
  }

  return (
    <div className="space-y-6">
      {/* Welcome Header */}
      <div className="bg-gradient-to-r from-primary-600 to-primary-700 rounded-lg shadow-lg p-6 text-white">
        <h1 className="text-2xl font-bold">Welcome, {user?.username}</h1>
        <p className="mt-1 text-primary-100">
          Access your training events and labs from this portal.
        </p>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
          {error}
          <button
            onClick={loadMyEvents}
            className="ml-2 text-red-600 underline hover:text-red-800"
          >
            Retry
          </button>
        </div>
      )}

      {/* No Events State */}
      {!isLoading && !error && events.length === 0 && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8 text-center">
          <Calendar className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-4 text-lg font-medium text-gray-900">No Active Training Events</h3>
          <p className="mt-2 text-gray-500">
            You are not currently enrolled in any scheduled or running training events.
            Check back later or contact your instructor.
          </p>
        </div>
      )}

      {/* Events List */}
      {!isLoading && events.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">Your Training Events</h2>

          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {events.map((event) => (
              <div
                key={event.id}
                className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden hover:shadow-md transition-shadow"
              >
                <div className="p-5">
                  <div className="flex items-start justify-between">
                    <h3 className="text-lg font-semibold text-gray-900 line-clamp-1">
                      {event.name}
                    </h3>
                    {getStatusBadge(event.status)}
                  </div>

                  {event.description && (
                    <p className="mt-2 text-sm text-gray-600 line-clamp-2">
                      {event.description}
                    </p>
                  )}

                  <div className="mt-4 space-y-2 text-sm text-gray-500">
                    <div className="flex items-center">
                      <Calendar className="h-4 w-4 mr-2 text-gray-400" />
                      <span>
                        {formatDate(event.start_datetime)}
                        {!event.is_all_day && ` at ${formatTime(event.start_datetime)}`}
                      </span>
                    </div>

                    {event.location && (
                      <div className="flex items-center">
                        <MapPin className="h-4 w-4 mr-2 text-gray-400" />
                        <span className="truncate">{event.location}</span>
                      </div>
                    )}

                    {event.organization && (
                      <div className="flex items-center">
                        <Users className="h-4 w-4 mr-2 text-gray-400" />
                        <span className="truncate">{event.organization}</span>
                      </div>
                    )}
                  </div>
                </div>

                <div className="px-5 py-3 bg-gray-50 border-t border-gray-200 flex items-center justify-between">
                  <Link
                    to={`/events/${event.id}`}
                    className="text-sm text-primary-600 hover:text-primary-700 font-medium flex items-center"
                  >
                    <BookOpen className="h-4 w-4 mr-1" />
                    View Details
                  </Link>

                  {event.status === 'running' && event.has_blueprint && (
                    <Link
                      to={`/lab/${event.id}`}
                      className="inline-flex items-center px-3 py-1.5 text-sm font-medium text-white bg-green-600 rounded-md hover:bg-green-700 transition-colors"
                    >
                      <Play className="h-4 w-4 mr-1" />
                      Open Lab
                    </Link>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Quick Links Section */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Quick Links</h2>
        <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3">
          <Link
            to="/events"
            className="flex items-center p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <Calendar className="h-8 w-8 text-primary-600 mr-3" />
            <div>
              <div className="font-medium text-gray-900">All Events</div>
              <div className="text-sm text-gray-500">Browse training events</div>
            </div>
          </Link>
        </div>
      </div>
    </div>
  )
}
