// frontend/src/pages/VMLibrary.tsx
import { useEffect, useState } from 'react'
import { templatesApi, cacheApi, VMTemplateCreate } from '../services/api'
import type { VMTemplate, CachedImage, WindowsVersionsResponse, LinuxVersionsResponse, CustomISOList, RecommendedImages } from '../types'
import { Plus, Pencil, Trash2, Copy, Loader2, X, Server, Monitor, Info, RefreshCw, Tag, LayoutGrid, List, Disc, Camera, HardDrive } from 'lucide-react'
import clsx from 'clsx'
import { ConfirmDialog } from '../components/common/ConfirmDialog'
import { toast } from '../stores/toastStore'

// Tab type for the VM Library
type VMLibraryTab = 'snapshots' | 'base-images'

// Core CYROID service images to exclude from the dropdown
const CYROID_SERVICE_IMAGES = [
  'postgres',
  'redis',
  'minio',
  'traefik',
  'cyroid-api',
  'cyroid-frontend',
  'cyroid-worker',
]

interface TemplateFormData {
  name: string
  description: string
  os_type: 'windows' | 'linux' | 'custom' | 'network'
  os_variant: string
  base_image: string
  default_cpu: number
  default_ram_mb: number
  default_disk_gb: number
  config_script: string
  tags: string
  custom_iso: string  // For custom ISO selection
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
  tags: '',
  custom_iso: ''
}

const CUSTOM_DEFAULTS = {
  default_cpu: 2,
  default_ram_mb: 4096,
  default_disk_gb: 32,
  base_image: 'qemux/qemu'  // Use qemu for custom ISOs
}

const WINDOWS_DEFAULTS = {
  default_cpu: 4,
  default_ram_mb: 8192,
  default_disk_gb: 64,
  base_image: 'dockur/windows'
}

