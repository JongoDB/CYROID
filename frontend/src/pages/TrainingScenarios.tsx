// frontend/src/pages/TrainingScenarios.tsx
import { useEffect, useState, useRef } from 'react'
import { scenariosApi } from '../services/api'
import type { Scenario } from '../types'
import { Loader2, Target, Shield, UserX, Clock, Zap, AlertTriangle, Upload, RefreshCw, Trash2, FolderOpen } from 'lucide-react'
import clsx from 'clsx'
import { toast } from '../stores/toastStore'
import { ConfirmDialog } from '../components/common/ConfirmDialog'

const categoryConfig = {
  'red-team': {
    label: 'Red Team',
    icon: Target,
    color: 'text-red-600',
    bgColor: 'bg-red-100',
  },
  'blue-team': {
    label: 'Blue Team',
    icon: Shield,
    color: 'text-blue-600',
    bgColor: 'bg-blue-100',
  },
  'insider-threat': {
    label: 'Insider Threat',
    icon: UserX,
    color: 'text-yellow-600',
    bgColor: 'bg-yellow-100',
  },
}

const difficultyConfig = {
  beginner: { label: 'Beginner', color: 'bg-green-100 text-green-800' },
  intermediate: { label: 'Intermediate', color: 'bg-yellow-100 text-yellow-800' },
  advanced: { label: 'Advanced', color: 'bg-red-100 text-red-800' },
}

export default function TrainingScenarios() {
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [scenariosDir, setScenariosDir] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [categoryFilter, setCategoryFilter] = useState<string>('')
  const [searchQuery, setSearchQuery] = useState('')
  const [deleteConfirm, setDeleteConfirm] = useState<{ open: boolean; id: string; name: string }>({
    open: false,
    id: '',
    name: '',
  })
  const fileInputRef = useRef<HTMLInputElement>(null)

  const fetchScenarios = async () => {
    try {
      const response = await scenariosApi.list(categoryFilter || undefined)
      setScenarios(response.data.scenarios)
      setScenariosDir(response.data.scenarios_dir)
    } catch (err) {
      console.error('Failed to fetch scenarios:', err)
      toast.error('Failed to load scenarios')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchScenarios()
  }, [categoryFilter])

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploading(true)
    try {
      const response = await scenariosApi.upload(file, false)
      toast.success(`Uploaded scenario: ${response.data.name}`)
      fetchScenarios()
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'Failed to upload scenario'
      toast.error(detail)
    } finally {
      setUploading(false)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      const response = await scenariosApi.refresh()
      toast.success(`Refreshed: ${response.data.total} scenarios found`)
      fetchScenarios()
    } catch (err) {
      toast.error('Failed to refresh scenarios')
    } finally {
      setRefreshing(false)
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await scenariosApi.delete(id)
      toast.success('Scenario deleted')
      fetchScenarios()
    } catch (err) {
      toast.error('Failed to delete scenario')
    }
    setDeleteConfirm({ open: false, id: '', name: '' })
  }

  const filteredScenarios = scenarios.filter((s) =>
    s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    s.description.toLowerCase().includes(searchQuery.toLowerCase())
  )

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    )
  }

  return (
    <div>
      <div className="sm:flex sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Training Scenarios</h1>
          <p className="mt-2 text-sm text-gray-700">
            Pre-built cyber training scenarios ready to deploy to your ranges
          </p>
          {scenariosDir && (
            <p className="mt-1 text-xs text-gray-500 flex items-center">
              <FolderOpen className="h-3 w-3 mr-1" />
              {scenariosDir}
            </p>
          )}
        </div>
        <div className="mt-4 sm:mt-0 flex gap-2">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleUpload}
            accept=".yaml,.yml"
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
          >
            {uploading ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Upload className="h-4 w-4 mr-2" />
            )}
            Upload YAML
          </button>
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="inline-flex items-center px-3 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
            title="Refresh from filesystem"
          >
            <RefreshCw className={clsx("h-4 w-4", refreshing && "animate-spin")} />
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="mt-6 flex flex-col sm:flex-row gap-4">
        <input
          type="text"
          placeholder="Search scenarios..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="flex-1 rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
        />
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
        >
          <option value="">All Categories</option>
          <option value="red-team">Red Team</option>
          <option value="blue-team">Blue Team</option>
          <option value="insider-threat">Insider Threat</option>
        </select>
      </div>

      {filteredScenarios.length === 0 ? (
        <div className="mt-8 text-center">
          <AlertTriangle className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900">No scenarios found</h3>
          <p className="mt-1 text-sm text-gray-500">
            {searchQuery || categoryFilter
              ? 'Try adjusting your filters.'
              : 'Upload a YAML file or add scenarios to the scenarios directory.'}
          </p>
        </div>
      ) : (
        <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {filteredScenarios.map((scenario) => {
            const catConfig = categoryConfig[scenario.category] || categoryConfig['red-team']
            const diffConfig = difficultyConfig[scenario.difficulty] || difficultyConfig.intermediate
            const CategoryIcon = catConfig.icon

            return (
              <div
                key={scenario.id}
                className="bg-white rounded-lg shadow overflow-hidden hover:shadow-md transition-shadow"
              >
                <div className="p-5">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center">
                      <div className={clsx("flex-shrink-0 rounded-md p-2", catConfig.bgColor)}>
                        <CategoryIcon className={clsx("h-6 w-6", catConfig.color)} />
                      </div>
                      <div className="ml-3">
                        <h3 className="text-sm font-medium text-gray-900">{scenario.name}</h3>
                        <span className={clsx("inline-block mt-1 text-xs px-2 py-0.5 rounded", diffConfig.color)}>
                          {diffConfig.label}
                        </span>
                      </div>
                    </div>
                    <button
                      onClick={() => setDeleteConfirm({ open: true, id: scenario.id, name: scenario.name })}
                      className="text-gray-400 hover:text-red-500 p-1"
                      title="Delete scenario"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>

                  <p className="mt-3 text-sm text-gray-500 line-clamp-3">
                    {scenario.description}
                  </p>

                  <div className="mt-4 flex items-center text-xs text-gray-500 space-x-4">
                    <span className="flex items-center">
                      <Clock className="h-3.5 w-3.5 mr-1" />
                      {scenario.duration_minutes} min
                    </span>
                    <span className="flex items-center">
                      <Zap className="h-3.5 w-3.5 mr-1" />
                      {scenario.event_count} events
                    </span>
                  </div>

                  <div className="mt-3">
                    <p className="text-xs text-gray-400 mb-1">Required roles:</p>
                    <div className="flex flex-wrap gap-1">
                      {scenario.required_roles.map((role) => (
                        <span
                          key={role}
                          className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700"
                        >
                          {role}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="bg-gray-50 px-5 py-3">
                  <p className="text-xs text-gray-500">
                    Deploy this scenario from a Range's detail page
                  </p>
                </div>
              </div>
            )
          })}
        </div>
      )}

      <ConfirmDialog
        isOpen={deleteConfirm.open}
        onCancel={() => setDeleteConfirm({ open: false, id: '', name: '' })}
        onConfirm={() => handleDelete(deleteConfirm.id)}
        title="Delete Scenario"
        message={`Are you sure you want to delete "${deleteConfirm.name}"? This will remove the YAML file from the filesystem.`}
        confirmLabel="Delete"
        variant="danger"
      />
    </div>
  )
}
