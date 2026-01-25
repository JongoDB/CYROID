// frontend/src/pages/StudentPortal.tsx
import { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import { trainingEventsApi, rangesApi, TrainingEventListItem } from '../services/api'
import type { Range } from '../types'
import { BookOpen, Calendar, MapPin, Play, Users, Server, ChevronLeft, ChevronRight, Loader2, Monitor } from 'lucide-react'
import clsx from 'clsx'

export default function StudentPortal() {
  const { user } = useAuthStore()
  const [events, setEvents] = useState<TrainingEventListItem[]>([])
  const [myRanges, setMyRanges] = useState<Range[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isLoadingRanges, setIsLoadingRanges] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeView, setActiveView] = useState<'list' | 'calendar'>('list')
  const [calendarDate, setCalendarDate] = useState(new Date())

  useEffect(() => {
    loadMyEvents()
    loadMyRanges()
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

  const loadMyRanges = async () => {
    setIsLoadingRanges(true)
    try {
      const response = await rangesApi.getMyRanges()
      setMyRanges(response.data)
    } catch (err) {
      console.error('Error loading ranges:', err)
    } finally {
      setIsLoadingRanges(false)
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
      stopped: 'bg-gray-100 text-gray-800',
      deploying: 'bg-yellow-100 text-yellow-800',
      error: 'bg-red-100 text-red-800',
    }
    return (
      <span className={clsx('px-2 py-1 text-xs font-medium rounded-full', styles[status] || styles.draft)}>
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </span>
    )
  }

  // Calendar helpers
  const getDaysInMonth = (date: Date) => {
    const year = date.getFullYear()
    const month = date.getMonth()
    const firstDay = new Date(year, month, 1)
    const lastDay = new Date(year, month + 1, 0)
    const daysInMonth = lastDay.getDate()
    const startingDay = firstDay.getDay()

    const days: (number | null)[] = []
    // Add empty cells for days before the first day
    for (let i = 0; i < startingDay; i++) {
      days.push(null)
    }
    // Add the days of the month
    for (let i = 1; i <= daysInMonth; i++) {
      days.push(i)
    }
    return days
  }

  const getEventsForDay = (day: number) => {
    const year = calendarDate.getFullYear()
    const month = calendarDate.getMonth()
    const dayDate = new Date(year, month, day)
    const dayStart = dayDate.setHours(0, 0, 0, 0)
    const dayEnd = dayDate.setHours(23, 59, 59, 999)

    return events.filter(event => {
      const eventStart = new Date(event.start_datetime).getTime()
      return eventStart >= dayStart && eventStart <= dayEnd
    })
  }

  const calendarDays = useMemo(() => getDaysInMonth(calendarDate), [calendarDate])
  const monthNames = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
  const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

  const navigateMonth = (direction: 'prev' | 'next') => {
    setCalendarDate(prev => {
      const newDate = new Date(prev)
      if (direction === 'prev') {
        newDate.setMonth(newDate.getMonth() - 1)
      } else {
        newDate.setMonth(newDate.getMonth() + 1)
      }
      return newDate
    })
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

      {/* My Labs Section */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <Server className="w-5 h-5 text-primary-600" />
            My Labs
          </h2>
        </div>

        {isLoadingRanges ? (
          <div className="flex justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-primary-600" />
          </div>
        ) : myRanges.length === 0 ? (
          <div className="p-8 text-center">
            <Server className="mx-auto h-10 w-10 text-gray-400" />
            <p className="mt-3 text-gray-500">
              You are not currently assigned to any labs.
            </p>
          </div>
        ) : (
          <div className="p-4">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {myRanges.map((range) => (
                <div
                  key={range.id}
                  className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow bg-white"
                >
                  <div className="flex items-start justify-between">
                    <h3 className="font-semibold text-gray-900 line-clamp-1">{range.name}</h3>
                    {getStatusBadge(range.status)}
                  </div>
                  {range.description && (
                    <p className="mt-2 text-sm text-gray-600 line-clamp-2">{range.description}</p>
                  )}
                  <div className="mt-4 flex items-center justify-between">
                    <span className="text-xs text-gray-500">
                      {range.vm_count} VM{range.vm_count !== 1 ? 's' : ''} / {range.network_count} Network{range.network_count !== 1 ? 's' : ''}
                    </span>
                    {range.status === 'running' && (
                      <Link
                        to={`/ranges/${range.id}`}
                        className="inline-flex items-center px-3 py-1.5 text-sm font-medium text-white bg-green-600 rounded-md hover:bg-green-700 transition-colors"
                      >
                        <Monitor className="h-4 w-4 mr-1" />
                        Open Console
                      </Link>
                    )}
                    {range.status !== 'running' && (
                      <Link
                        to={`/ranges/${range.id}`}
                        className="text-sm text-primary-600 hover:text-primary-700 font-medium"
                      >
                        View Details
                      </Link>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Events Section with Toggle */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <Calendar className="w-5 h-5 text-primary-600" />
            Your Training Events
          </h2>
          <div className="flex items-center gap-2 bg-gray-100 p-1 rounded-lg">
            <button
              onClick={() => setActiveView('list')}
              className={clsx(
                'px-3 py-1 text-sm font-medium rounded-md transition-colors',
                activeView === 'list' ? 'bg-white shadow text-gray-900' : 'text-gray-600 hover:text-gray-900'
              )}
            >
              List
            </button>
            <button
              onClick={() => setActiveView('calendar')}
              className={clsx(
                'px-3 py-1 text-sm font-medium rounded-md transition-colors',
                activeView === 'calendar' ? 'bg-white shadow text-gray-900' : 'text-gray-600 hover:text-gray-900'
              )}
            >
              Calendar
            </button>
          </div>
        </div>

        {/* Loading State */}
        {isLoading && (
          <div className="flex justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="m-4 bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
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
          <div className="p-8 text-center">
            <Calendar className="mx-auto h-10 w-10 text-gray-400" />
            <h3 className="mt-3 text-gray-900 font-medium">No Active Training Events</h3>
            <p className="mt-1 text-gray-500 text-sm">
              You are not currently enrolled in any scheduled or running training events.
            </p>
          </div>
        )}

        {/* List View */}
        {!isLoading && !error && events.length > 0 && activeView === 'list' && (
          <div className="p-4">
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {events.map((event) => (
                <div
                  key={event.id}
                  className="border border-gray-200 rounded-lg overflow-hidden hover:shadow-md transition-shadow bg-white"
                >
                  <div className="p-4">
                    <div className="flex items-start justify-between">
                      <h3 className="font-semibold text-gray-900 line-clamp-1">
                        {event.name}
                      </h3>
                      {getStatusBadge(event.status)}
                    </div>

                    {event.description && (
                      <p className="mt-2 text-sm text-gray-600 line-clamp-2">
                        {event.description}
                      </p>
                    )}

                    <div className="mt-3 space-y-1.5 text-sm text-gray-500">
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

                  <div className="px-4 py-3 bg-gray-50 border-t border-gray-200 flex items-center justify-between">
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

        {/* Calendar View */}
        {!isLoading && !error && activeView === 'calendar' && (
          <div className="p-4">
            {/* Calendar Navigation */}
            <div className="flex items-center justify-between mb-4">
              <button
                onClick={() => navigateMonth('prev')}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <ChevronLeft className="w-5 h-5 text-gray-600" />
              </button>
              <h3 className="text-lg font-semibold text-gray-900">
                {monthNames[calendarDate.getMonth()]} {calendarDate.getFullYear()}
              </h3>
              <button
                onClick={() => navigateMonth('next')}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <ChevronRight className="w-5 h-5 text-gray-600" />
              </button>
            </div>

            {/* Calendar Grid */}
            <div className="border border-gray-200 rounded-lg overflow-hidden">
              {/* Day Headers */}
              <div className="grid grid-cols-7 bg-gray-50 border-b border-gray-200">
                {dayNames.map((day) => (
                  <div key={day} className="px-2 py-3 text-center text-xs font-semibold text-gray-600 uppercase">
                    {day}
                  </div>
                ))}
              </div>

              {/* Calendar Days */}
              <div className="grid grid-cols-7">
                {calendarDays.map((day, index) => {
                  const dayEvents = day ? getEventsForDay(day) : []
                  const isToday = day !== null &&
                    new Date().getDate() === day &&
                    new Date().getMonth() === calendarDate.getMonth() &&
                    new Date().getFullYear() === calendarDate.getFullYear()

                  return (
                    <div
                      key={index}
                      className={clsx(
                        'min-h-[80px] p-1 border-b border-r border-gray-200',
                        index % 7 === 6 && 'border-r-0',
                        !day && 'bg-gray-50'
                      )}
                    >
                      {day && (
                        <>
                          <div className={clsx(
                            'text-sm font-medium mb-1 w-6 h-6 flex items-center justify-center rounded-full',
                            isToday ? 'bg-primary-600 text-white' : 'text-gray-700'
                          )}>
                            {day}
                          </div>
                          <div className="space-y-1">
                            {dayEvents.slice(0, 2).map((event) => (
                              <Link
                                key={event.id}
                                to={`/events/${event.id}`}
                                className={clsx(
                                  'block text-xs px-1.5 py-0.5 rounded truncate',
                                  event.status === 'running'
                                    ? 'bg-green-100 text-green-800 hover:bg-green-200'
                                    : 'bg-blue-100 text-blue-800 hover:bg-blue-200'
                                )}
                                title={event.name}
                              >
                                {event.name}
                              </Link>
                            ))}
                            {dayEvents.length > 2 && (
                              <span className="text-xs text-gray-500 px-1.5">
                                +{dayEvents.length - 2} more
                              </span>
                            )}
                          </div>
                        </>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Legend */}
            <div className="mt-4 flex items-center gap-4 text-xs text-gray-600">
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded bg-blue-100 border border-blue-200"></span>
                <span>Scheduled</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded bg-green-100 border border-green-200"></span>
                <span>Running</span>
              </div>
            </div>
          </div>
        )}
      </div>

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
