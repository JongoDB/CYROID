// frontend/src/components/admin/CatalogSourcesTab.tsx
import { useEffect, useState } from 'react'
import {
  catalogApi,
  type CatalogSource,
  type CatalogSourceCreate,
  type CatalogSourceUpdate,
} from '../../services/api'
import { toast } from '../../stores/toastStore'
import {
  Loader2,
  Plus,
  Pencil,
  Trash2,
  RefreshCw,
  X,
  AlertCircle,
  CheckCircle2,
  Store,
  GitBranch,
} from 'lucide-react'
import clsx from 'clsx'
import { ConfirmDialog } from '../common/ConfirmDialog'

export default function CatalogSourcesTab() {
  const [sources, setSources] = useState<CatalogSource[]>([])
  const [loading, setLoading] = useState(true)
  const [syncingSourceId, setSyncingSourceId] = useState<string | null>(null)

  // Add/Edit modal
  const [showModal, setShowModal] = useState(false)
  const [editingSource, setEditingSource] = useState<CatalogSource | null>(null)
  const [form, setForm] = useState<CatalogSourceCreate>({
    name: '',
    source_type: 'git',
    url: '',
    branch: 'main',
    enabled: true,
  })
  const [submitting, setSubmitting] = useState(false)

  // Delete
  const [deleteConfirm, setDeleteConfirm] = useState<{
    source: CatalogSource | null
    isLoading: boolean
  }>({ source: null, isLoading: false })

  const fetchSources = async () => {
    setLoading(true)
    try {
      const res = await catalogApi.listSources()
      setSources(res.data)
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to load catalog sources')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchSources()
  }, [])

  const openAddModal = () => {
    setEditingSource(null)
    setForm({
      name: '',
      source_type: 'git',
      url: '',
      branch: 'main',
      enabled: true,
    })
    setShowModal(true)
  }

  const openEditModal = (source: CatalogSource) => {
    setEditingSource(source)
    setForm({
      name: source.name,
      source_type: source.source_type,
      url: source.url,
      branch: source.branch,
      enabled: source.enabled,
    })
    setShowModal(true)
  }

  const handleSave = async () => {
    setSubmitting(true)
    try {
      if (editingSource) {
        const update: CatalogSourceUpdate = {
          name: form.name,
          url: form.url,
          branch: form.branch,
          enabled: form.enabled,
        }
        await catalogApi.updateSource(editingSource.id, update)
        toast.success(`Updated source "${form.name}"`)
      } else {
        await catalogApi.createSource(form)
        toast.success(`Created source "${form.name}"`)
      }
      setShowModal(false)
      fetchSources()
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to save catalog source')
    } finally {
      setSubmitting(false)
    }
  }

  const handleSync = async (source: CatalogSource) => {
    setSyncingSourceId(source.id)
    try {
      await catalogApi.syncSource(source.id)
      toast.success(`Synced "${source.name}" successfully`)
      fetchSources()
    } catch (err: any) {
      toast.error(err.response?.data?.detail || `Failed to sync "${source.name}"`)
    } finally {
      setSyncingSourceId(null)
    }
  }

  const handleDelete = async () => {
    if (!deleteConfirm.source) return
    setDeleteConfirm((prev) => ({ ...prev, isLoading: true }))
    try {
      await catalogApi.deleteSource(deleteConfirm.source.id)
      toast.success(`Deleted source "${deleteConfirm.source.name}"`)
      setDeleteConfirm({ source: null, isLoading: false })
      fetchSources()
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to delete source')
      setDeleteConfirm({ source: null, isLoading: false })
    }
  }

  const getSyncStatusBadge = (source: CatalogSource) => {
    switch (source.sync_status) {
      case 'syncing':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
            <Loader2 className="h-3 w-3 mr-1 animate-spin" />
            Syncing
          </span>
        )
      case 'error':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800" title={source.error_message || 'Sync error'}>
            <AlertCircle className="h-3 w-3 mr-1" />
            Error
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
            <CheckCircle2 className="h-3 w-3 mr-1" />
            Idle
          </span>
        )
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-medium text-gray-900">Catalog Sources</h3>
          <p className="mt-1 text-sm text-gray-500">
            Manage external content sources for browsable training material.
          </p>
        </div>
        <button
          onClick={openAddModal}
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-primary-600 hover:bg-primary-700"
        >
          <Plus className="h-4 w-4 mr-2" />
          Add Source
        </button>
      </div>

      {/* Sources List */}
      {sources.length === 0 ? (
        <div className="text-center bg-white shadow rounded-lg p-8">
          <Store className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-4 text-lg font-medium text-gray-900">No Catalog Sources</h3>
          <p className="mt-2 text-sm text-gray-500 max-w-md mx-auto">
            Add a catalog source to make training content available for installation.
            The official CYROID catalog is available at:
          </p>
          <div className="mt-3 bg-gray-50 rounded-md p-3 max-w-lg mx-auto">
            <code className="text-sm text-gray-700">https://github.com/JongoDB/cyroid-catalog</code>
          </div>
          <div className="mt-6">
            <button
              onClick={openAddModal}
              className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700"
            >
              <Plus className="h-4 w-4 mr-2" />
              Add Catalog Source
            </button>
          </div>
        </div>
      ) : (
        <div className="bg-white shadow rounded-lg overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Source</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Branch</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Items</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Last Synced</th>
                <th className="relative px-6 py-3"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {sources.map((source) => (
                <tr key={source.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-gray-900">{source.name}</span>
                        {!source.enabled && (
                          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600">
                            Disabled
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-gray-500 font-mono truncate max-w-xs" title={source.url}>
                        {source.url}
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className="inline-flex items-center text-sm text-gray-700">
                      <GitBranch className="h-3.5 w-3.5 mr-1 text-gray-400" />
                      {source.branch}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {getSyncStatusBadge(source)}
                    {source.sync_status === 'error' && source.error_message && (
                      <p className="mt-1 text-xs text-red-600 truncate max-w-xs" title={source.error_message}>
                        {source.error_message}
                      </p>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                    {source.item_count}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {source.last_synced
                      ? new Date(source.last_synced).toLocaleString()
                      : 'Never'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => handleSync(source)}
                        disabled={syncingSourceId === source.id}
                        className="p-1.5 text-gray-400 hover:text-primary-600 disabled:opacity-50"
                        title="Sync now"
                      >
                        <RefreshCw className={clsx('h-4 w-4', syncingSourceId === source.id && 'animate-spin')} />
                      </button>
                      <button
                        onClick={() => openEditModal(source)}
                        className="p-1.5 text-gray-400 hover:text-primary-600"
                        title="Edit"
                      >
                        <Pencil className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => setDeleteConfirm({ source, isLoading: false })}
                        className="p-1.5 text-gray-400 hover:text-red-600"
                        title="Delete"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Add/Edit Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex items-center justify-center min-h-screen px-4">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75" onClick={() => setShowModal(false)} />
            <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full p-6">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-medium text-gray-900">
                  {editingSource ? 'Edit Catalog Source' : 'Add Catalog Source'}
                </h3>
                <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-600">
                  <X className="h-5 w-5" />
                </button>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700">Name</label>
                  <input
                    type="text"
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    placeholder="e.g., CYROID Official Catalog"
                    className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm px-3 py-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">Repository URL</label>
                  <input
                    type="text"
                    value={form.url}
                    onChange={(e) => setForm({ ...form, url: e.target.value })}
                    placeholder="https://github.com/JongoDB/cyroid-catalog"
                    className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm px-3 py-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Branch</label>
                    <input
                      type="text"
                      value={form.branch}
                      onChange={(e) => setForm({ ...form, branch: e.target.value })}
                      placeholder="main"
                      className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm px-3 py-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Type</label>
                    <select
                      value={form.source_type}
                      onChange={(e) => setForm({ ...form, source_type: e.target.value as any })}
                      className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm px-3 py-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
                    >
                      <option value="git">Git</option>
                      <option value="http">HTTP</option>
                      <option value="local">Local</option>
                    </select>
                  </div>
                </div>

                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="source-enabled"
                    checked={form.enabled}
                    onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
                    className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                  />
                  <label htmlFor="source-enabled" className="ml-2 text-sm text-gray-700">
                    Enabled (items appear in catalog browser)
                  </label>
                </div>
              </div>

              <div className="mt-6 flex justify-end gap-3">
                <button
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  disabled={submitting || !form.name || !form.url}
                  className="px-4 py-2 text-sm font-medium text-white bg-primary-600 border border-transparent rounded-md hover:bg-primary-700 disabled:opacity-50"
                >
                  {submitting ? 'Saving...' : (editingSource ? 'Save Changes' : 'Add Source')}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation */}
      <ConfirmDialog
        isOpen={deleteConfirm.source !== null}
        title="Delete Catalog Source"
        message={`Are you sure you want to delete "${deleteConfirm.source?.name}"? This will remove the source and all cached catalog data. Installed items will not be removed.`}
        confirmLabel="Delete"
        variant="danger"
        onConfirm={handleDelete}
        onCancel={() => setDeleteConfirm({ source: null, isLoading: false })}
        isLoading={deleteConfirm.isLoading}
      />
    </div>
  )
}
