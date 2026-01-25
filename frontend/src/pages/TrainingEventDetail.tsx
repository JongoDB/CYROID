// frontend/src/pages/TrainingEventDetail.tsx
import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Save,
  ArrowLeft,
  Calendar,
  Clock,
  MapPin,
  Users,
  Plus,
  X,
  Tag,
  Play,
  CheckCircle,
  XCircle,
  CalendarCheck,
  BookOpen,
  LayoutTemplate,
  Trash2,
  Monitor,
  Rocket,
  Loader2,
  ExternalLink,
  RotateCcw,
} from 'lucide-react'
import {
  trainingEventsApi,
  TrainingEventDetail as TrainingEventDetailType,
  EventCreate,
  EventUpdate,
  EventStatus,
  blueprintsApi,
  Blueprint,
  contentApi,
  ContentListItem,
  usersApi,
  User,
} from '../services/api'
import { useAuthStore } from '../stores/authStore'
import { VMVisibilityControl } from '../components/events/VMVisibilityControl'
import { format, parseISO } from 'date-fns'
import DOMPurify from 'dompurify'

const STATUS_LABELS: Record<EventStatus, string> = {
  draft: 'Draft',
  scheduled: 'Scheduled',
  running: 'Running',
  completed: 'Completed',
  cancelled: 'Cancelled',
}

// Sanitize HTML to prevent XSS - uses DOMPurify for secure rendering
function sanitizeHtml(html: string): string {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: [
      'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'br', 'hr',
      'strong', 'b', 'em', 'i', 'u', 's', 'strike', 'code', 'pre',
      'ul', 'ol', 'li', 'blockquote',
      'a', 'img',
      'table', 'thead', 'tbody', 'tr', 'th', 'td',
      'div', 'span',
    ],
    ALLOWED_ATTR: ['href', 'src', 'alt', 'title', 'class', 'target', 'rel', 'colspan', 'rowspan'],
  })
}