export default function VMLibrary() {
  // Tab state - default to 'snapshots'
  const [activeTab, setActiveTab] = useState<VMLibraryTab>('snapshots')

  const [templates, setTemplates] = useState<VMTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [viewMode, setViewMode] = useState<'tile' | 'list'>('tile')
  const [showModal, setShowModal] = useState(false)
  const [editingTemplate, setEditingTemplate] = useState<VMTemplate | null>(null)
  const [formData, setFormData] = useState<TemplateFormData>(defaultFormData)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Cached data for dropdowns
  const [cachedImages, setCachedImages] = useState<CachedImage[]>([])
  const [windowsVersions, setWindowsVersions] = useState<WindowsVersionsResponse | null>(null)
  const [linuxVersions, setLinuxVersions] = useState<LinuxVersionsResponse | null>(null)
  const [customISOs, setCustomISOs] = useState<CustomISOList | null>(null)
  const [recommendedImages, setRecommendedImages] = useState<RecommendedImages | null>(null)
  const [cacheLoading, setCacheLoading] = useState(false)

  // Visibility tags (ABAC)
  const [visibilityTags, setVisibilityTags] = useState<string[]>([])
  const [newVisibilityTag, setNewVisibilityTag] = useState('')
  const [visibilityTagsLoading, setVisibilityTagsLoading] = useState(false)

  // Delete confirmation
  const [deleteConfirm, setDeleteConfirm] = useState<{
    template: VMTemplate | null
    isLoading: boolean
  }>({ template: null, isLoading: false })


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
      const [imagesRes, windowsRes, linuxRes, customISOsRes, recommendedRes] = await Promise.all([
        cacheApi.listImages(),
        cacheApi.getWindowsVersions(),
        cacheApi.getLinuxVersions(),
        cacheApi.listCustomISOs(),
        cacheApi.getRecommendedImages(),
      ])
      setCachedImages(imagesRes.data)
      setWindowsVersions(windowsRes.data)
      setLinuxVersions(linuxRes.data)
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

  // Helper to filter out CYROID service images
  const filterServiceImages = (images: CachedImage[]): CachedImage[] => {
    return images.filter(img => {
      const isServiceImage = img.tags.some(tag =>
        CYROID_SERVICE_IMAGES.some(service =>
          tag.toLowerCase().includes(service.toLowerCase())
        )
      )
      return !isServiceImage
    })
  }

  const filteredCachedImages = filterServiceImages(cachedImages)

  // Helper to get human-readable name for a cached container image
  const getContainerImageName = (tag: string): string => {
    if (!recommendedImages) return tag
    // Search all categories for matching image
    const allImages = [
      ...(recommendedImages.desktop || []),
      ...(recommendedImages.server || []),
      ...(recommendedImages.services || []),
    ]
    const match = allImages.find(img => img.image === tag)
    return match?.name || tag
  }

  // Helper to get the category of a cached container image
  const getContainerImageCategory = (tag: string): 'desktop' | 'server' | 'services' | null => {
    if (!recommendedImages) return null
    if (recommendedImages.desktop?.some(img => img.image === tag)) return 'desktop'
    if (recommendedImages.server?.some(img => img.image === tag)) return 'server'
    if (recommendedImages.services?.some(img => img.image === tag)) return 'services'
    return null
  }

  // Get cached container images by category
  const getCachedContainersByCategory = (category: 'desktop' | 'server' | 'services') => {
    return filteredCachedImages.flatMap(img =>
      img.tags.filter(tag => !tag.includes('windows') && getContainerImageCategory(tag) === category)
        .map(tag => ({ tag, size_gb: img.size_gb }))
    )
  }

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
      tags: template.tags.join(', '),
      custom_iso: ''  // Will be populated if editing a custom template
    })
    setNewVisibilityTag('')
    setError(null)
    setShowModal(true)
    // Fetch visibility tags for this template
    fetchVisibilityTags(template.id)
  }

  const handleOsTypeChange = (newOsType: 'windows' | 'linux' | 'custom') => {
    if (newOsType === 'windows') {
      setFormData({
        ...formData,
        os_type: newOsType,
        os_variant: '11', // Default to Windows 11
        base_image: WINDOWS_DEFAULTS.base_image,
        default_cpu: WINDOWS_DEFAULTS.default_cpu,
        default_ram_mb: WINDOWS_DEFAULTS.default_ram_mb,
        default_disk_gb: WINDOWS_DEFAULTS.default_disk_gb,
        custom_iso: '',
      })
    } else if (newOsType === 'custom') {
      setFormData({
        ...formData,
        os_type: newOsType,
        os_variant: '',
        base_image: CUSTOM_DEFAULTS.base_image,
        default_cpu: CUSTOM_DEFAULTS.default_cpu,
        default_ram_mb: CUSTOM_DEFAULTS.default_ram_mb,
        default_disk_gb: CUSTOM_DEFAULTS.default_disk_gb,
        custom_iso: '',
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
        custom_iso: '',
      })
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)

    // For custom ISOs, find the path from the selected ISO
    let cachedIsoPath: string | undefined
    if (formData.os_type === 'custom' && formData.custom_iso && customISOs) {
      const selectedIso = customISOs.isos.find(iso => iso.filename === formData.custom_iso)
      cachedIsoPath = selectedIso?.path
    }

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
      tags: formData.tags ? formData.tags.split(',').map(t => t.trim()).filter(Boolean) : undefined,
      cached_iso_path: cachedIsoPath
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

  const handleDelete = (template: VMTemplate) => {
    setDeleteConfirm({ template, isLoading: false })
  }

  const confirmDelete = async () => {
    if (!deleteConfirm.template) return
    setDeleteConfirm(prev => ({ ...prev, isLoading: true }))
    try {
      await templatesApi.delete(deleteConfirm.template.id)
      setDeleteConfirm({ template: null, isLoading: false })
      fetchTemplates()
    } catch (err: any) {
      setDeleteConfirm({ template: null, isLoading: false })
      toast.error(err.response?.data?.detail || 'Failed to delete template')
    }
  }

  const handleClone = async (template: VMTemplate) => {
    try {
      await templatesApi.clone(template.id)
      fetchTemplates()
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to clone template')
    }
  }

  // Render the Snapshots tab content
  const renderSnapshotsTab = () => {
    return (
      <div className="mt-6">
        <div className="bg-white shadow rounded-lg p-8 text-center">
          <Camera className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-4 text-lg font-medium text-gray-900">Snapshots</h3>
          <p className="mt-2 text-sm text-gray-500 max-w-md mx-auto">
            Snapshots allow you to capture the state of a running VM and restore it later.
            This feature will be implemented in a future update.
          </p>
          <div className="mt-6 bg-gray-50 rounded-lg p-4 max-w-lg mx-auto">
            <h4 className="text-sm font-medium text-gray-700 mb-2">Planned Features:</h4>
            <ul className="text-sm text-gray-600 text-left list-disc list-inside space-y-1">
              <li>Create snapshots from running or stopped VMs</li>
              <li>Restore VMs to previous snapshot states</li>
              <li>Create VM templates from snapshots</li>
              <li>Export snapshots for backup or sharing</li>
              <li>Golden image management for rapid deployment</li>
            </ul>
          </div>
        </div>
      </div>
    )
  }

  // Render the Base OS Images tab content (existing template list)
  const renderBaseImagesTab = () => {
    if (loading) {
      return (
        <div className="flex items-center justify-center h-64">
          <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
        </div>
      )
    }

    return (
      <>
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
        ) : viewMode === 'tile' ? (
          /* Tile View */
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
        ) : (
          /* List View */
          <div className="mt-8 bg-white shadow rounded-lg overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Template
                  </th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    OS
                  </th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Resources
                  </th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Tags
                  </th>
                  <th scope="col" className="relative px-6 py-3">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {templates.map((template) => (
                  <tr key={template.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <div className={clsx(
                          "flex-shrink-0 rounded-md p-2",
                          template.os_type === 'linux' ? 'bg-orange-100' : 'bg-blue-100'
                        )}>
                          {template.os_type === 'linux' ? (
                            <Server className="h-5 w-5 text-orange-600" />
                          ) : (
                            <Monitor className="h-5 w-5 text-blue-600" />
                          )}
                        </div>
                        <div className="ml-4">
                          <div className="text-sm font-medium text-gray-900">{template.name}</div>
                          {template.description && (
                            <div className="text-sm text-gray-500 truncate max-w-xs">{template.description}</div>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-900">{template.os_variant}</div>
                      <div className="text-xs text-gray-500 capitalize">{template.os_type}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      <div className="flex items-center space-x-4">
                        <span>{template.default_cpu} CPU</span>
                        <span>{template.default_ram_mb / 1024} GB RAM</span>
                        <span>{template.default_disk_gb} GB Disk</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {template.tags.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {template.tags.slice(0, 3).map((tag) => (
                            <span
                              key={tag}
                              className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800"
                            >
                              {tag}
                            </span>
                          ))}
                          {template.tags.length > 3 && (
                            <span className="text-xs text-gray-500">+{template.tags.length - 3}</span>
                          )}
                        </div>
                      ) : (
                        <span className="text-gray-400 text-sm">-</span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <div className="flex justify-end space-x-2">
                        <button
                          onClick={() => handleClone(template)}
                          className="p-1.5 text-gray-400 hover:text-gray-600 rounded"
                          title="Clone"
                        >
                          <Copy className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => openEditModal(template)}
                          className="p-1.5 text-gray-400 hover:text-primary-600 rounded"
                          title="Edit"
                        >
                          <Pencil className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => handleDelete(template)}
                          className="p-1.5 text-gray-400 hover:text-red-600 rounded"
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
      </>
    )
  }

  return (
    <div>
      <div className="sm:flex sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">VM Library</h1>
          <p className="mt-2 text-sm text-gray-700">
            Manage preconfigured snapshots and base OS images
          </p>
        </div>
        <div className="mt-4 sm:mt-0 flex items-center space-x-3">
          {/* View Toggle - only show on Base OS Images tab */}
          {activeTab === 'base-images' && (
            <>
              <div className="flex items-center bg-gray-100 rounded-lg p-1">
                <button
                  onClick={() => setViewMode('tile')}
                  className={clsx(
                    "p-2 rounded-md transition-colors",
                    viewMode === 'tile'
                      ? "bg-white text-primary-600 shadow-sm"
                      : "text-gray-500 hover:text-gray-700"
                  )}
                  title="Tile view"
                >
                  <LayoutGrid className="h-4 w-4" />
                </button>
                <button
                  onClick={() => setViewMode('list')}
                  className={clsx(
                    "p-2 rounded-md transition-colors",
                    viewMode === 'list'
                      ? "bg-white text-primary-600 shadow-sm"
                      : "text-gray-500 hover:text-gray-700"
                  )}
                  title="List view"
                >
                  <List className="h-4 w-4" />
                </button>
              </div>
              <button
                onClick={openCreateModal}
                className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
              >
                <Plus className="h-4 w-4 mr-2" />
                New Template
              </button>
            </>
          )}
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="mt-6 border-b border-gray-200">
        <nav className="-mb-px flex space-x-8" aria-label="Tabs">
          <button
            onClick={() => setActiveTab('snapshots')}
            className={clsx(
              "flex items-center whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm",
              activeTab === 'snapshots'
                ? "border-primary-500 text-primary-600"
                : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
            )}
          >
            <Camera className={clsx(
              "mr-2 h-5 w-5",
              activeTab === 'snapshots' ? "text-primary-500" : "text-gray-400"
            )} />
            Snapshots
          </button>
          <button
            onClick={() => setActiveTab('base-images')}
            className={clsx(
              "flex items-center whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm",
              activeTab === 'base-images'
                ? "border-primary-500 text-primary-600"
                : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
            )}
          >
            <HardDrive className={clsx(
              "mr-2 h-5 w-5",
              activeTab === 'base-images' ? "text-primary-500" : "text-gray-400"
            )} />
            Base OS Images
            {templates.length > 0 && (
              <span className={clsx(
                "ml-2 py-0.5 px-2.5 rounded-full text-xs font-medium",
                activeTab === 'base-images'
                  ? "bg-primary-100 text-primary-600"
                  : "bg-gray-100 text-gray-900"
              )}>
                {templates.length}
              </span>
            )}
          </button>
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'snapshots' ? renderSnapshotsTab() : renderBaseImagesTab()}

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
                  <div className="grid grid-cols-3 gap-3">
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
                    <button
                      type="button"
                      onClick={() => handleOsTypeChange('custom')}
                      className={clsx(
                        "flex items-center justify-center p-3 border-2 rounded-lg transition-all",
                        formData.os_type === 'custom'
                          ? "border-purple-500 bg-purple-50 text-purple-700"
                          : "border-gray-200 hover:border-gray-300"
                      )}
                    >
                      <Disc className="h-5 w-5 mr-2" />
                      <span className="font-medium">Custom</span>
                    </button>
                  </div>
                </div>

                {/* Linux-specific fields */}
                {formData.os_type === 'linux' && (
                  <>
                    <div className="bg-orange-50 border border-orange-200 rounded-md p-3">
                      <div className="flex">
                        <Info className="h-4 w-4 text-orange-500 mt-0.5 mr-2" />
                        <p className="text-xs text-orange-700">
                          Linux VMs can use <strong>qemux/qemu</strong> with ISOs or <strong>Docker containers</strong>.
                          {linuxVersions && linuxVersions.cached_count > 0
                            ? ` ${linuxVersions.cached_count} ISO(s) cached locally.`
                            : ''}
                          {filteredCachedImages.length > 0
                            ? ` ${filteredCachedImages.length} container image(s) cached.`
                            : ''}
                        </p>
                      </div>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700">
                        Base Image
                      </label>
                      <select
                        required
                        value={formData.base_image}
                        onChange={(e) => {
                          const img = e.target.value
                          // Auto-fill os_variant from image name
                          let variant = ''
                          if (img.startsWith('iso:')) {
                            // Linux ISO
                            const version = img.replace('iso:', '')
                            const linuxVersion = linuxVersions?.all.find(v => v.version === version)
                            variant = linuxVersion?.name || version
                          } else {
                            // Docker image
                            variant = img.split(':')[0].split('/').pop() || img
                          }
                          setFormData({
                            ...formData,
                            base_image: img,
                            os_variant: formData.os_variant || variant
                          })
                        }}
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                      >
                        <option value="">Select an image...</option>

                        {/* Desktop */}
                        {((linuxVersions?.desktop.some(v => v.cached)) || getCachedContainersByCategory('desktop').length > 0) && (
                          <optgroup label="Desktop">
                            {linuxVersions?.desktop.filter(v => v.cached).map(v => (
                              <option key={`iso-${v.version}`} value={`iso:${v.version}`}>
                                {v.name} (ISO) - {v.size_gb} GB
                              </option>
                            ))}
                            {getCachedContainersByCategory('desktop').map(({ tag, size_gb }) => {
                              const displayName = getContainerImageName(tag)
                              return (
                                <option key={tag} value={tag}>
                                  {displayName} ({tag}) - {size_gb} GB
                                </option>
                              )
                            })}
                          </optgroup>
                        )}

                        {/* Server/CLI */}
                        {((linuxVersions?.server.some(v => v.cached)) || getCachedContainersByCategory('server').length > 0) && (
                          <optgroup label="Server/CLI">
                            {linuxVersions?.server.filter(v => v.cached).map(v => (
                              <option key={`iso-${v.version}`} value={`iso:${v.version}`}>
                                {v.name} (ISO) - {v.size_gb} GB
                              </option>
                            ))}
                            {getCachedContainersByCategory('server').map(({ tag, size_gb }) => {
                              const displayName = getContainerImageName(tag)
                              return (
                                <option key={tag} value={tag}>
                                  {displayName} ({tag}) - {size_gb} GB
                                </option>
                              )
                            })}
                          </optgroup>
                        )}

                        {/* Security */}
                        {linuxVersions?.security.some(v => v.cached) && (
                          <optgroup label="Security">
                            {linuxVersions.security.filter(v => v.cached).map(v => (
                              <option key={`iso-${v.version}`} value={`iso:${v.version}`}>
                                {v.name} (ISO) - {v.size_gb} GB
                              </option>
                            ))}
                          </optgroup>
                        )}

                        {/* Services */}
                        {getCachedContainersByCategory('services').length > 0 && (
                          <optgroup label="Services">
                            {getCachedContainersByCategory('services').map(({ tag, size_gb }) => {
                              const displayName = getContainerImageName(tag)
                              return (
                                <option key={tag} value={tag}>
                                  {displayName} ({tag}) - {size_gb} GB
                                </option>
                              )
                            })}
                          </optgroup>
                        )}

                      </select>
                      <p className="mt-1 text-xs text-gray-500">
                        Only cached images are shown. Visit <strong>Image Cache</strong> to download more options.
                      </p>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700">OS Variant Name</label>
                      <input
                        type="text"
                        required
                        placeholder="e.g., Ubuntu 24.04, Debian 13"
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
                            ? ` ${windowsVersions.cached_count} ISO(s) cached locally.`
                            : ' No ISOs cached. Visit Image Cache to download Windows ISOs.'}
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
                        {/* Desktop */}
                        {windowsVersions.desktop.some(v => v.cached) && (
                          <optgroup label="Desktop">
                            {windowsVersions.desktop.filter(v => v.cached).map(v => (
                              <option key={v.version} value={v.version}>
                                {v.name} ({v.version}) - {v.size_gb} GB
                              </option>
                            ))}
                          </optgroup>
                        )}
                        {/* Server */}
                        {windowsVersions.server.some(v => v.cached) && (
                          <optgroup label="Server">
                            {windowsVersions.server.filter(v => v.cached).map(v => (
                              <option key={v.version} value={v.version}>
                                {v.name} ({v.version}) - {v.size_gb} GB
                              </option>
                            ))}
                          </optgroup>
                        )}
                        {/* Legacy */}
                        {windowsVersions.legacy.some(v => v.cached) && (
                          <optgroup label="Legacy">
                            {windowsVersions.legacy.filter(v => v.cached).map(v => (
                              <option key={v.version} value={v.version}>
                                {v.name} ({v.version}) - {v.size_gb} GB
                              </option>
                            ))}
                          </optgroup>
                        )}
                      </select>
                      <p className="mt-1 text-xs text-gray-500">
                        Only cached ISOs are shown. Visit <strong>Image Cache</strong> to download more options.
                      </p>
                    </div>

                    {/* Custom ISO option */}
                    {customISOs && customISOs.isos.length > 0 && (
                      <div className="bg-gray-50 border border-gray-200 rounded-md p-3">
                        <p className="text-xs text-gray-600">
                          <strong>Custom ISO available:</strong> You can also use a custom ISO when creating VMs
                          from this template. {customISOs.total_count} custom ISO(s) in cache.
                        </p>
                      </div>
                    )}
                  </>
                )}

                {/* Custom ISO fields */}
                {formData.os_type === 'custom' && (
                  <>
                    <div className="bg-purple-50 border border-purple-200 rounded-md p-3">
                      <div className="flex">
                        <Info className="h-4 w-4 text-purple-500 mt-0.5 mr-2" />
                        <p className="text-xs text-purple-700">
                          Custom ISOs use <strong>qemux/qemu</strong> to boot any ISO image.
                          {customISOs && customISOs.total_count > 0
                            ? ` ${customISOs.total_count} custom ISO(s) available.`
                            : ' No custom ISOs available. Visit Image Cache to upload or download custom ISOs.'}
                        </p>
                      </div>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700">Custom ISO</label>
                      <select
                        required
                        value={formData.custom_iso}
                        onChange={(e) => {
                          const iso = customISOs?.isos.find(i => i.filename === e.target.value)
                          setFormData({
                            ...formData,
                            custom_iso: e.target.value,
                            os_variant: iso?.name || e.target.value.replace('.iso', ''),
                            base_image: 'qemux/qemu'
                          })
                        }}
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                      >
                        <option value="">Select a custom ISO...</option>
                        {customISOs?.isos.map(iso => (
                          <option key={iso.filename} value={iso.filename}>
                            {iso.name} ({iso.size_gb} GB)
                          </option>
                        ))}
                      </select>
                      <p className="mt-1 text-xs text-gray-500">
                        Select from your uploaded/downloaded custom ISOs. Visit <strong>Image Cache</strong> to add more.
                      </p>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700">OS Variant Name</label>
                      <input
                        type="text"
                        required
                        value={formData.os_variant}
                        onChange={(e) => setFormData({ ...formData, os_variant: e.target.value })}
                        placeholder="e.g., OPNsense 24.1, pfSense 2.7, FreeBSD 14"
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                      />
                      <p className="mt-1 text-xs text-gray-500">
                        A descriptive name for this OS (shown in UI).
                      </p>
                    </div>
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
                    disabled={submitting}
                    className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 disabled:opacity-50"
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

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        isOpen={deleteConfirm.template !== null}
        title="Delete Template"
        message={`Are you sure you want to delete "${deleteConfirm.template?.name}"? This action cannot be undone.`}
        confirmLabel="Delete"
        variant="danger"
        onConfirm={confirmDelete}
        onCancel={() => setDeleteConfirm({ template: null, isLoading: false })}
        isLoading={deleteConfirm.isLoading}
      />
    </div>
  )
}
