// frontend/src/pages/Templates.tsx
import { useEffect, useState } from 'react'
import { templatesApi, cacheApi, VMTemplateCreate } from '../services/api'
import type { VMTemplate, CachedImage, WindowsVersionsResponse, CustomISOList, RecommendedImages, WindowsVersion, WindowsISODownloadStatus } from '../types'
import { Plus, Pencil, Trash2, Copy, Loader2, X, Server, Monitor, Info, RefreshCw, Tag, Download, Check } from 'lucide-react'
import clsx from 'clsx'

interface TemplateFormData {
  name: string
  description: string
  os_type: 'windows' | 'linux'
  os_variant: string
  base_image: string
  default_cpu: number
  default_ram_mb: number
  default_disk_gb: number
  config_script: string
  tags: string
}

const defaultFormData: TemplateFormData = {
  name: '',
  description: '',
  os_type: 'linux',
  os_variant: '',
  base_image: '',
  default_cpu: 2,
  default_ram_mb: 2048,
  default_disk_gb: 20,
  config_script: '',
  tags: ''
}

const WINDOWS_DEFAULTS = {
  default_cpu: 4,
  default_ram_mb: 8192,
  default_disk_gb: 64,
  base_image: 'dockur/windows'
}

export default function Templates() {
  const [templates, setTemplates] = useState<VMTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [editingTemplate, setEditingTemplate] = useState<VMTemplate | null>(null)
  const [formData, setFormData] = useState<TemplateFormData>(defaultFormData)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Cached data for dropdowns
  const [cachedImages, setCachedImages] = useState<CachedImage[]>([])
  const [windowsVersions, setWindowsVersions] = useState<WindowsVersionsResponse | null>(null)
  const [customISOs, setCustomISOs] = useState<CustomISOList | null>(null)
  const [recommendedImages, setRecommendedImages] = useState<RecommendedImages | null>(null)
  const [cacheLoading, setCacheLoading] = useState(false)

  // Visibility tags (ABAC)
  const [visibilityTags, setVisibilityTags] = useState<string[]>([])
  const [newVisibilityTag, setNewVisibilityTag] = useState('')
  const [visibilityTagsLoading, setVisibilityTagsLoading] = useState(false)

  // Windows ISO download state
  const [downloadingVersion, setDownloadingVersion] = useState<string | null>(null)
  const [downloadStatus, setDownloadStatus] = useState<WindowsISODownloadStatus | null>(null)

  const fetchTemplates = async () => {
    try {
      const response = await templatesApi.list()
      setTemplates(response.data)
    } catch (err) {
      console.error('Failed to fetch templates:', err)
    } finally {
      setLoading(false)
    }
  }

  const fetchCacheData = async () => {
    setCacheLoading(true)
    try {
      const [imagesRes, windowsRes, customISOsRes, recommendedRes] = await Promise.all([
        cacheApi.listImages(),
        cacheApi.getWindowsVersions(),
        cacheApi.listCustomISOs(),
        cacheApi.getRecommendedImages(),
      ])
      setCachedImages(imagesRes.data)
      setWindowsVersions(windowsRes.data)
      setCustomISOs(customISOsRes.data)
      setRecommendedImages(recommendedRes.data)
    } catch (err) {
      console.error('Failed to fetch cache data:', err)
    } finally {
      setCacheLoading(false)
    }
  }

  useEffect(() => {
    fetchTemplates()
    fetchCacheData()
  }, [])

  // Fetch visibility tags when editing a template
  const fetchVisibilityTags = async (templateId: string) => {
    setVisibilityTagsLoading(true)
    try {
      const response = await templatesApi.getTags(templateId)
      setVisibilityTags(response.data.tags)
    } catch (err) {
      console.error('Failed to fetch visibility tags:', err)
      setVisibilityTags([])
    } finally {
      setVisibilityTagsLoading(false)
    }
  }

  const handleAddVisibilityTag = async () => {
    if (!editingTemplate || !newVisibilityTag.trim()) return
    try {
      await templatesApi.addTag(editingTemplate.id, newVisibilityTag.trim())
      setVisibilityTags([...visibilityTags, newVisibilityTag.trim()])
      setNewVisibilityTag('')
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to add visibility tag')
    }
  }

  const handleRemoveVisibilityTag = async (tag: string) => {
    if (!editingTemplate) return
    try {
      await templatesApi.removeTag(editingTemplate.id, tag)
      setVisibilityTags(visibilityTags.filter(t => t !== tag))
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to remove visibility tag')
    }
  }

  // Windows ISO download
  const handleDownloadWindowsISO = async (version: string) => {
    setDownloadingVersion(version)
    setDownloadStatus(null)
    try {
      await cacheApi.downloadWindowsISO(version)
      // Poll for download status
      const pollInterval = setInterval(async () => {
        try {
          const statusRes = await cacheApi.getWindowsISODownloadStatus(version)
          setDownloadStatus(statusRes.data)
          if (statusRes.data.status === 'completed' || statusRes.data.status === 'failed') {
            clearInterval(pollInterval)
            setDownloadingVersion(null)
            if (statusRes.data.status === 'completed') {
              // Refresh cache data to update cached status
              fetchCacheData()
            }
          }
        } catch {
          clearInterval(pollInterval)
          setDownloadingVersion(null)
        }
      }, 2000)
    } catch (err: any) {
      setDownloadingVersion(null)
      alert(err.response?.data?.detail || 'Failed to start download')
    }
  }

  // Get selected Windows version info
  const getSelectedWindowsVersion = (): WindowsVersion | null => {
    if (!windowsVersions || !formData.os_variant) return null
    return windowsVersions.all.find(v => v.version === formData.os_variant) || null
  }

  const selectedWindowsVersion = getSelectedWindowsVersion()

  const openCreateModal = () => {
    setEditingTemplate(null)
    setFormData(defaultFormData)
    setVisibilityTags([])
    setNewVisibilityTag('')
    setError(null)
    setShowModal(true)
  }

  const openEditModal = (template: VMTemplate) => {
    setEditingTemplate(template)
    setFormData({
      name: template.name,
      description: template.description || '',
      os_type: template.os_type,
      os_variant: template.os_variant,
      base_image: template.base_image,
      default_cpu: template.default_cpu,
      default_ram_mb: template.default_ram_mb,
      default_disk_gb: template.default_disk_gb,
      config_script: template.config_script || '',
      tags: template.tags.join(', ')
    })
    setNewVisibilityTag('')
    setError(null)
    setShowModal(true)
    // Fetch visibility tags for this template
    fetchVisibilityTags(template.id)
  }

  const handleOsTypeChange = (newOsType: 'windows' | 'linux') => {
    if (newOsType === 'windows') {
      setFormData({
        ...formData,
        os_type: newOsType,
        os_variant: '11', // Default to Windows 11
        base_image: WINDOWS_DEFAULTS.base_image,
        default_cpu: WINDOWS_DEFAULTS.default_cpu,
        default_ram_mb: WINDOWS_DEFAULTS.default_ram_mb,
        default_disk_gb: WINDOWS_DEFAULTS.default_disk_gb,
      })
    } else {
      setFormData({
        ...formData,
        os_type: newOsType,
        os_variant: '',
        base_image: '',
        default_cpu: 2,
        default_ram_mb: 2048,
        default_disk_gb: 20,
      })
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)

    const data: VMTemplateCreate = {
      name: formData.name,
      description: formData.description || undefined,
      os_type: formData.os_type,
      os_variant: formData.os_variant,
      base_image: formData.base_image,
      default_cpu: formData.default_cpu,
      default_ram_mb: formData.default_ram_mb,
      default_disk_gb: formData.default_disk_gb,
      config_script: formData.config_script || undefined,
      tags: formData.tags ? formData.tags.split(',').map(t => t.trim()).filter(Boolean) : undefined
    }

    try {
      if (editingTemplate) {
        await templatesApi.update(editingTemplate.id, data)
      } else {
        await templatesApi.create(data)
      }
      setShowModal(false)
      fetchTemplates()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save template')
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async (template: VMTemplate) => {
    if (!confirm(`Are you sure you want to delete "${template.name}"?`)) return

    try {
      await templatesApi.delete(template.id)
      fetchTemplates()
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to delete template')
    }
  }

  const handleClone = async (template: VMTemplate) => {
    try {
      await templatesApi.clone(template.id)
      fetchTemplates()
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to clone template')
    }
  }

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
          <h1 className="text-2xl font-bold text-gray-900">VM Templates</h1>
          <p className="mt-2 text-sm text-gray-700">
            Create and manage VM templates for your cyber ranges
          </p>
        </div>
        <div className="mt-4 sm:mt-0">
          <button
            onClick={openCreateModal}
            className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
          >
            <Plus className="h-4 w-4 mr-2" />
            New Template
          </button>
        </div>
      </div>

      {templates.length === 0 ? (
        <div className="mt-8 text-center">
          <Server className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900">No templates</h3>
          <p className="mt-1 text-sm text-gray-500">Get started by creating a new VM template.</p>
          <div className="mt-6">
            <button
              onClick={openCreateModal}
              className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700"
            >
              <Plus className="h-4 w-4 mr-2" />
              New Template
            </button>
          </div>
        </div>
      ) : (
        <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {templates.map((template) => (
            <div
              key={template.id}
              className="bg-white overflow-hidden shadow rounded-lg"
            >
              <div className="p-5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center">
                    <div className={clsx(
                      "flex-shrink-0 rounded-md p-2",
                      template.os_type === 'linux' ? 'bg-orange-100' : 'bg-blue-100'
                    )}>
                      {template.os_type === 'linux' ? (
                        <Server className="h-6 w-6 text-orange-600" />
                      ) : (
                        <Monitor className="h-6 w-6 text-blue-600" />
                      )}
                    </div>
                    <div className="ml-4">
                      <h3 className="text-lg font-medium text-gray-900">{template.name}</h3>
                      <p className="text-sm text-gray-500">{template.os_variant}</p>
                    </div>
                  </div>
                </div>

                {template.description && (
                  <p className="mt-3 text-sm text-gray-600 line-clamp-2">{template.description}</p>
                )}

                <div className="mt-4 grid grid-cols-3 gap-2 text-center text-xs">
                  <div className="bg-gray-50 rounded p-2">
                    <div className="font-semibold text-gray-900">{template.default_cpu}</div>
                    <div className="text-gray-500">CPU</div>
                  </div>
                  <div className="bg-gray-50 rounded p-2">
                    <div className="font-semibold text-gray-900">{template.default_ram_mb / 1024}GB</div>
                    <div className="text-gray-500">RAM</div>
                  </div>
                  <div className="bg-gray-50 rounded p-2">
                    <div className="font-semibold text-gray-900">{template.default_disk_gb}GB</div>
                    <div className="text-gray-500">Disk</div>
                  </div>
                </div>

                {template.tags.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1">
                    {template.tags.map((tag) => (
                      <span
                        key={tag}
                        className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              <div className="bg-gray-50 px-5 py-3 flex justify-end space-x-2">
                <button
                  onClick={() => handleClone(template)}
                  className="p-2 text-gray-400 hover:text-gray-600"
                  title="Clone"
                >
                  <Copy className="h-4 w-4" />
                </button>
                <button
                  onClick={() => openEditModal(template)}
                  className="p-2 text-gray-400 hover:text-primary-600"
                  title="Edit"
                >
                  <Pencil className="h-4 w-4" />
                </button>
                <button
                  onClick={() => handleDelete(template)}
                  className="p-2 text-gray-400 hover:text-red-600"
                  title="Delete"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex items-center justify-center min-h-screen px-4">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75" onClick={() => setShowModal(false)} />

            <div className="relative bg-white rounded-lg shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
              <div className="flex items-center justify-between p-4 border-b sticky top-0 bg-white z-10">
                <h3 className="text-lg font-medium text-gray-900">
                  {editingTemplate ? 'Edit Template' : 'Create Template'}
                </h3>
                <div className="flex items-center space-x-2">
                  <button
                    type="button"
                    onClick={fetchCacheData}
                    disabled={cacheLoading}
                    className="p-1 text-gray-400 hover:text-gray-600"
                    title="Refresh cache data"
                  >
                    <RefreshCw className={clsx("h-4 w-4", cacheLoading && "animate-spin")} />
                  </button>
                  <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-500">
                    <X className="h-5 w-5" />
                  </button>
                </div>
              </div>

              <form onSubmit={handleSubmit} className="p-4 space-y-4">
                {error && (
                  <div className="p-3 bg-red-50 text-red-700 rounded-md text-sm">{error}</div>
                )}

                <div>
                  <label className="block text-sm font-medium text-gray-700">Name</label>
                  <input
                    type="text"
                    required
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">Description</label>
                  <textarea
                    rows={2}
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                  />
                </div>

                {/* OS Type Selection */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Operating System</label>
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      type="button"
                      onClick={() => handleOsTypeChange('linux')}
                      className={clsx(
                        "flex items-center justify-center p-3 border-2 rounded-lg transition-all",
                        formData.os_type === 'linux'
                          ? "border-orange-500 bg-orange-50 text-orange-700"
                          : "border-gray-200 hover:border-gray-300"
                      )}
                    >
                      <Server className="h-5 w-5 mr-2" />
                      <span className="font-medium">Linux</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => handleOsTypeChange('windows')}
                      className={clsx(
                        "flex items-center justify-center p-3 border-2 rounded-lg transition-all",
                        formData.os_type === 'windows'
                          ? "border-blue-500 bg-blue-50 text-blue-700"
                          : "border-gray-200 hover:border-gray-300"
                      )}
                    >
                      <Monitor className="h-5 w-5 mr-2" />
                      <span className="font-medium">Windows</span>
                    </button>
                  </div>
                </div>

                {/* Linux-specific fields */}
                {formData.os_type === 'linux' && (
                  <>
                    <div>
                      <label className="block text-sm font-medium text-gray-700">
                        Base Image
                        {cachedImages.length > 0 && (
                          <span className="ml-2 text-xs text-green-600">({cachedImages.length} cached)</span>
                        )}
                      </label>
                      <select
                        required
                        value={formData.base_image}
                        onChange={(e) => {
                          const img = e.target.value
                          // Auto-fill os_variant from image name
                          const variant = img.split(':')[0].split('/').pop() || img
                          setFormData({
                            ...formData,
                            base_image: img,
                            os_variant: formData.os_variant || variant
                          })
                        }}
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                      >
                        <option value="">Select an image...</option>
                        {cachedImages.length > 0 && (
                          <optgroup label="Cached Images">
                            {cachedImages.map(img =>
                              img.tags.filter(tag => !tag.includes('windows')).map(tag => (
                                <option key={tag} value={tag}>{tag} ({img.size_gb} GB)</option>
                              ))
                            )}
                          </optgroup>
                        )}
                        {recommendedImages && (
                          <>
                            <optgroup label="Recommended Linux">
                              {recommendedImages.linux.map(rec => (
                                <option key={rec.image} value={rec.image!}>
                                  {rec.image} - {rec.description}
                                </option>
                              ))}
                            </optgroup>
                            <optgroup label="Services">
                              {recommendedImages.services.map(rec => (
                                <option key={rec.image} value={rec.image!}>
                                  {rec.image} - {rec.description}
                                </option>
                              ))}
                            </optgroup>
                          </>
                        )}
                      </select>
                      <p className="mt-1 text-xs text-gray-500">
                        Select from cached images or recommended images. Non-cached images will be pulled on first use.
                      </p>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700">OS Variant Name</label>
                      <input
                        type="text"
                        required
                        placeholder="e.g., Ubuntu 22.04, Debian 12"
                        value={formData.os_variant}
                        onChange={(e) => setFormData({ ...formData, os_variant: e.target.value })}
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                      />
                    </div>
                  </>
                )}

                {/* Windows-specific fields */}
                {formData.os_type === 'windows' && windowsVersions && (
                  <>
                    <div className="bg-blue-50 border border-blue-200 rounded-md p-3">
                      <div className="flex">
                        <Info className="h-4 w-4 text-blue-500 mt-0.5 mr-2" />
                        <p className="text-xs text-blue-700">
                          Windows VMs use <strong>dockur/windows</strong> container.
                          {windowsVersions.cached_count > 0
                            ? ` ${windowsVersions.cached_count} ISO(s) cached locally for faster VM creation.`
                            : ' Download an ISO to cache for faster VM creation.'}
                        </p>
                      </div>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700">Windows Version</label>
                      <select
                        required
                        value={formData.os_variant}
                        onChange={(e) => {
                          setFormData({
                            ...formData,
                            os_variant: e.target.value,
                            base_image: 'dockur/windows'
                          })
                        }}
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                      >
                        <option value="">Select a Windows version...</option>
                        {/* Cached versions first */}
                        {windowsVersions.all.some(v => v.cached) && (
                          <optgroup label="Cached (Ready to Use)">
                            {windowsVersions.all.filter(v => v.cached).map(v => (
                              <option key={v.version} value={v.version}>
                                {v.name} ({v.version}) - {v.size_gb} GB ✓
                              </option>
                            ))}
                          </optgroup>
                        )}
                        <optgroup label="Desktop (Download Required)">
                          {windowsVersions.desktop.filter(v => !v.cached).map(v => (
                            <option key={v.version} value={v.version}>
                              {v.name} ({v.version}) - {v.size_gb} GB
                            </option>
                          ))}
                        </optgroup>
                        <optgroup label="Server (Download Required)">
                          {windowsVersions.server.filter(v => !v.cached).map(v => (
                            <option key={v.version} value={v.version}>
                              {v.name} ({v.version}) - {v.size_gb} GB
                            </option>
                          ))}
                        </optgroup>
                        <optgroup label="Legacy (Download Required)">
                          {windowsVersions.legacy.filter(v => !v.cached).map(v => (
                            <option key={v.version} value={v.version}>
                              {v.name} ({v.version}) - {v.size_gb} GB
                            </option>
                          ))}
                        </optgroup>
                      </select>
                    </div>

                    {/* Download prompt for non-cached versions */}
                    {selectedWindowsVersion && !selectedWindowsVersion.cached && (
                      <div className="bg-amber-50 border border-amber-200 rounded-md p-3">
                        <p className="text-sm text-amber-800 mb-2">
                          <strong>{selectedWindowsVersion.name}</strong> is not cached locally.
                          Download it first to create templates with this version.
                        </p>
                        {downloadingVersion === selectedWindowsVersion.version ? (
                          <div className="space-y-2">
                            <div className="flex items-center gap-2 text-sm text-amber-700">
                              <Loader2 className="h-4 w-4 animate-spin" />
                              <span>
                                {downloadStatus?.progress_percent
                                  ? `Downloading... ${downloadStatus.progress_percent}%`
                                  : downloadStatus?.progress_gb
                                    ? `Downloading... ${downloadStatus.progress_gb} GB`
                                    : 'Starting download...'}
                              </span>
                            </div>
                            {downloadStatus?.total_bytes && downloadStatus?.progress_bytes && (
                              <div className="w-full bg-amber-200 rounded-full h-2">
                                <div
                                  className="bg-amber-600 h-2 rounded-full transition-all duration-300"
                                  style={{ width: `${(downloadStatus.progress_bytes / downloadStatus.total_bytes) * 100}%` }}
                                />
                              </div>
                            )}
                          </div>
                        ) : (
                          <button
                            type="button"
                            onClick={() => handleDownloadWindowsISO(selectedWindowsVersion.version)}
                            className="inline-flex items-center px-3 py-1.5 border border-amber-300 rounded-md text-sm font-medium text-amber-800 bg-amber-100 hover:bg-amber-200"
                          >
                            <Download className="h-4 w-4 mr-2" />
                            Download and Cache ({selectedWindowsVersion.size_gb} GB)
                          </button>
                        )}
                      </div>
                    )}

                    {/* Show cached confirmation */}
                    {selectedWindowsVersion && selectedWindowsVersion.cached && (
                      <div className="bg-green-50 border border-green-200 rounded-md p-3">
                        <div className="flex items-center gap-2 text-sm text-green-700">
                          <Check className="h-4 w-4" />
                          <span><strong>{selectedWindowsVersion.name}</strong> is cached and ready to use.</span>
                        </div>
                      </div>
                    )}

                    {/* Custom ISO option */}
                    {customISOs && customISOs.isos.length > 0 && (
                      <div className="bg-gray-50 border border-gray-200 rounded-md p-3">
                        <p className="text-xs text-gray-600 mb-2">
                          <strong>Custom ISO available:</strong> You can also use a custom ISO when creating VMs
                          from this template. {customISOs.total_count} custom ISO(s) in cache.
                        </p>
                      </div>
                    )}
                  </>
                )}

                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">CPU Cores</label>
                    <input
                      type="number"
                      min={1}
                      max={32}
                      value={formData.default_cpu}
                      onChange={(e) => setFormData({ ...formData, default_cpu: parseInt(e.target.value) })}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700">RAM (MB)</label>
                    <input
                      type="number"
                      min={512}
                      step={512}
                      value={formData.default_ram_mb}
                      onChange={(e) => setFormData({ ...formData, default_ram_mb: parseInt(e.target.value) })}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700">Disk (GB)</label>
                    <input
                      type="number"
                      min={5}
                      value={formData.default_disk_gb}
                      onChange={(e) => setFormData({ ...formData, default_disk_gb: parseInt(e.target.value) })}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">Config Script (optional)</label>
                  <textarea
                    rows={3}
                    placeholder="#!/bin/bash&#10;# Initialization script"
                    value={formData.config_script}
                    onChange={(e) => setFormData({ ...formData, config_script: e.target.value })}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm font-mono text-xs"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">Tags (comma-separated)</label>
                  <input
                    type="text"
                    placeholder="e.g., web, database, production"
                    value={formData.tags}
                    onChange={(e) => setFormData({ ...formData, tags: e.target.value })}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                  />
                  <p className="mt-1 text-xs text-gray-500">
                    Organizational tags for categorizing templates.
                  </p>
                </div>

                {/* Visibility Tags (ABAC) - Only show when editing */}
                {editingTemplate && (
                  <div className="border-t border-gray-200 pt-4">
                    <div className="flex items-center gap-2 mb-2">
                      <Tag className="h-4 w-4 text-gray-500" />
                      <label className="text-sm font-medium text-gray-700">Visibility Tags (Access Control)</label>
                    </div>
                    <p className="text-xs text-gray-500 mb-3">
                      Control who can see this template. Users must have at least one matching tag to view.
                      Templates with no visibility tags are visible to all users.
                    </p>

                    {visibilityTagsLoading ? (
                      <div className="flex items-center gap-2 text-sm text-gray-500">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        <span>Loading visibility tags...</span>
                      </div>
                    ) : (
                      <>
                        {/* Current visibility tags */}
                        {visibilityTags.length > 0 ? (
                          <div className="flex flex-wrap gap-2 mb-3">
                            {visibilityTags.map((tag) => (
                              <span
                                key={tag}
                                className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-800"
                              >
                                {tag}
                                <button
                                  type="button"
                                  onClick={() => handleRemoveVisibilityTag(tag)}
                                  className="ml-1.5 text-purple-600 hover:text-purple-800"
                                >
                                  <X className="h-3 w-3" />
                                </button>
                              </span>
                            ))}
                          </div>
                        ) : (
                          <p className="text-sm text-gray-500 italic mb-3">
                            No visibility tags - template is visible to all users.
                          </p>
                        )}

                        {/* Add new visibility tag */}
                        <div className="flex gap-2">
                          <input
                            type="text"
                            placeholder="Add visibility tag..."
                            value={newVisibilityTag}
                            onChange={(e) => setNewVisibilityTag(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') {
                                e.preventDefault()
                                handleAddVisibilityTag()
                              }
                            }}
                            className="flex-1 rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                          />
                          <button
                            type="button"
                            onClick={handleAddVisibilityTag}
                            disabled={!newVisibilityTag.trim()}
                            className="px-3 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
                          >
                            Add
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                )}

                <div className="flex justify-end space-x-3 pt-4">
                  <button
                    type="button"
                    onClick={() => setShowModal(false)}
                    className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={submitting || (formData.os_type === 'windows' && selectedWindowsVersion && !selectedWindowsVersion.cached)}
                    className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 disabled:opacity-50"
                    title={formData.os_type === 'windows' && selectedWindowsVersion && !selectedWindowsVersion.cached
                      ? 'Download the Windows ISO first'
                      : undefined}
                  >
                    {submitting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                    {editingTemplate ? 'Update' : 'Create'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