export default function TrainingEventDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const isNew = id === 'new'

  const [loading, setLoading] = useState(!isNew)
  const [saving, setSaving] = useState(false)
  const [event, setEvent] = useState<TrainingEventDetailType | null>(null)

  // Form state
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [startDatetime, setStartDatetime] = useState('')
  const [endDatetime, setEndDatetime] = useState('')
  const [isAllDay, setIsAllDay] = useState(false)
  const [timezone, setTimezone] = useState('UTC')
  const [organization, setOrganization] = useState('')
  const [location, setLocation] = useState('')
  const [blueprintId, setBlueprintId] = useState('')
  const [selectedContentIds, setSelectedContentIds] = useState<string[]>([])
  const [allowedRoles, setAllowedRoles] = useState<string[]>([])
  const [tags, setTags] = useState<string[]>([])
  const [tagInput, setTagInput] = useState('')

  // Dropdown data
  const [blueprints, setBlueprints] = useState<Blueprint[]>([])
  const [contentItems, setContentItems] = useState<ContentListItem[]>([])
  const [users, setUsers] = useState<User[]>([])

  // Participant management
  const [selectedUserId, setSelectedUserId] = useState('')
  const [participantRole, setParticipantRole] = useState('student')

  // Briefing view
  const [showBriefing, setShowBriefing] = useState(false)
  const [briefingContent, setBriefingContent] = useState<{ title: string; html: string }[]>([])

  const canManage = event
    ? user?.id === event.created_by_id || user?.roles?.includes('admin')
    : user?.roles?.includes('admin') || user?.roles?.includes('engineer')

  useEffect(() => {
    loadDropdownData()
    if (!isNew && id) {
      loadEvent(id)
    }
  }, [id, isNew])

  async function loadDropdownData() {
    try {
      const [blueprintsRes, contentRes, usersRes] = await Promise.all([
        blueprintsApi.list(),
        contentApi.list({ published_only: true }),
        usersApi.list(),
      ])
      setBlueprints(blueprintsRes.data)
      setContentItems(contentRes.data)
      setUsers(usersRes.data)
    } catch (err) {
      console.error('Failed to load dropdown data:', err)
    }
  }

  async function loadEvent(eventId: string) {
    setLoading(true)
    try {
      const response = await trainingEventsApi.get(eventId)
      const data = response.data
      setEvent(data)
      setName(data.name)
      setDescription(data.description || '')
      setStartDatetime(format(parseISO(data.start_datetime), "yyyy-MM-dd'T'HH:mm"))
      if (data.end_datetime) {
        setEndDatetime(format(parseISO(data.end_datetime), "yyyy-MM-dd'T'HH:mm"))
      }
      setIsAllDay(data.is_all_day)
      setTimezone(data.timezone)
      setOrganization(data.organization || '')
      setLocation(data.location || '')
      setBlueprintId(data.blueprint_id || '')
      setSelectedContentIds(data.content_ids || [])
      setAllowedRoles(data.allowed_roles || [])
      setTags(data.tags || [])
    } catch (err) {
      console.error('Failed to load event:', err)
      navigate('/events')
    } finally {
      setLoading(false)
    }
  }

  async function handleSave() {
    if (!name.trim()) {
      alert('Name is required')
      return
    }
    if (!startDatetime) {
      alert('Start date/time is required')
      return
    }

    setSaving(true)
    try {
      if (isNew) {
        const data: EventCreate = {
          name,
          description: description || undefined,
          start_datetime: new Date(startDatetime).toISOString(),
          end_datetime: endDatetime ? new Date(endDatetime).toISOString() : undefined,
          is_all_day: isAllDay,
          timezone,
          organization: organization || undefined,
          location: location || undefined,
          blueprint_id: blueprintId || undefined,
          content_ids: selectedContentIds,
          allowed_roles: allowedRoles,
          tags,
        }
        const response = await trainingEventsApi.create(data)
        navigate(`/events/${response.data.id}`)
      } else if (id) {
        const data: EventUpdate = {
          name,
          description: description || undefined,
          start_datetime: new Date(startDatetime).toISOString(),
          end_datetime: endDatetime ? new Date(endDatetime).toISOString() : undefined,
          is_all_day: isAllDay,
          timezone,
          organization: organization || undefined,
          location: location || undefined,
          blueprint_id: blueprintId || undefined,
          content_ids: selectedContentIds,
          allowed_roles: allowedRoles,
          tags,
        }
        await trainingEventsApi.update(id, data)
        await loadEvent(id)
      }
    } catch (err) {
      console.error('Failed to save:', err)
      alert('Failed to save event')
    } finally {
      setSaving(false)
    }
  }

  function handleAddTag() {
    const tag = tagInput.trim()
    if (tag && !tags.includes(tag)) {
      setTags([...tags, tag])
      setTagInput('')
    }
  }

  function handleToggleRole(role: string) {
    if (allowedRoles.includes(role)) {
      setAllowedRoles(allowedRoles.filter((r) => r !== role))
    } else {
      setAllowedRoles([...allowedRoles, role])
    }
  }

  function handleToggleContent(contentId: string) {
    if (selectedContentIds.includes(contentId)) {
      setSelectedContentIds(selectedContentIds.filter((c) => c !== contentId))
    } else {
      setSelectedContentIds([...selectedContentIds, contentId])
    }
  }

  async function handleAddParticipant() {
    if (!selectedUserId || !id) return
    try {
      await trainingEventsApi.addParticipant(id, selectedUserId, participantRole)
      await loadEvent(id)
      setSelectedUserId('')
    } catch (err) {
      console.error('Failed to add participant:', err)
    }
  }

  async function handleRemoveParticipant(userId: string) {
    if (!id) return
    try {
      await trainingEventsApi.removeParticipant(id, userId)
      await loadEvent(id)
    } catch (err) {
      console.error('Failed to remove participant:', err)
    }
  }

  async function loadBriefing() {
    if (!id) return
    try {
      const response = await trainingEventsApi.getBriefing(id)
      setBriefingContent(
        response.data.content_items.map((item) => ({
          title: item.title,
          html: item.body_html || '',
        }))
      )
      setShowBriefing(true)
    } catch (err) {
      console.error('Failed to load briefing:', err)
    }
  }

  async function handleStatusChange(action: 'publish' | 'start' | 'complete' | 'cancel' | 'reactivate', autoDeploy = false) {
    if (!id) return
    try {
      switch (action) {
        case 'publish':
          await trainingEventsApi.publish(id)
          break
        case 'start':
          await trainingEventsApi.start(id, autoDeploy)
          break
        case 'complete':
          await trainingEventsApi.complete(id)
          break
        case 'cancel':
          await trainingEventsApi.cancel(id)
          break
        case 'reactivate':
          await trainingEventsApi.reactivate(id)
          break
      }
      await loadEvent(id)
    } catch (err) {
      console.error(`Failed to ${action}:`, err)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <button
            onClick={() => navigate('/events')}
            className="p-2 rounded-md hover:bg-gray-100"
          >
            <ArrowLeft className="h-5 w-5 text-gray-600" />
          </button>
          <h1 className="text-2xl font-semibold text-gray-900">
            {isNew ? 'Create Event' : 'Edit Event'}
          </h1>
          {event && (
            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
              event.status === 'draft' ? 'bg-gray-100 text-gray-800' :
              event.status === 'scheduled' ? 'bg-blue-100 text-blue-800' :
              event.status === 'running' ? 'bg-green-100 text-green-800' :
              event.status === 'completed' ? 'bg-purple-100 text-purple-800' :
              'bg-red-100 text-red-800'
            }`}>
              {STATUS_LABELS[event.status]}
            </span>
          )}
        </div>
        <div className="flex items-center space-x-3">
          {!isNew && event && (
            <button
              onClick={loadBriefing}
              className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
            >
              <BookOpen className="h-4 w-4 mr-2" />
              View Briefing
            </button>
          )}
          {canManage && (
            <button
              onClick={handleSave}
              disabled={saving}
              className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700 disabled:opacity-50"
            >
              <Save className="h-4 w-4 mr-2" />
              {saving ? 'Saving...' : 'Save'}
            </button>
          )}
        </div>
      </div>

      {/* Status Actions */}
      {!isNew && event && canManage && (
        <div className="bg-white shadow rounded-lg p-4">
          <h3 className="text-sm font-medium text-gray-900 mb-3">Event Status</h3>
          <div className="flex flex-wrap gap-2">
            {event.status === 'draft' && (
              <button
                onClick={() => handleStatusChange('publish')}
                className="inline-flex items-center px-3 py-1.5 border border-blue-300 text-sm font-medium rounded text-blue-700 bg-blue-50 hover:bg-blue-100"
              >
                <CalendarCheck className="h-4 w-4 mr-1" />
                Publish
              </button>
            )}
            {(event.status === 'draft' || event.status === 'scheduled') && (
              <>
                <button
                  onClick={() => handleStatusChange('start', false)}
                  className="inline-flex items-center px-3 py-1.5 border border-green-300 text-sm font-medium rounded text-green-700 bg-green-50 hover:bg-green-100"
                >
                  <Play className="h-4 w-4 mr-1" />
                  Start
                </button>
                {event.blueprint_id && event.participants.some(p => p.role === 'student') && (
                  <button
                    onClick={() => handleStatusChange('start', true)}
                    className="inline-flex items-center px-3 py-1.5 border border-primary-300 text-sm font-medium rounded text-primary-700 bg-primary-50 hover:bg-primary-100"
                  >
                    <Rocket className="h-4 w-4 mr-1" />
                    Start & Deploy Labs
                  </button>
                )}
              </>
            )}
            {event.status === 'running' && (
              <button
                onClick={() => handleStatusChange('complete')}
                className="inline-flex items-center px-3 py-1.5 border border-purple-300 text-sm font-medium rounded text-purple-700 bg-purple-50 hover:bg-purple-100"
              >
                <CheckCircle className="h-4 w-4 mr-1" />
                Complete
              </button>
            )}
            {event.status !== 'completed' && event.status !== 'cancelled' && (
              <button
                onClick={() => handleStatusChange('cancel')}
                className="inline-flex items-center px-3 py-1.5 border border-red-300 text-sm font-medium rounded text-red-700 bg-red-50 hover:bg-red-100"
              >
                <XCircle className="h-4 w-4 mr-1" />
                Cancel
              </button>
            )}
            {event.status === 'cancelled' && (
              <button
                onClick={() => handleStatusChange('reactivate')}
                className="inline-flex items-center px-3 py-1.5 border border-amber-300 text-sm font-medium rounded text-amber-700 bg-amber-50 hover:bg-amber-100"
              >
                <RotateCcw className="h-4 w-4 mr-1" />
                Reactivate
              </button>
            )}
          </div>
        </div>
      )}

      {/* Main Form */}
      <div className="bg-white shadow rounded-lg p-6 space-y-6">
        {/* Basic Info */}
        <div>
          <h3 className="text-sm font-medium text-gray-900 mb-4">Basic Information</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={!canManage}
                className="w-full border border-gray-300 rounded-md py-2 px-3 focus:ring-primary-500 focus:border-primary-500 disabled:bg-gray-100"
              />
            </div>
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                disabled={!canManage}
                rows={3}
                className="w-full border border-gray-300 rounded-md py-2 px-3 focus:ring-primary-500 focus:border-primary-500 disabled:bg-gray-100"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Organization</label>
              <input
                type="text"
                value={organization}
                onChange={(e) => setOrganization(e.target.value)}
                disabled={!canManage}
                placeholder="e.g., USMC, CYBERCOM"
                className="w-full border border-gray-300 rounded-md py-2 px-3 focus:ring-primary-500 focus:border-primary-500 disabled:bg-gray-100"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Location</label>
              <div className="relative">
                <MapPin className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <input
                  type="text"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  disabled={!canManage}
                  placeholder="e.g., Room 101, Virtual"
                  className="w-full pl-10 border border-gray-300 rounded-md py-2 px-3 focus:ring-primary-500 focus:border-primary-500 disabled:bg-gray-100"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Schedule */}
        <div className="border-t pt-6">
          <h3 className="text-sm font-medium text-gray-900 mb-4">Schedule</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Start Date/Time *</label>
              <div className="relative">
                <Calendar className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <input
                  type="datetime-local"
                  value={startDatetime}
                  onChange={(e) => setStartDatetime(e.target.value)}
                  disabled={!canManage}
                  className="w-full pl-10 border border-gray-300 rounded-md py-2 px-3 focus:ring-primary-500 focus:border-primary-500 disabled:bg-gray-100"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">End Date/Time</label>
              <div className="relative">
                <Clock className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <input
                  type="datetime-local"
                  value={endDatetime}
                  onChange={(e) => setEndDatetime(e.target.value)}
                  disabled={!canManage}
                  className="w-full pl-10 border border-gray-300 rounded-md py-2 px-3 focus:ring-primary-500 focus:border-primary-500 disabled:bg-gray-100"
                />
              </div>
            </div>
            <div className="flex items-center">
              <input
                type="checkbox"
                id="isAllDay"
                checked={isAllDay}
                onChange={(e) => setIsAllDay(e.target.checked)}
                disabled={!canManage}
                className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
              />
              <label htmlFor="isAllDay" className="ml-2 text-sm text-gray-700">
                All-day event
              </label>
            </div>
          </div>
        </div>

        {/* Blueprint & Content */}
        <div className="border-t pt-6">
          <h3 className="text-sm font-medium text-gray-900 mb-4">Lab & Content</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                <LayoutTemplate className="inline h-4 w-4 mr-1" />
                Range Blueprint
              </label>
              <select
                value={blueprintId}
                onChange={(e) => setBlueprintId(e.target.value)}
                disabled={!canManage}
                className="w-full border border-gray-300 rounded-md py-2 px-3 focus:ring-primary-500 focus:border-primary-500 disabled:bg-gray-100"
              >
                <option value="">No blueprint</option>
                {blueprints.map((bp) => (
                  <option key={bp.id} value={bp.id}>
                    {bp.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                <BookOpen className="inline h-4 w-4 mr-1" />
                Linked Content
              </label>
              <div className="border border-gray-200 rounded-md max-h-48 overflow-y-auto">
                {contentItems.length === 0 ? (
                  <p className="p-3 text-sm text-gray-500">No published content available</p>
                ) : (
                  contentItems.map((item) => (
                    <label
                      key={item.id}
                      className="flex items-center px-3 py-2 hover:bg-gray-50 cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={selectedContentIds.includes(item.id)}
                        onChange={() => handleToggleContent(item.id)}
                        disabled={!canManage}
                        className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                      />
                      <span className="ml-3 text-sm text-gray-700">{item.title}</span>
                      <span className="ml-2 text-xs text-gray-500 capitalize">
                        ({item.content_type.replace('_', ' ')})
                      </span>
                    </label>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Access Control */}
        <div className="border-t pt-6">
          <h3 className="text-sm font-medium text-gray-900 mb-4">Access Control</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Allowed Roles</label>
              <div className="flex flex-wrap gap-2">
                {['student', 'engineer', 'evaluator', 'admin'].map((role) => (
                  <button
                    key={role}
                    type="button"
                    onClick={() => handleToggleRole(role)}
                    disabled={!canManage}
                    className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
                      allowedRoles.includes(role)
                        ? 'bg-primary-100 text-primary-800'
                        : 'bg-gray-100 text-gray-600'
                    } ${canManage ? 'cursor-pointer hover:opacity-80' : 'cursor-not-allowed'}`}
                  >
                    {role}
                  </button>
                ))}
              </div>
              <p className="mt-1 text-xs text-gray-500">
                Leave empty to make event visible to all users
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Tags</label>
              <div className="flex gap-2 mb-2 flex-wrap">
                {tags.map((tag) => (
                  <span
                    key={tag}
                    className="inline-flex items-center px-2 py-1 rounded text-xs bg-gray-100 text-gray-700"
                  >
                    {tag}
                    {canManage && (
                      <button
                        onClick={() => setTags(tags.filter((t) => t !== tag))}
                        className="ml-1 hover:text-red-500"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    )}
                  </span>
                ))}
              </div>
              {canManage && (
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={tagInput}
                    onChange={(e) => setTagInput(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), handleAddTag())}
                    placeholder="Add tag..."
                    className="flex-1 border border-gray-300 rounded-md py-1 px-2 text-sm"
                  />
                  <button
                    onClick={handleAddTag}
                    className="px-3 py-1 border border-gray-300 rounded-md text-sm hover:bg-gray-50"
                  >
                    <Tag className="h-4 w-4" />
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Participants */}
      {!isNew && event && (
        <div className="bg-white shadow rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium text-gray-900">
              <Users className="inline h-4 w-4 mr-1" />
              Participants ({event.participants.length})
            </h3>
          </div>
          {canManage && (
            <div className="flex gap-2 mb-4">
              <select
                value={selectedUserId}
                onChange={(e) => setSelectedUserId(e.target.value)}
                className="flex-1 border border-gray-300 rounded-md py-2 px-3 text-sm"
              >
                <option value="">Select user...</option>
                {users
                  .filter((u) => !event.participants.some((p) => p.user_id === u.id))
                  .map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.username}
                    </option>
                  ))}
              </select>
              <select
                value={participantRole}
                onChange={(e) => setParticipantRole(e.target.value)}
                className="border border-gray-300 rounded-md py-2 px-3 text-sm"
              >
                <option value="student">Student</option>
                <option value="instructor">Instructor</option>
                <option value="evaluator">Evaluator</option>
                <option value="observer">Observer</option>
              </select>
              <button
                onClick={handleAddParticipant}
                disabled={!selectedUserId}
                className="inline-flex items-center px-3 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700 disabled:opacity-50"
              >
                <Plus className="h-4 w-4" />
              </button>
            </div>
          )}
          {event.participants.length === 0 ? (
            <p className="text-sm text-gray-500">No participants yet</p>
          ) : (
            <div className="divide-y divide-gray-100">
              {event.participants.map((p) => (
                <div key={p.id} className="flex items-center justify-between py-3">
                  <div className="flex items-center gap-3">
                    <div>
                      <span className="text-sm font-medium text-gray-900">{p.username}</span>
                      <span className="ml-2 text-xs text-gray-500 capitalize">{p.role}</span>
                    </div>
                    {/* Range Status Badge */}
                    {p.range_id && (
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                        p.range_status === 'running' ? 'bg-green-100 text-green-700' :
                        p.range_status === 'deploying' ? 'bg-yellow-100 text-yellow-700' :
                        p.range_status === 'error' ? 'bg-red-100 text-red-700' :
                        p.range_status === 'stopped' ? 'bg-gray-100 text-gray-700' :
                        'bg-blue-100 text-blue-700'
                      }`}>
                        {p.range_status === 'deploying' && (
                          <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                        )}
                        {p.range_status === 'running' && (
                          <Monitor className="h-3 w-3 mr-1" />
                        )}
                        {p.range_name || 'Lab'}
                        {p.range_status && ` (${p.range_status})`}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {/* Open Console Button */}
                    {p.range_id && p.range_status === 'running' && (
                      <a
                        href={`/ranges/${p.range_id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center px-2 py-1 text-xs font-medium text-primary-600 hover:text-primary-700 hover:bg-primary-50 rounded"
                      >
                        <ExternalLink className="h-3 w-3 mr-1" />
                        Open Lab
                      </a>
                    )}
                    {canManage && (
                      <button
                        onClick={() => handleRemoveParticipant(p.user_id)}
                        className="p-1 hover:bg-red-50 rounded text-red-500"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* VM Visibility Control - only show for running events with student participants */}
      {!isNew && event && event.status === 'running' && canManage && (
        <VMVisibilityControl
          event={event}
          canManage={canManage}
          onUpdate={() => loadEvent(id!)}
        />
      )}

      {/* Briefing Modal */}
      {showBriefing && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex items-center justify-center min-h-screen px-4">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75" onClick={() => setShowBriefing(false)} />
            <div className="relative bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[80vh] overflow-y-auto">
              <div className="sticky top-0 bg-white border-b px-6 py-4 flex items-center justify-between">
                <h3 className="text-lg font-medium text-gray-900">Event Briefing</h3>
                <button onClick={() => setShowBriefing(false)} className="p-1 hover:bg-gray-100 rounded">
                  <X className="h-5 w-5" />
                </button>
              </div>
              <div className="p-6 space-y-6">
                {briefingContent.length === 0 ? (
                  <p className="text-gray-500">No briefing content available for your role.</p>
                ) : (
                  briefingContent.map((item, idx) => (
                    <div key={idx}>
                      <h4 className="text-lg font-medium text-gray-900 mb-2">{item.title}</h4>
                      <div
                        className="prose prose-sm max-w-none"
                        dangerouslySetInnerHTML={{ __html: sanitizeHtml(item.html) }}
                      />
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
