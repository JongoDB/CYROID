// frontend/src/components/admin/RegistryTab.tsx
import { useEffect, useState, useCallback } from 'react'
import {
  registryApi,
  cacheApi,
  type RegistryImage,
  type RegistryStats,
} from '../../services/api'
import type { CachedImage } from '../../types'
import { toast } from '../../stores/toastStore'
import {
  Loader2,
  RefreshCw,
  Upload,
  Box,
  CheckCircle2,
  XCircle,
  Server,
  Tag,
  Database,
  Trash2,
  UploadCloud,
} from 'lucide-react'
import clsx from 'clsx'

export default function RegistryTab() {
  // Stats state
  const [stats, setStats] = useState<RegistryStats | null>(null)
  const [statsLoading, setStatsLoading] = useState(true)

  // Images list state
  const [images, setImages] = useState<RegistryImage[]>([])
  const [imagesLoading, setImagesLoading] = useState(true)

  // Host images for push dropdown
  const [hostImages, setHostImages] = useState<CachedImage[]>([])
  const [hostImagesLoading, setHostImagesLoading] = useState(true)

  // Push state
  const [selectedImage, setSelectedImage] = useState<string>('')
  const [pushing, setPushing] = useState(false)

  // Delete state
  const [deleting, setDeleting] = useState<string | null>(null)

  // Bulk push state
  const [pushingAll, setPushingAll] = useState(false)
  const [pushProgress, setPushProgress] = useState<{ current: number; total: number } | null>(null)

  // Refresh state
  const [refreshing, setRefreshing] = useState(false)

  const fetchStats = useCallback(async () => {
    try {
      const res = await registryApi.getStats()
      setStats(res.data)
    } catch (err: any) {
      console.error('Failed to fetch registry stats:', err)
      // Set unhealthy stats if we can't reach the registry
      setStats({ image_count: 0, tag_count: 0, healthy: false })
    }
  }, [])

  const fetchImages = useCallback(async () => {
    try {
      const res = await registryApi.listImages()
      setImages(res.data)
    } catch (err: any) {
      console.error('Failed to fetch registry images:', err)
      setImages([])
    }
  }, [])

  const fetchHostImages = useCallback(async () => {
    try {
      const res = await cacheApi.listImages()
      setHostImages(res.data)
    } catch (err: any) {
      console.error('Failed to fetch host images:', err)
      toast.error('Failed to load host Docker images')
    }
  }, [])

  const fetchAll = useCallback(async (showLoading = true) => {
    if (showLoading) {
      setStatsLoading(true)
      setImagesLoading(true)
      setHostImagesLoading(true)
    }
    setRefreshing(true)

    try {
      await Promise.all([
        fetchStats(),
        fetchImages(),
        fetchHostImages(),
      ])
    } finally {
      setStatsLoading(false)
      setImagesLoading(false)
      setHostImagesLoading(false)
      setRefreshing(false)
    }
  }, [fetchStats, fetchImages, fetchHostImages])

  useEffect(() => {
    fetchAll()
  }, [fetchAll])

  const handlePush = async () => {
    if (!selectedImage) {
      toast.warning('Please select an image to push')
      return
    }

    setPushing(true)
    try {
      const res = await registryApi.pushImage(selectedImage)
      if (res.data.operation_id) {
        toast.success(res.data.message || `Push started for ${selectedImage}`)
        setSelectedImage('')
        // Refresh the registry images list
        await fetchAll(false)
      } else {
        toast.error(res.data.message || 'Failed to start push')
      }
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to push image to registry')
    } finally {
      setPushing(false)
    }
  }

  const handleRefresh = () => {
    fetchAll(false)
  }

  const handleDeleteImage = async (imageName: string, tag: string) => {
    const imageTag = `${imageName}:${tag}`
    if (!confirm(`Delete ${imageTag} from registry? This cannot be undone.`)) {
      return
    }
    setDeleting(imageTag)
    try {
      const res = await registryApi.deleteImage(imageTag)
      if (res.data.success) {
        toast.success(res.data.message || `Deleted ${imageTag} from registry`)
        await fetchAll(false)
      } else {
        toast.error(res.data.message || 'Failed to delete image')
      }
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to delete image from registry')
    } finally {
      setDeleting(null)
    }
  }

  const handlePushAllMissing = async () => {
    if (hostImages.length === 0) {
      toast.warning('No host images available to push')
      return
    }

    setPushingAll(true)
    setPushProgress({ current: 0, total: 0 })

    try {
      // Check status of each host image to find ones that need pushing
      const imagesToPush: string[] = []

      for (const img of hostImages) {
        const imageTag = img.tags?.[0] || img.id
        if (!imageTag) continue

        try {
          const statusRes = await registryApi.getImageStatus(imageTag)
          if (statusRes.data.needs_push) {
            imagesToPush.push(imageTag)
          }
        } catch (err) {
          // If status check fails, assume it might need push
          console.warn(`Could not check status for ${imageTag}, skipping`)
        }
      }

      if (imagesToPush.length === 0) {
        toast.info('All host images are already in the registry')
        return
      }

      setPushProgress({ current: 0, total: imagesToPush.length })
      let successCount = 0
      let failCount = 0

      for (let i = 0; i < imagesToPush.length; i++) {
        const imageTag = imagesToPush[i]
        setPushProgress({ current: i + 1, total: imagesToPush.length })

        try {
          const res = await registryApi.pushImage(imageTag)
          if (res.data.operation_id) {
            successCount++
          } else {
            failCount++
          }
        } catch (err) {
          failCount++
          console.error(`Failed to push ${imageTag}:`, err)
        }
      }

      if (failCount === 0) {
        toast.success(`Successfully pushed ${successCount} images to registry`)
      } else if (successCount > 0) {
        toast.warning(`Pushed ${successCount} images, ${failCount} failed`)
      } else {
        toast.error(`Failed to push all ${failCount} images`)
      }

      await fetchAll(false)
    } catch (err: any) {
      toast.error('Failed to push images to registry')
    } finally {
      setPushingAll(false)
      setPushProgress(null)
    }
  }

  const isLoading = statsLoading && imagesLoading && hostImagesLoading

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
        <span className="ml-2 text-gray-600">Loading registry data...</span>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-medium text-gray-900">Local Docker Registry</h3>
          <p className="mt-1 text-sm text-gray-500">
            Manage the local registry used for distributing images to DinD ranges.
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="inline-flex items-center px-3 py-1.5 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
        >
          <RefreshCw className={clsx('h-4 w-4 mr-2', refreshing && 'animate-spin')} />
          Refresh
        </button>
      </div>

      {/* Stats Card */}
      <div className="bg-white rounded-lg shadow p-6">
        <h4 className="text-sm font-medium text-gray-900 mb-4 flex items-center gap-2">
          <Server className="h-4 w-4" />
          Registry Status
        </h4>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {/* Health Status */}
          <div className="flex items-center p-4 bg-gray-50 rounded-lg">
            <div className={clsx(
              'flex-shrink-0 h-10 w-10 rounded-full flex items-center justify-center',
              stats?.healthy ? 'bg-green-100' : 'bg-red-100'
            )}>
              {stats?.healthy ? (
                <CheckCircle2 className="h-5 w-5 text-green-600" />
              ) : (
                <XCircle className="h-5 w-5 text-red-600" />
              )}
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-900">Health</p>
              <p className={clsx(
                'text-lg font-bold',
                stats?.healthy ? 'text-green-600' : 'text-red-600'
              )}>
                {stats?.healthy ? 'Healthy' : 'Unhealthy'}
              </p>
            </div>
          </div>

          {/* Total Images */}
          <div className="flex items-center p-4 bg-gray-50 rounded-lg">
            <div className="flex-shrink-0 h-10 w-10 rounded-full bg-blue-100 flex items-center justify-center">
              <Box className="h-5 w-5 text-blue-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-900">Images</p>
              <p className="text-lg font-bold text-gray-900">
                {stats?.image_count ?? 0}
              </p>
            </div>
          </div>

          {/* Total Tags */}
          <div className="flex items-center p-4 bg-gray-50 rounded-lg">
            <div className="flex-shrink-0 h-10 w-10 rounded-full bg-purple-100 flex items-center justify-center">
              <Tag className="h-5 w-5 text-purple-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-900">Tags</p>
              <p className="text-lg font-bold text-gray-900">
                {stats?.tag_count ?? 0}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Manual Push Section */}
      <div className="bg-white rounded-lg shadow p-6">
        <h4 className="text-sm font-medium text-gray-900 mb-4 flex items-center gap-2">
          <Upload className="h-4 w-4" />
          Push Image to Registry
        </h4>
        <div className="flex items-end gap-4">
          <div className="flex-1">
            <label htmlFor="image-select" className="block text-sm font-medium text-gray-700 mb-1">
              Select Host Image
            </label>
            <select
              id="image-select"
              value={selectedImage}
              onChange={(e) => setSelectedImage(e.target.value)}
              disabled={hostImagesLoading || pushing}
              className="block w-full border border-gray-300 rounded-md shadow-sm px-3 py-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm disabled:bg-gray-100"
            >
              <option value="">-- Select an image --</option>
              {hostImages.map((img) => (
                <option key={img.id} value={img.tags?.[0] || img.id}>
                  {img.tags?.[0] || img.id.slice(0, 12)}
                </option>
              ))}
            </select>
            {hostImages.length === 0 && !hostImagesLoading && (
              <p className="mt-1 text-xs text-gray-500">
                No cached images found. Pull images from the Image Cache page first.
              </p>
            )}
          </div>
          <button
            onClick={handlePush}
            disabled={!selectedImage || pushing}
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {pushing ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Pushing...
              </>
            ) : (
              <>
                <Upload className="h-4 w-4 mr-2" />
                Push to Registry
              </>
            )}
          </button>
        </div>

        {/* Push All Missing Button */}
        <div className="mt-4 pt-4 border-t border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700">Bulk Push</p>
              <p className="text-xs text-gray-500">
                Push all host images that are not yet in the registry.
              </p>
            </div>
            <button
              onClick={handlePushAllMissing}
              disabled={pushingAll || hostImages.length === 0}
              className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {pushingAll ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  {pushProgress
                    ? `Pushing ${pushProgress.current}/${pushProgress.total}...`
                    : 'Checking...'}
                </>
              ) : (
                <>
                  <UploadCloud className="h-4 w-4 mr-2" />
                  Push All Missing
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Registry Images Table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h4 className="text-sm font-medium text-gray-900 flex items-center gap-2">
            <Database className="h-4 w-4" />
            Registry Images
            <span className="ml-2 px-2 py-0.5 bg-gray-100 text-gray-600 rounded-full text-xs">
              {images.length}
            </span>
          </h4>
        </div>
        {imagesLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
          </div>
        ) : images.length === 0 ? (
          <div className="text-center py-12">
            <Box className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-4 text-sm font-medium text-gray-900">No Images in Registry</h3>
            <p className="mt-2 text-sm text-gray-500">
              Push images from the host to make them available for DinD ranges.
            </p>
          </div>
        ) : (
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Image Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Tags
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {images.map((image, idx) => (
                <tr key={idx} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <Box className="h-5 w-5 text-gray-400 mr-3" />
                      <span className="text-sm font-medium text-gray-900 font-mono">
                        {image.name}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-wrap gap-1">
                      {image.tags.map((tag) => (
                        <span
                          key={tag}
                          className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800"
                        >
                          {tag}
                        </span>
                      ))}
                      {image.tags.length === 0 && (
                        <span className="text-xs text-gray-400">No tags</span>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex justify-end gap-2">
                      {image.tags.length > 0 ? (
                        image.tags.map((tag) => {
                          const imageTag = `${image.name}:${tag}`
                          const isDeleting = deleting === imageTag
                          return (
                            <button
                              key={tag}
                              onClick={() => handleDeleteImage(image.name, tag)}
                              disabled={isDeleting}
                              title={`Delete ${imageTag}`}
                              className="inline-flex items-center p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              {isDeleting ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <Trash2 className="h-4 w-4" />
                              )}
                            </button>
                          )
                        })
                      ) : (
                        <span className="text-xs text-gray-400">-</span>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
