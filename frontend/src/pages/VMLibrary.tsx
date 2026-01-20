// frontend/src/pages/VMLibrary.tsx
import { useEffect, useState } from 'react'
import { imagesApi, BaseImageUpdate, GoldenImageUpdate } from '../services/api'
import type { BaseImage, GoldenImageLibrary, SnapshotWithLineage, LibraryStats } from '../types'
import { Pencil, Trash2, Loader2, X, Server, HardDrive, Star, Camera, Upload, Database, ArrowRight, RefreshCw, LayoutGrid, List } from 'lucide-react'
import clsx from 'clsx'
import { ConfirmDialog } from '../components/common/ConfirmDialog'
import { toast } from '../stores/toastStore'
import { Link } from 'react-router-dom'

// Tab type for the VM Library
type VMLibraryTab = 'base' | 'golden' | 'snapshots'

// Format bytes to human readable
const formatBytes = (bytes: number | null): string => {
  if (!bytes) return '-'
  const gb = bytes / (1024 * 1024 * 1024)
  if (gb >= 1) return `${gb.toFixed(1)} GB`
  const mb = bytes / (1024 * 1024)
  return `${mb.toFixed(0)} MB`
}

export default function VMLibrary() {
  // Tab state - default to 'base'
  const [activeTab, setActiveTab] = useState<VMLibraryTab>('base')
  const [viewMode, setViewMode] = useState<'tile' | 'list'>('tile')
  const [loading, setLoading] = useState(true)

  // Data states
  const [stats, setStats] = useState<LibraryStats | null>(null)
  const [baseImages, setBaseImages] = useState<BaseImage[]>([])
  const [goldenImages, setGoldenImages] = useState<GoldenImageLibrary[]>([])
  const [snapshots, setSnapshots] = useState<SnapshotWithLineage[]>([])

  // Edit modal states
  const [editingBaseImage, setEditingBaseImage] = useState<BaseImage | null>(null)
  const [editingGoldenImage, setEditingGoldenImage] = useState<GoldenImageLibrary | null>(null)
  const [showEditModal, setShowEditModal] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  // Import modal
  const [showImportModal, setShowImportModal] = useState(false)
  const [importFile, setImportFile] = useState<File | null>(null)
  const [importMetadata, setImportMetadata] = useState({
    name: '',
    description: '',
    os_type: 'linux' as 'windows' | 'linux' | 'network' | 'custom',
    vm_type: 'linux_vm' as 'container' | 'linux_vm' | 'windows_vm',
    native_arch: 'x86_64',
    default_cpu: 2,
    default_ram_mb: 4096,
    default_disk_gb: 40,
  })
  const [importing, setImporting] = useState(false)

  // Delete confirmation
  const [deleteConfirm, setDeleteConfirm] = useState<{
    type: 'base' | 'golden' | null
    item: BaseImage | GoldenImageLibrary | null
    isLoading: boolean
  }>({ type: null, item: null, isLoading: false })

  const fetchStats = async () => {
    try {
      const response = await imagesApi.getLibraryStats()
      setStats(response.data)
    } catch (err) {
      console.error('Failed to fetch library stats:', err)
    }
  }

  const fetchBaseImages = async () => {
    try {
      const response = await imagesApi.listBaseImages()
      setBaseImages(response.data)
    } catch (err) {
      console.error('Failed to fetch base images:', err)
    }
  }

  const fetchGoldenImages = async () => {
    try {
      const response = await imagesApi.listGoldenImages()
      setGoldenImages(response.data)
    } catch (err) {
      console.error('Failed to fetch golden images:', err)
    }
  }

  const fetchSnapshots = async () => {
    try {
      const response = await imagesApi.listLibrarySnapshots()
      setSnapshots(response.data)
    } catch (err) {
      console.error('Failed to fetch snapshots:', err)
    }
  }

  const fetchAll = async () => {
    setLoading(true)
    await Promise.all([fetchStats(), fetchBaseImages(), fetchGoldenImages(), fetchSnapshots()])
    setLoading(false)
  }

  useEffect(() => {
    fetchAll()
  }, [])

  // Edit handlers
  const openEditBaseImage = (image: BaseImage) => {
    setEditingBaseImage(image)
    setEditingGoldenImage(null)
    setShowEditModal(true)
  }

  const openEditGoldenImage = (image: GoldenImageLibrary) => {
    setEditingGoldenImage(image)
    setEditingBaseImage(null)
    setShowEditModal(true)
  }

  const handleSaveEdit = async () => {
    setSubmitting(true)
    try {
      if (editingBaseImage) {
        const update: BaseImageUpdate = {
          name: editingBaseImage.name,
          description: editingBaseImage.description || undefined,
          default_cpu: editingBaseImage.default_cpu,
          default_ram_mb: editingBaseImage.default_ram_mb,
          default_disk_gb: editingBaseImage.default_disk_gb,
        }
        await imagesApi.updateBaseImage(editingBaseImage.id, update)
        toast.success('Base image updated')
        fetchBaseImages()
      } else if (editingGoldenImage) {
        const update: GoldenImageUpdate = {
          name: editingGoldenImage.name,
          description: editingGoldenImage.description || undefined,
          default_cpu: editingGoldenImage.default_cpu,
          default_ram_mb: editingGoldenImage.default_ram_mb,
          default_disk_gb: editingGoldenImage.default_disk_gb,
        }
        await imagesApi.updateGoldenImage(editingGoldenImage.id, update)
        toast.success('Golden image updated')
        fetchGoldenImages()
      }
      setShowEditModal(false)
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to save changes')
    } finally {
      setSubmitting(false)
    }
  }

  // Delete handlers
  const handleDeleteBase = (image: BaseImage) => {
    setDeleteConfirm({ type: 'base', item: image, isLoading: false })
  }

  const handleDeleteGolden = (image: GoldenImageLibrary) => {
    setDeleteConfirm({ type: 'golden', item: image, isLoading: false })
  }

  const confirmDelete = async () => {
    if (!deleteConfirm.item || !deleteConfirm.type) return
    setDeleteConfirm(prev => ({ ...prev, isLoading: true }))
    try {
      if (deleteConfirm.type === 'base') {
        await imagesApi.deleteBaseImage(deleteConfirm.item.id)
        toast.success('Base image deleted')
        fetchBaseImages()
      } else {
        await imagesApi.deleteGoldenImage(deleteConfirm.item.id)
        toast.success('Golden image deleted')
        fetchGoldenImages()
      }
      fetchStats()
      setDeleteConfirm({ type: null, item: null, isLoading: false })
    } catch (err: any) {
      setDeleteConfirm({ type: null, item: null, isLoading: false })
      toast.error(err.response?.data?.detail || 'Failed to delete image')
    }
  }

  // Import handlers
  const handleImport = async () => {
    if (!importFile) return
    setImporting(true)
    try {
      await imagesApi.importGoldenImage(importFile, importMetadata)
      toast.success('Image imported successfully')
      setShowImportModal(false)
      setImportFile(null)
      setImportMetadata({
        name: '',
        description: '',
        os_type: 'linux',
        vm_type: 'linux_vm',
        native_arch: 'x86_64',
        default_cpu: 2,
        default_ram_mb: 4096,
        default_disk_gb: 40,
      })
      fetchGoldenImages()
      fetchStats()
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to import image')
    } finally {
      setImporting(false)
    }
  }

  // Get type badge color
  const getTypeBadgeColor = (imageType: string) => {
    return imageType === 'container'
      ? 'bg-blue-100 text-blue-800'
      : 'bg-purple-100 text-purple-800'
  }

  const getSourceBadgeColor = (source: string) => {
    return source === 'snapshot'
      ? 'bg-green-100 text-green-800'
      : 'bg-orange-100 text-orange-800'
  }

  // Render Base Images tab
  const renderBaseImagesTab = () => {
    if (baseImages.length === 0) {
      return (
        <div className="mt-8 text-center bg-white shadow rounded-lg p-8">
          <Database className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-4 text-lg font-medium text-gray-900">No Base Images</h3>
          <p className="mt-2 text-sm text-gray-500 max-w-md mx-auto">
            Base images are automatically created when you pull Docker images or download ISOs from the Image Cache.
          </p>
          <div className="mt-6">
            <Link
              to="/vm-library/cache"
              className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700"
            >
              <HardDrive className="h-4 w-4 mr-2" />
              Go to Image Cache
            </Link>
          </div>
        </div>
      )
    }

    return viewMode === 'tile' ? (
      <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {baseImages.map((image) => (
          <div key={image.id} className="bg-white overflow-hidden shadow rounded-lg">
            <div className="p-5">
              <div className="flex items-center justify-between">
                <div className="flex items-center">
                  <div className={clsx(
                    "flex-shrink-0 rounded-md p-2",
                    image.image_type === 'container' ? 'bg-blue-100' : 'bg-purple-100'
                  )}>
                    {image.image_type === 'container' ? (
                      <Server className="h-6 w-6 text-blue-600" />
                    ) : (
                      <HardDrive className="h-6 w-6 text-purple-600" />
                    )}
                  </div>
                  <div className="ml-4">
                    <h3 className="text-lg font-medium text-gray-900">{image.name}</h3>
                    <span className={clsx(
                      "inline-flex items-center px-2 py-0.5 rounded text-xs font-medium",
                      getTypeBadgeColor(image.image_type)
                    )}>
                      {image.image_type === 'container' ? 'Container' : 'ISO'}
                    </span>
                  </div>
                </div>
              </div>

              {image.description && (
                <p className="mt-3 text-sm text-gray-600 line-clamp-2">{image.description}</p>
              )}

              <div className="mt-4 text-xs text-gray-500 space-y-1">
                <div className="flex justify-between">
                  <span>OS Type:</span>
                  <span className="font-medium capitalize">{image.os_type}</span>
                </div>
                <div className="flex justify-between">
                  <span>VM Type:</span>
                  <span className="font-medium">{image.vm_type.replace('_', ' ')}</span>
                </div>
                <div className="flex justify-between">
                  <span>Size:</span>
                  <span className="font-medium">{formatBytes(image.size_bytes)}</span>
                </div>
              </div>

              <div className="mt-4 grid grid-cols-3 gap-2 text-center text-xs">
                <div className="bg-gray-50 rounded p-2">
                  <div className="font-semibold text-gray-900">{image.default_cpu}</div>
                  <div className="text-gray-500">CPU</div>
                </div>
                <div className="bg-gray-50 rounded p-2">
                  <div className="font-semibold text-gray-900">{image.default_ram_mb / 1024}GB</div>
                  <div className="text-gray-500">RAM</div>
                </div>
                <div className="bg-gray-50 rounded p-2">
                  <div className="font-semibold text-gray-900">{image.default_disk_gb}GB</div>
                  <div className="text-gray-500">Disk</div>
                </div>
              </div>
            </div>

            <div className="bg-gray-50 px-5 py-3 flex justify-end space-x-2">
              <button
                onClick={() => openEditBaseImage(image)}
                className="p-2 text-gray-400 hover:text-primary-600"
                title="Edit"
              >
                <Pencil className="h-4 w-4" />
              </button>
              <button
                onClick={() => handleDeleteBase(image)}
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
      <div className="mt-8 bg-white shadow rounded-lg overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Image</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">OS</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Resources</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Size</th>
              <th className="relative px-6 py-3"><span className="sr-only">Actions</span></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {baseImages.map((image) => (
              <tr key={image.id} className="hover:bg-gray-50">
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex items-center">
                    <div className={clsx(
                      "flex-shrink-0 rounded-md p-2",
                      image.image_type === 'container' ? 'bg-blue-100' : 'bg-purple-100'
                    )}>
                      {image.image_type === 'container' ? (
                        <Server className="h-5 w-5 text-blue-600" />
                      ) : (
                        <HardDrive className="h-5 w-5 text-purple-600" />
                      )}
                    </div>
                    <div className="ml-4">
                      <div className="text-sm font-medium text-gray-900">{image.name}</div>
                      {image.docker_image_tag && (
                        <div className="text-xs text-gray-500 truncate max-w-xs">{image.docker_image_tag}</div>
                      )}
                    </div>
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className={clsx(
                    "inline-flex items-center px-2 py-0.5 rounded text-xs font-medium",
                    getTypeBadgeColor(image.image_type)
                  )}>
                    {image.image_type === 'container' ? 'Container' : 'ISO'}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="text-sm text-gray-900 capitalize">{image.os_type}</div>
                  <div className="text-xs text-gray-500">{image.vm_type.replace('_', ' ')}</div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {image.default_cpu} CPU / {image.default_ram_mb / 1024}GB RAM / {image.default_disk_gb}GB
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {formatBytes(image.size_bytes)}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                  <div className="flex justify-end space-x-2">
                    <button onClick={() => openEditBaseImage(image)} className="p-1.5 text-gray-400 hover:text-primary-600">
                      <Pencil className="h-4 w-4" />
                    </button>
                    <button onClick={() => handleDeleteBase(image)} className="p-1.5 text-gray-400 hover:text-red-600">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  // Render Golden Images tab
  const renderGoldenImagesTab = () => {
    if (goldenImages.length === 0) {
      return (
        <div className="mt-8 text-center bg-white shadow rounded-lg p-8">
          <Star className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-4 text-lg font-medium text-gray-900">No Golden Images</h3>
          <p className="mt-2 text-sm text-gray-500 max-w-md mx-auto">
            Golden images are created when you take the first snapshot of a VM, or when you import OVA/QCOW2/VMDK files.
          </p>
          <div className="mt-6">
            <button
              onClick={() => setShowImportModal(true)}
              className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700"
            >
              <Upload className="h-4 w-4 mr-2" />
              Import VM Image
            </button>
          </div>
        </div>
      )
    }

    return viewMode === 'tile' ? (
      <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {goldenImages.map((image) => (
          <div key={image.id} className="bg-white overflow-hidden shadow rounded-lg">
            <div className="p-5">
              <div className="flex items-center justify-between">
                <div className="flex items-center">
                  <div className="flex-shrink-0 rounded-md p-2 bg-yellow-100">
                    <Star className="h-6 w-6 text-yellow-600" />
                  </div>
                  <div className="ml-4">
                    <h3 className="text-lg font-medium text-gray-900">{image.name}</h3>
                    <span className={clsx(
                      "inline-flex items-center px-2 py-0.5 rounded text-xs font-medium",
                      getSourceBadgeColor(image.source)
                    )}>
                      {image.source === 'snapshot' ? 'Snapshot' : 'Imported'}
                    </span>
                  </div>
                </div>
              </div>

              {image.base_image && (
                <div className="mt-3 flex items-center text-xs text-gray-500">
                  <ArrowRight className="h-3 w-3 mr-1 text-gray-400" />
                  <span>From: <strong>{image.base_image.name}</strong></span>
                </div>
              )}

              {image.description && (
                <p className="mt-2 text-sm text-gray-600 line-clamp-2">{image.description}</p>
              )}

              <div className="mt-4 text-xs text-gray-500 space-y-1">
                <div className="flex justify-between">
                  <span>OS Type:</span>
                  <span className="font-medium capitalize">{image.os_type}</span>
                </div>
                <div className="flex justify-between">
                  <span>VM Type:</span>
                  <span className="font-medium">{image.vm_type.replace('_', ' ')}</span>
                </div>
                {image.import_format && (
                  <div className="flex justify-between">
                    <span>Format:</span>
                    <span className="font-medium uppercase">{image.import_format}</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span>Size:</span>
                  <span className="font-medium">{formatBytes(image.size_bytes)}</span>
                </div>
              </div>

              <div className="mt-4 grid grid-cols-3 gap-2 text-center text-xs">
                <div className="bg-gray-50 rounded p-2">
                  <div className="font-semibold text-gray-900">{image.default_cpu}</div>
                  <div className="text-gray-500">CPU</div>
                </div>
                <div className="bg-gray-50 rounded p-2">
                  <div className="font-semibold text-gray-900">{image.default_ram_mb / 1024}GB</div>
                  <div className="text-gray-500">RAM</div>
                </div>
                <div className="bg-gray-50 rounded p-2">
                  <div className="font-semibold text-gray-900">{image.default_disk_gb}GB</div>
                  <div className="text-gray-500">Disk</div>
                </div>
              </div>
            </div>

            <div className="bg-gray-50 px-5 py-3 flex justify-end space-x-2">
              <button
                onClick={() => openEditGoldenImage(image)}
                className="p-2 text-gray-400 hover:text-primary-600"
                title="Edit"
              >
                <Pencil className="h-4 w-4" />
              </button>
              <button
                onClick={() => handleDeleteGolden(image)}
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
      <div className="mt-8 bg-white shadow rounded-lg overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Image</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Source</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Lineage</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Resources</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Size</th>
              <th className="relative px-6 py-3"><span className="sr-only">Actions</span></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {goldenImages.map((image) => (
              <tr key={image.id} className="hover:bg-gray-50">
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex items-center">
                    <div className="flex-shrink-0 rounded-md p-2 bg-yellow-100">
                      <Star className="h-5 w-5 text-yellow-600" />
                    </div>
                    <div className="ml-4">
                      <div className="text-sm font-medium text-gray-900">{image.name}</div>
                      <div className="text-xs text-gray-500 capitalize">{image.os_type} / {image.vm_type.replace('_', ' ')}</div>
                    </div>
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className={clsx(
                    "inline-flex items-center px-2 py-0.5 rounded text-xs font-medium",
                    getSourceBadgeColor(image.source)
                  )}>
                    {image.source === 'snapshot' ? 'Snapshot' : 'Imported'}
                  </span>
                  {image.import_format && (
                    <span className="ml-1 text-xs text-gray-500 uppercase">({image.import_format})</span>
                  )}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {image.base_image ? (
                    <span>From: {image.base_image.name}</span>
                  ) : (
                    <span className="text-gray-400">-</span>
                  )}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {image.default_cpu} CPU / {image.default_ram_mb / 1024}GB RAM / {image.default_disk_gb}GB
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {formatBytes(image.size_bytes)}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                  <div className="flex justify-end space-x-2">
                    <button onClick={() => openEditGoldenImage(image)} className="p-1.5 text-gray-400 hover:text-primary-600">
                      <Pencil className="h-4 w-4" />
                    </button>
                    <button onClick={() => handleDeleteGolden(image)} className="p-1.5 text-gray-400 hover:text-red-600">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  // Render Snapshots tab
  const renderSnapshotsTab = () => {
    if (snapshots.length === 0) {
      return (
        <div className="mt-8 text-center bg-white shadow rounded-lg p-8">
          <Camera className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-4 text-lg font-medium text-gray-900">No Snapshots</h3>
          <p className="mt-2 text-sm text-gray-500 max-w-md mx-auto">
            Snapshots are created when you take additional snapshots of a VM after the first one (which becomes a Golden Image).
          </p>
          <div className="mt-6 bg-gray-50 rounded-lg p-4 max-w-lg mx-auto">
            <h4 className="text-sm font-medium text-gray-700 mb-2">How Snapshots Work:</h4>
            <ul className="text-sm text-gray-600 text-left list-disc list-inside space-y-1">
              <li><strong>First snapshot</strong> of a VM becomes a Golden Image</li>
              <li><strong>Additional snapshots</strong> become Snapshots (forks)</li>
              <li>Snapshots track their lineage to the parent Golden Image</li>
              <li>Create VMs from any snapshot to restore to that state</li>
            </ul>
          </div>
        </div>
      )
    }

    return viewMode === 'tile' ? (
      <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {snapshots.map((snapshot) => (
          <div key={snapshot.id} className="bg-white overflow-hidden shadow rounded-lg">
            <div className="p-5">
              <div className="flex items-center justify-between">
                <div className="flex items-center">
                  <div className="flex-shrink-0 rounded-md p-2 bg-cyan-100">
                    <Camera className="h-6 w-6 text-cyan-600" />
                  </div>
                  <div className="ml-4">
                    <h3 className="text-lg font-medium text-gray-900">{snapshot.name}</h3>
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-cyan-100 text-cyan-800">
                      Fork
                    </span>
                  </div>
                </div>
              </div>

              {snapshot.golden_image && (
                <div className="mt-3 flex items-center text-xs text-gray-500">
                  <ArrowRight className="h-3 w-3 mr-1 text-gray-400" />
                  <span>Fork of: <strong>{snapshot.golden_image.name}</strong></span>
                </div>
              )}

              {snapshot.description && (
                <p className="mt-2 text-sm text-gray-600 line-clamp-2">{snapshot.description}</p>
              )}

              <div className="mt-4 grid grid-cols-3 gap-2 text-center text-xs">
                <div className="bg-gray-50 rounded p-2">
                  <div className="font-semibold text-gray-900">{snapshot.default_cpu}</div>
                  <div className="text-gray-500">CPU</div>
                </div>
                <div className="bg-gray-50 rounded p-2">
                  <div className="font-semibold text-gray-900">{snapshot.default_ram_mb / 1024}GB</div>
                  <div className="text-gray-500">RAM</div>
                </div>
                <div className="bg-gray-50 rounded p-2">
                  <div className="font-semibold text-gray-900">{snapshot.default_disk_gb}GB</div>
                  <div className="text-gray-500">Disk</div>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    ) : (
      <div className="mt-8 bg-white shadow rounded-lg overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Snapshot</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Parent Golden Image</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Resources</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Created</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {snapshots.map((snapshot) => (
              <tr key={snapshot.id} className="hover:bg-gray-50">
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex items-center">
                    <div className="flex-shrink-0 rounded-md p-2 bg-cyan-100">
                      <Camera className="h-5 w-5 text-cyan-600" />
                    </div>
                    <div className="ml-4">
                      <div className="text-sm font-medium text-gray-900">{snapshot.name}</div>
                      {snapshot.description && (
                        <div className="text-xs text-gray-500 truncate max-w-xs">{snapshot.description}</div>
                      )}
                    </div>
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {snapshot.golden_image ? (
                    <span>Fork of: {snapshot.golden_image.name}</span>
                  ) : (
                    <span className="text-gray-400">-</span>
                  )}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {snapshot.default_cpu} CPU / {snapshot.default_ram_mb / 1024}GB RAM / {snapshot.default_disk_gb}GB
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {new Date(snapshot.created_at).toLocaleDateString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
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
          <h1 className="text-2xl font-bold text-gray-900">Image Library</h1>
          <p className="mt-2 text-sm text-gray-700">
            Manage base images, golden images, and snapshots for VM creation
          </p>
        </div>
        <div className="mt-4 sm:mt-0 flex items-center space-x-3">
          {/* Stats Summary */}
          {stats && (
            <div className="hidden md:flex items-center space-x-4 text-sm text-gray-500 mr-4">
              <span>{stats.base_images_count} base</span>
              <span>{stats.golden_images_count} golden</span>
              <span>{stats.snapshots_count} snapshots</span>
            </div>
          )}

          {/* View Toggle */}
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

          {/* Refresh */}
          <button
            onClick={fetchAll}
            className="p-2 text-gray-400 hover:text-gray-600"
            title="Refresh"
          >
            <RefreshCw className="h-5 w-5" />
          </button>

          {/* Import button (Golden Images tab only) */}
          {activeTab === 'golden' && (
            <button
              onClick={() => setShowImportModal(true)}
              className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700"
            >
              <Upload className="h-4 w-4 mr-2" />
              Import
            </button>
          )}
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="mt-6 border-b border-gray-200">
        <nav className="-mb-px flex space-x-8" aria-label="Tabs">
          <button
            onClick={() => setActiveTab('base')}
            className={clsx(
              "flex items-center whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm",
              activeTab === 'base'
                ? "border-primary-500 text-primary-600"
                : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
            )}
          >
            <Database className={clsx("mr-2 h-5 w-5", activeTab === 'base' ? "text-primary-500" : "text-gray-400")} />
            Base Images
            {stats && stats.base_images_count > 0 && (
              <span className={clsx(
                "ml-2 py-0.5 px-2.5 rounded-full text-xs font-medium",
                activeTab === 'base' ? "bg-primary-100 text-primary-600" : "bg-gray-100 text-gray-900"
              )}>
                {stats.base_images_count}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab('golden')}
            className={clsx(
              "flex items-center whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm",
              activeTab === 'golden'
                ? "border-primary-500 text-primary-600"
                : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
            )}
          >
            <Star className={clsx("mr-2 h-5 w-5", activeTab === 'golden' ? "text-primary-500" : "text-gray-400")} />
            Golden Images
            {stats && stats.golden_images_count > 0 && (
              <span className={clsx(
                "ml-2 py-0.5 px-2.5 rounded-full text-xs font-medium",
                activeTab === 'golden' ? "bg-primary-100 text-primary-600" : "bg-gray-100 text-gray-900"
              )}>
                {stats.golden_images_count}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab('snapshots')}
            className={clsx(
              "flex items-center whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm",
              activeTab === 'snapshots'
                ? "border-primary-500 text-primary-600"
                : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
            )}
          >
            <Camera className={clsx("mr-2 h-5 w-5", activeTab === 'snapshots' ? "text-primary-500" : "text-gray-400")} />
            Snapshots
            {stats && stats.snapshots_count > 0 && (
              <span className={clsx(
                "ml-2 py-0.5 px-2.5 rounded-full text-xs font-medium",
                activeTab === 'snapshots' ? "bg-primary-100 text-primary-600" : "bg-gray-100 text-gray-900"
              )}>
                {stats.snapshots_count}
              </span>
            )}
          </button>
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'base' && renderBaseImagesTab()}
      {activeTab === 'golden' && renderGoldenImagesTab()}
      {activeTab === 'snapshots' && renderSnapshotsTab()}

      {/* Edit Modal */}
      {showEditModal && (editingBaseImage || editingGoldenImage) && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex items-center justify-center min-h-screen px-4">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75" onClick={() => setShowEditModal(false)} />

            <div className="relative bg-white rounded-lg shadow-xl max-w-lg w-full">
              <div className="flex items-center justify-between p-4 border-b">
                <h3 className="text-lg font-medium text-gray-900">
                  Edit {editingBaseImage ? 'Base Image' : 'Golden Image'}
                </h3>
                <button onClick={() => setShowEditModal(false)} className="text-gray-400 hover:text-gray-500">
                  <X className="h-5 w-5" />
                </button>
              </div>

              <div className="p-4 space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700">Name</label>
                  <input
                    type="text"
                    value={editingBaseImage?.name || editingGoldenImage?.name || ''}
                    onChange={(e) => {
                      if (editingBaseImage) {
                        setEditingBaseImage({ ...editingBaseImage, name: e.target.value })
                      } else if (editingGoldenImage) {
                        setEditingGoldenImage({ ...editingGoldenImage, name: e.target.value })
                      }
                    }}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">Description</label>
                  <textarea
                    rows={2}
                    value={editingBaseImage?.description || editingGoldenImage?.description || ''}
                    onChange={(e) => {
                      if (editingBaseImage) {
                        setEditingBaseImage({ ...editingBaseImage, description: e.target.value })
                      } else if (editingGoldenImage) {
                        setEditingGoldenImage({ ...editingGoldenImage, description: e.target.value })
                      }
                    }}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                  />
                </div>

                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Default CPU</label>
                    <input
                      type="number"
                      min={1}
                      max={32}
                      value={editingBaseImage?.default_cpu || editingGoldenImage?.default_cpu || 2}
                      onChange={(e) => {
                        const val = parseInt(e.target.value)
                        if (editingBaseImage) {
                          setEditingBaseImage({ ...editingBaseImage, default_cpu: val })
                        } else if (editingGoldenImage) {
                          setEditingGoldenImage({ ...editingGoldenImage, default_cpu: val })
                        }
                      }}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">RAM (MB)</label>
                    <input
                      type="number"
                      min={512}
                      step={512}
                      value={editingBaseImage?.default_ram_mb || editingGoldenImage?.default_ram_mb || 4096}
                      onChange={(e) => {
                        const val = parseInt(e.target.value)
                        if (editingBaseImage) {
                          setEditingBaseImage({ ...editingBaseImage, default_ram_mb: val })
                        } else if (editingGoldenImage) {
                          setEditingGoldenImage({ ...editingGoldenImage, default_ram_mb: val })
                        }
                      }}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Disk (GB)</label>
                    <input
                      type="number"
                      min={5}
                      value={editingBaseImage?.default_disk_gb || editingGoldenImage?.default_disk_gb || 40}
                      onChange={(e) => {
                        const val = parseInt(e.target.value)
                        if (editingBaseImage) {
                          setEditingBaseImage({ ...editingBaseImage, default_disk_gb: val })
                        } else if (editingGoldenImage) {
                          setEditingGoldenImage({ ...editingGoldenImage, default_disk_gb: val })
                        }
                      }}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                    />
                  </div>
                </div>

                <div className="flex justify-end space-x-3 pt-4">
                  <button
                    type="button"
                    onClick={() => setShowEditModal(false)}
                    className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSaveEdit}
                    disabled={submitting}
                    className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 disabled:opacity-50"
                  >
                    {submitting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                    Save
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Import Modal */}
      {showImportModal && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex items-center justify-center min-h-screen px-4">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75" onClick={() => setShowImportModal(false)} />

            <div className="relative bg-white rounded-lg shadow-xl max-w-lg w-full">
              <div className="flex items-center justify-between p-4 border-b">
                <h3 className="text-lg font-medium text-gray-900">Import VM Image</h3>
                <button onClick={() => setShowImportModal(false)} className="text-gray-400 hover:text-gray-500">
                  <X className="h-5 w-5" />
                </button>
              </div>

              <div className="p-4 space-y-4">
                <div className="bg-blue-50 border border-blue-200 rounded-md p-3">
                  <p className="text-xs text-blue-700">
                    Import OVA, QCOW2, VMDK, or VDI files as Golden Images. Files will be converted to QCOW2 format for use with QEMU.
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">VM Image File</label>
                  <input
                    type="file"
                    accept=".ova,.qcow2,.vmdk,.vdi"
                    onChange={(e) => {
                      const file = e.target.files?.[0]
                      if (file) {
                        setImportFile(file)
                        // Auto-fill name from filename
                        if (!importMetadata.name) {
                          const name = file.name.replace(/\.(ova|qcow2|vmdk|vdi)$/i, '').replace(/[_-]/g, ' ')
                          setImportMetadata(prev => ({ ...prev, name }))
                        }
                      }
                    }}
                    className="mt-1 block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">Name</label>
                  <input
                    type="text"
                    required
                    value={importMetadata.name}
                    onChange={(e) => setImportMetadata({ ...importMetadata, name: e.target.value })}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">Description</label>
                  <textarea
                    rows={2}
                    value={importMetadata.description}
                    onChange={(e) => setImportMetadata({ ...importMetadata, description: e.target.value })}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">OS Type</label>
                    <select
                      value={importMetadata.os_type}
                      onChange={(e) => setImportMetadata({ ...importMetadata, os_type: e.target.value as any })}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                    >
                      <option value="linux">Linux</option>
                      <option value="windows">Windows</option>
                      <option value="network">Network</option>
                      <option value="custom">Custom</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">VM Type</label>
                    <select
                      value={importMetadata.vm_type}
                      onChange={(e) => setImportMetadata({ ...importMetadata, vm_type: e.target.value as any })}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                    >
                      <option value="linux_vm">Linux VM</option>
                      <option value="windows_vm">Windows VM</option>
                      <option value="container">Container</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">CPU</label>
                    <input
                      type="number"
                      min={1}
                      max={32}
                      value={importMetadata.default_cpu}
                      onChange={(e) => setImportMetadata({ ...importMetadata, default_cpu: parseInt(e.target.value) })}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">RAM (MB)</label>
                    <input
                      type="number"
                      min={512}
                      step={512}
                      value={importMetadata.default_ram_mb}
                      onChange={(e) => setImportMetadata({ ...importMetadata, default_ram_mb: parseInt(e.target.value) })}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Disk (GB)</label>
                    <input
                      type="number"
                      min={5}
                      value={importMetadata.default_disk_gb}
                      onChange={(e) => setImportMetadata({ ...importMetadata, default_disk_gb: parseInt(e.target.value) })}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                    />
                  </div>
                </div>

                <div className="flex justify-end space-x-3 pt-4">
                  <button
                    type="button"
                    onClick={() => setShowImportModal(false)}
                    className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleImport}
                    disabled={importing || !importFile || !importMetadata.name}
                    className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 disabled:opacity-50"
                  >
                    {importing && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                    Import
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        isOpen={deleteConfirm.item !== null}
        title={`Delete ${deleteConfirm.type === 'base' ? 'Base Image' : 'Golden Image'}`}
        message={`Are you sure you want to delete "${deleteConfirm.item?.name}"? This action cannot be undone.`}
        confirmLabel="Delete"
        variant="danger"
        onConfirm={confirmDelete}
        onCancel={() => setDeleteConfirm({ type: null, item: null, isLoading: false })}
        isLoading={deleteConfirm.isLoading}
      />
    </div>
  )
}
