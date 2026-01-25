// frontend/src/components/range/TrainingTab.tsx
import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { BookOpen, Plus, ExternalLink, Loader2, Check, AlertCircle } from 'lucide-react'
import { contentApi, rangesApi, ContentListItem } from '../../services/api'
import { toast } from '../../stores/toastStore'
import { RangeVMVisibilityControl } from '../ranges/RangeVMVisibilityControl'

interface TrainingTabProps {
  rangeId: string
  studentGuideId: string | null
  canManage?: boolean
  onUpdate: () => void
}

export function TrainingTab({ rangeId, studentGuideId, canManage = true, onUpdate }: TrainingTabProps) {
  const [guides, setGuides] = useState<ContentListItem[]>([])
  const [selectedGuideId, setSelectedGuideId] = useState<string | null>(studentGuideId)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadGuides()
  }, [])

  useEffect(() => {
    setSelectedGuideId(studentGuideId)
  }, [studentGuideId])

  async function loadGuides() {
    setLoading(true)
    setError(null)
    try {
      const response = await contentApi.listStudentGuides()
      setGuides(response.data)
    } catch (err) {
      setError('Failed to load student guides')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  async function handleSave() {
    setSaving(true)
    try {
      await rangesApi.setStudentGuide(rangeId, selectedGuideId)
      onUpdate()
      toast.success('Student guide updated')
    } catch (err) {
      toast.error('Failed to update student guide')
      console.error(err)
    } finally {
      setSaving(false)
    }
  }

  const hasChanges = selectedGuideId !== studentGuideId
  const selectedGuide = guides.find(g => g.id === selectedGuideId)

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h3 className="text-lg font-medium text-gray-900 flex items-center gap-2">
          <BookOpen className="w-5 h-5 text-primary-600" />
          Student Lab Guide
        </h3>
        <p className="text-sm text-gray-500 mt-1">
          Select content from the Content Library to display in the Student Lab view.
          Students will see this guide when they click "Open Lab".
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
          <span className="text-red-700">{error}</span>
        </div>
      )}

      {/* Guide Selector */}
      <div className="max-w-md">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Student Guide
        </label>
        {loading ? (
          <div className="flex items-center gap-2 text-gray-500">
            <Loader2 className="w-4 h-4 animate-spin" />
            Loading guides...
          </div>
        ) : (
          <select
            value={selectedGuideId || ''}
            onChange={(e) => setSelectedGuideId(e.target.value || null)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          >
            <option value="">None selected</option>
            {guides.map(guide => (
              <option key={guide.id} value={guide.id}>
                {guide.title} (v{guide.version})
              </option>
            ))}
          </select>
        )}

        {guides.length === 0 && !loading && (
          <p className="text-sm text-gray-500 mt-2">
            No published student guides available.{' '}
            <Link to="/content/new?type=student_guide" className="text-primary-600 hover:underline">
              Create one
            </Link>
          </p>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-4">
        <button
          onClick={handleSave}
          disabled={!hasChanges || saving}
          className="inline-flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {saving ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Saving...
            </>
          ) : (
            <>
              <Check className="w-4 h-4 mr-2" />
              Save
            </>
          )}
        </button>

        <Link
          to="/content/new?type=student_guide"
          className="inline-flex items-center text-primary-600 hover:text-primary-700 text-sm"
        >
          <Plus className="w-4 h-4 mr-1" />
          Create new guide
        </Link>

        {selectedGuideId && (
          <Link
            to={`/content/${selectedGuideId}`}
            className="inline-flex items-center text-gray-600 hover:text-gray-700 text-sm"
          >
            <ExternalLink className="w-4 h-4 mr-1" />
            Edit selected guide
          </Link>
        )}
      </div>

      {/* Selected Guide Preview */}
      {selectedGuide && (
        <div className="border rounded-lg bg-gray-50 p-4 mt-6">
          <h4 className="font-medium text-gray-900 mb-2">Selected Guide</h4>
          <div className="space-y-2 text-sm">
            <p>
              <span className="text-gray-500">Title:</span>{' '}
              <span className="font-medium">{selectedGuide.title}</span>
            </p>
            {selectedGuide.description && (
              <p>
                <span className="text-gray-500">Description:</span>{' '}
                {selectedGuide.description}
              </p>
            )}
            <p>
              <span className="text-gray-500">Version:</span> {selectedGuide.version}
            </p>
            {selectedGuide.tags.length > 0 && (
              <div className="flex items-center gap-2">
                <span className="text-gray-500">Tags:</span>
                <div className="flex gap-1">
                  {selectedGuide.tags.map(tag => (
                    <span
                      key={tag}
                      className="px-2 py-0.5 bg-gray-200 text-gray-700 rounded text-xs"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Info Box */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mt-6">
        <h4 className="font-medium text-blue-900 mb-1">How it works</h4>
        <ul className="text-sm text-blue-700 space-y-1 list-disc list-inside">
          <li>Create training content in the <Link to="/content" className="underline">Content Library</Link></li>
          <li>Use the "Student Guide" content type for lab walkthroughs</li>
          <li>Publish the content when it's ready for students</li>
          <li>Select the published guide here to link it to this range</li>
          <li>Students see the guide in the left panel when they "Open Lab"</li>
        </ul>
      </div>

      {/* VM Console Visibility */}
      <div className="mt-6">
        <RangeVMVisibilityControl
          rangeId={rangeId}
          canManage={canManage}
          onUpdate={onUpdate}
        />
      </div>
    </div>
  )
}
