// frontend/src/pages/ImageCache.tsx
import { useState, useEffect, useRef } from 'react'
import { cacheApi, DockerPullStatus, DockerBuildStatus, BuildableImage } from '../services/api'
import { useAuthStore } from '../stores/authStore'
import type {
  CachedImage,
  CacheStats,
  RecommendedImages,
  RecommendedImage,
  WindowsVersionsResponse,
  WindowsVersion,
  WindowsISODownloadStatus,
  CustomISOList,
  CustomISOStatusResponse,
  LinuxVersionsResponse,
  LinuxVersion,
  LinuxISODownloadStatus,
} from '../types'
import {
  HardDrive,
  Trash2,
  RefreshCw,
  Plus,
  Server,
  Monitor,
  AlertCircle,
  CheckCircle,
  Loader2,
  Info,
  Download,
  Link,
  Upload,
  Check,
  X,
  Terminal,
  Hammer,
  FolderEdit,
  Database,
} from 'lucide-react'
import clsx from 'clsx'
import { ConfirmDialog } from '../components/common/ConfirmDialog'
import { toast } from '../stores/toastStore'
import { FileBrowser } from '../components/files/FileBrowser'

type TabType = 'overview' | 'docker' | 'build' | 'files' | 'isos' | 'linux-isos' | 'custom-isos'

export default function ImageCache() {
  const { user } = useAuthStore()
  const isAdmin = user?.roles?.includes('admin') ?? false
  const [activeTab, setActiveTab] = useState<TabType>('overview')
  const [stats, setStats] = useState<CacheStats | null>(null)
  const [images, setImages] = useState<CachedImage[]>([])
  const [recommended, setRecommended] = useState<RecommendedImages | null>(null)
  const [windowsVersions, setWindowsVersions] = useState<WindowsVersionsResponse | null>(null)
  const [linuxVersions, setLinuxVersions] = useState<LinuxVersionsResponse | null>(null)
  const [customISOs, setCustomISOs] = useState<CustomISOList | null>(null)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  // Modal state for caching new images
  const [showCacheModal, setShowCacheModal] = useState(false)
  const [newImageName, setNewImageName] = useState('')
  const [selectedRecommended, setSelectedRecommended] = useState<string[]>([])

  // Custom ISO modal state
  const [showCustomISOModal, setShowCustomISOModal] = useState(false)
  const [customISOName, setCustomISOName] = useState('')
  const [customISOUrl, setCustomISOUrl] = useState('')

  // Upload modal state
  const [showUploadModal, setShowUploadModal] = useState<'windows' | 'linux' | 'custom' | null>(null)
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadVersion, setUploadVersion] = useState('')
  const [uploadName, setUploadName] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Download state for tracking Windows ISO downloads
  const [downloadStatus, setDownloadStatus] = useState<Record<string, WindowsISODownloadStatus>>({})
  // Download state for tracking Linux ISO downloads
  const [linuxDownloadStatus, setLinuxDownloadStatus] = useState<Record<string, LinuxISODownloadStatus>>({})
  // Download state for tracking Custom ISO downloads
  const [customISODownloadStatus, setCustomISODownloadStatus] = useState<Record<string, CustomISOStatusResponse>>({})
  // Pull state for tracking Docker image pulls
  const [dockerPullStatus, setDockerPullStatus] = useState<Record<string, DockerPullStatus>>({})
  // Build state for tracking Docker image builds
  const [buildableImages, setBuildableImages] = useState<BuildableImage[]>([])
  const [dockerBuildStatus, setDockerBuildStatus] = useState<Record<string, DockerBuildStatus>>({})

  // Delete confirmation state
  const [deleteConfirm, setDeleteConfirm] = useState<{
    type: 'docker' | 'windows-iso' | 'linux-iso' | 'custom-iso' | null
    name: string
    id?: string
    arch?: string  // For linux-iso architecture-specific delete
    isLoading: boolean
  }>({ type: null, name: '', isLoading: false })

  // Prune state
  const [isPruning, setIsPruning] = useState(false)
  const [isRefreshing, setIsRefreshing] = useState(false)

  const loadData = async () => {
    setLoading(true)
    setError(null)
    try {
      const [statsRes, imagesRes, recommendedRes, windowsRes, linuxRes, customISOsRes, buildableRes] = await Promise.all([
        cacheApi.getStats(),
        cacheApi.listImages(),
        cacheApi.getRecommendedImages(),
        cacheApi.getWindowsVersions(),
        cacheApi.getLinuxVersions(),
        cacheApi.listCustomISOs(),
        cacheApi.listBuildableImages(),
      ])
      setStats(statsRes.data)
      setImages(imagesRes.data)
      setRecommended(recommendedRes.data)
      setWindowsVersions(windowsRes.data)
      setLinuxVersions(linuxRes.data)
      setCustomISOs(customISOsRes.data)
      setBuildableImages(buildableRes.data.images || [])
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load cache data')
    } finally {
      setLoading(false)
    }
  }

  // Handler for refreshing all data
  const handleRefreshAll = async () => {
    setIsRefreshing(true)
    try {
      await loadData()
      toast.success('Cache data refreshed')
    } catch {
      toast.error('Failed to refresh data')
    } finally {
      setIsRefreshing(false)
    }
  }

  // Handler for pruning unused Docker images
  const handlePruneImages = async () => {
    setIsPruning(true)
    try {
      const result = await cacheApi.pruneImages()
      const { images_deleted, space_reclaimed_gb } = result.data
      if (images_deleted > 0) {
        toast.success(`Pruned ${images_deleted} image${images_deleted !== 1 ? 's' : ''}, reclaimed ${space_reclaimed_gb} GB`)
        await loadData() // Refresh to show updated state
      } else {
        toast.info('No unused images to prune')
      }
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to prune images')
    } finally {
      setIsPruning(false)
    }
  }

  // Store polling intervals so we can clear them
  const pollingIntervalsRef = useRef<Record<string, ReturnType<typeof setInterval>>>({})

  // Check for active downloads on mount and restore polling
  const checkActiveDownloads = async () => {
    // Check Linux downloads
    if (linuxVersions) {
      const allLinuxVersions = [
        ...(linuxVersions.desktop || []),
        ...(linuxVersions.server || []),
        ...(linuxVersions.security || []),
      ]
      for (const v of allLinuxVersions) {
        try {
          const statusRes = await cacheApi.getLinuxISODownloadStatus(v.version)
          if (statusRes.data.status === 'downloading') {
            setLinuxDownloadStatus(prev => ({ ...prev, [v.version]: statusRes.data }))
            // Start polling for this download
            startLinuxDownloadPolling(v.version)
          }
        } catch {
          // Ignore errors for individual status checks
        }
      }
    }

    // Check Windows downloads
    if (windowsVersions) {
      const allWindowsVersions = [
        ...(windowsVersions.desktop || []),
        ...(windowsVersions.server || []),
        ...(windowsVersions.legacy || []),
      ]
      for (const v of allWindowsVersions) {
        try {
          const statusRes = await cacheApi.getWindowsISODownloadStatus(v.version)
          if (statusRes.data.status === 'downloading') {
            setDownloadStatus(prev => ({ ...prev, [v.version]: statusRes.data }))
            // Start polling for this download
            startWindowsDownloadPolling(v.version)
          }
        } catch {
          // Ignore errors for individual status checks
        }
      }
    }

    // Check Custom ISO downloads
    if (customISOs) {
      for (const iso of customISOs.isos) {
        try {
          const statusRes = await cacheApi.getCustomISOStatus(iso.filename)
          if (statusRes.data.status === 'downloading') {
            setCustomISODownloadStatus(prev => ({ ...prev, [iso.filename]: statusRes.data }))
            // Start polling for this download
            startCustomISODownloadPolling(iso.filename)
          }
        } catch {
          // Ignore errors for individual status checks
        }
      }
    }

    // Check active Docker pulls
    try {
      const activePullsRes = await cacheApi.getActivePulls()
      for (const pull of activePullsRes.data.pulls) {
        if (pull.image) {
          const imageKey = pull.image.replace(/\//g, '_').replace(/:/g, '_')
          setDockerPullStatus(prev => ({ ...prev, [imageKey]: pull }))
          startDockerPullPolling(imageKey, pull.image)
        }
      }
    } catch {
      // Ignore errors for active pull check
    }
  }

  const startLinuxDownloadPolling = (version: string) => {
    // Clear any existing interval for this version
    if (pollingIntervalsRef.current[`linux-${version}`]) {
      clearInterval(pollingIntervalsRef.current[`linux-${version}`])
    }

    const pollInterval = setInterval(async () => {
      try {
        const statusRes = await cacheApi.getLinuxISODownloadStatus(version)
        setLinuxDownloadStatus(prev => ({ ...prev, [version]: statusRes.data }))

        if (statusRes.data.status === 'completed' || statusRes.data.status === 'failed') {
          clearInterval(pollInterval)
          delete pollingIntervalsRef.current[`linux-${version}`]

          if (statusRes.data.status === 'completed') {
            setSuccess(`Downloaded Linux ISO: ${version}`)
            await loadData()
          } else if (statusRes.data.error) {
            setError(`Download failed: ${statusRes.data.error}`)
          }

          // Clear download status after a delay
          setTimeout(() => {
            setLinuxDownloadStatus(prev => {
              const newStatus = { ...prev }
              delete newStatus[version]
              return newStatus
            })
          }, 5000)
        }
      } catch {
        clearInterval(pollInterval)
        delete pollingIntervalsRef.current[`linux-${version}`]
      }
    }, 2000)

    pollingIntervalsRef.current[`linux-${version}`] = pollInterval
  }

  const startWindowsDownloadPolling = (version: string) => {
    // Clear any existing interval for this version
    if (pollingIntervalsRef.current[`windows-${version}`]) {
      clearInterval(pollingIntervalsRef.current[`windows-${version}`])
    }

    const pollInterval = setInterval(async () => {
      try {
        const statusRes = await cacheApi.getWindowsISODownloadStatus(version)
        setDownloadStatus(prev => ({ ...prev, [version]: statusRes.data }))

        if (statusRes.data.status === 'completed' || statusRes.data.status === 'failed') {
          clearInterval(pollInterval)
          delete pollingIntervalsRef.current[`windows-${version}`]

          if (statusRes.data.status === 'completed') {
            setSuccess(`Downloaded Windows ISO: ${version}`)
            await loadData()
          } else if (statusRes.data.error) {
            setError(`Download failed: ${statusRes.data.error}`)
          }

          // Clear download status after a delay
          setTimeout(() => {
            setDownloadStatus(prev => {
              const newStatus = { ...prev }
              delete newStatus[version]
              return newStatus
            })
          }, 5000)
        }
      } catch {
        clearInterval(pollInterval)
        delete pollingIntervalsRef.current[`windows-${version}`]
      }
    }, 2000)

    pollingIntervalsRef.current[`windows-${version}`] = pollInterval
  }

  const startCustomISODownloadPolling = (filename: string) => {
    // Clear any existing interval for this filename
    if (pollingIntervalsRef.current[`custom-${filename}`]) {
      clearInterval(pollingIntervalsRef.current[`custom-${filename}`])
    }

    const pollInterval = setInterval(async () => {
      try {
        const statusRes = await cacheApi.getCustomISOStatus(filename)
        setCustomISODownloadStatus(prev => ({ ...prev, [filename]: statusRes.data }))

        if (statusRes.data.status === 'completed' || statusRes.data.status === 'failed') {
          clearInterval(pollInterval)
          delete pollingIntervalsRef.current[`custom-${filename}`]

          if (statusRes.data.status === 'completed') {
            setSuccess(`Downloaded custom ISO: ${statusRes.data.name || filename}`)
            await loadData()
          } else if (statusRes.data.error) {
            setError(`Download failed: ${statusRes.data.error}`)
          }

          // Clear download status after a delay
          setTimeout(() => {
            setCustomISODownloadStatus(prev => {
              const newStatus = { ...prev }
              delete newStatus[filename]
              return newStatus
            })
          }, 5000)
        }
      } catch {
        clearInterval(pollInterval)
        delete pollingIntervalsRef.current[`custom-${filename}`]
      }
    }, 2000)

    pollingIntervalsRef.current[`custom-${filename}`] = pollInterval
  }

  const startDockerPullPolling = (imageKey: string, imageName: string) => {
    // Clear any existing interval for this image
    if (pollingIntervalsRef.current[`docker-${imageKey}`]) {
      clearInterval(pollingIntervalsRef.current[`docker-${imageKey}`])
    }

    const pollInterval = setInterval(async () => {
      try {
        const statusRes = await cacheApi.getPullStatus(imageKey)
        setDockerPullStatus(prev => ({ ...prev, [imageKey]: statusRes.data }))

        if (statusRes.data.status === 'completed' || statusRes.data.status === 'failed' || statusRes.data.status === 'cancelled') {
          clearInterval(pollInterval)
          delete pollingIntervalsRef.current[`docker-${imageKey}`]

          if (statusRes.data.status === 'completed') {
            setSuccess(`Pulled Docker image: ${imageName}`)
            await loadData()
          } else if (statusRes.data.status === 'failed' && statusRes.data.error) {
            setError(`Pull failed: ${statusRes.data.error}`)
          }

          // Clear pull status after a delay
          setTimeout(() => {
            setDockerPullStatus(prev => {
              const newStatus = { ...prev }
              delete newStatus[imageKey]
              return newStatus
            })
          }, 5000)
        }
      } catch {
        clearInterval(pollInterval)
        delete pollingIntervalsRef.current[`docker-${imageKey}`]
      }
    }, 1000) // Poll every second for Docker pulls (they can be fast)

    pollingIntervalsRef.current[`docker-${imageKey}`] = pollInterval
  }

  const handlePullDockerImage = async (image: string) => {
    const imageKey = image.replace(/\//g, '_').replace(/:/g, '_')
    setActionLoading(`pull-${imageKey}`)
    setError(null)

    try {
      const res = await cacheApi.pullImage(image)

      if (res.data.status === 'already_cached') {
        setSuccess(`${image} is already cached`)
        setActionLoading(null)
        return
      }

      if (res.data.status === 'already_pulling') {
        setSuccess(`${image} is already being pulled`)
        setActionLoading(null)
        return
      }

      // Start polling for pull status
      setDockerPullStatus(prev => ({
        ...prev,
        [imageKey]: { status: 'pulling', image, progress_percent: 0 }
      }))
      startDockerPullPolling(imageKey, image)
      setSuccess(`Started pulling ${image}`)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to start pull')
    } finally {
      setActionLoading(null)
    }
  }

  const handleCancelDockerPull = async (imageKey: string) => {
    setActionLoading(`cancel-docker-${imageKey}`)
    setError(null)
    try {
      await cacheApi.cancelPull(imageKey)
      setSuccess(`Cancelled pull`)
      setDockerPullStatus(prev => {
        const newStatus = { ...prev }
        delete newStatus[imageKey]
        return newStatus
      })
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to cancel pull')
    } finally {
      setActionLoading(null)
    }
  }

  // ============ Docker Image Build Functions ============

  const startDockerBuildPolling = (buildKey: string, imageName: string) => {
    // Clear any existing polling for this build
    if (pollingIntervalsRef.current[`build-${buildKey}`]) {
      clearInterval(pollingIntervalsRef.current[`build-${buildKey}`])
    }

    const pollInterval = setInterval(async () => {
      try {
        const statusRes = await cacheApi.getBuildStatus(buildKey)

        setDockerBuildStatus(prev => ({
          ...prev,
          [buildKey]: statusRes.data
        }))

        // Stop polling if build is complete, failed, or cancelled
        if (['completed', 'failed', 'cancelled'].includes(statusRes.data.status)) {
          clearInterval(pollInterval)
          delete pollingIntervalsRef.current[`build-${buildKey}`]

          if (statusRes.data.status === 'completed') {
            toast.success(`Built ${imageName} successfully`)
            await loadData()
          } else if (statusRes.data.status === 'failed' && statusRes.data.error) {
            toast.error(`Build failed: ${statusRes.data.error}`)
          }

          // Clear build status after a delay
          setTimeout(() => {
            setDockerBuildStatus(prev => {
              const newStatus = { ...prev }
              delete newStatus[buildKey]
              return newStatus
            })
          }, 10000) // Keep visible for 10s after completion
        }
      } catch {
        clearInterval(pollInterval)
        delete pollingIntervalsRef.current[`build-${buildKey}`]
      }
    }, 2000) // Poll every 2 seconds for builds (they take longer)

    pollingIntervalsRef.current[`build-${buildKey}`] = pollInterval
  }

  const handleBuildImage = async (imageName: string, noCache = false) => {
    const buildKey = `${imageName}_latest`
    setActionLoading(`build-${buildKey}`)
    setError(null)

    try {
      const res = await cacheApi.buildImage({
        image_name: imageName,
        tag: 'latest',
        no_cache: noCache,
      })

      if (res.data.status === 'already_building') {
        toast.info(`${imageName} is already being built`)
        setActionLoading(null)
        return
      }

      // Start polling for build status
      setDockerBuildStatus(prev => ({
        ...prev,
        [buildKey]: {
          status: 'building',
          image_name: imageName,
          tag: 'latest',
          full_tag: `cyroid/${imageName}:latest`,
          progress_percent: 0,
          current_step: 0,
          total_steps: 0,
          current_step_name: 'Starting build...',
        }
      }))
      startDockerBuildPolling(buildKey, imageName)
      toast.success(`Started building cyroid/${imageName}:latest`)
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to start build')
    } finally {
      setActionLoading(null)
    }
  }

  const handleCancelDockerBuild = async (buildKey: string) => {
    setActionLoading(`cancel-build-${buildKey}`)
    setError(null)
    try {
      await cacheApi.cancelBuild(buildKey)
      toast.success(`Cancelled build`)
      setDockerBuildStatus(prev => {
        const newStatus = { ...prev }
        delete newStatus[buildKey]
        return newStatus
      })
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to cancel build')
    } finally {
      setActionLoading(null)
    }
  }

  // Check for active builds on mount
  const checkActiveBuilds = async () => {
    try {
      const res = await cacheApi.getActiveBuilds()
      if (res.data.builds && res.data.builds.length > 0) {
        for (const build of res.data.builds) {
          if (build.build_key && build.status === 'building') {
            setDockerBuildStatus(prev => ({
              ...prev,
              [build.build_key!]: build
            }))
            startDockerBuildPolling(build.build_key, build.image_name || '')
          }
        }
      }
    } catch {
      // Ignore errors checking for active builds
    }
  }

  useEffect(() => {
    loadData()
    checkActiveBuilds()
  }, [])

  // Check for active downloads after data is loaded
  useEffect(() => {
    if (linuxVersions || windowsVersions || customISOs) {
      checkActiveDownloads()
    }
  }, [linuxVersions, windowsVersions, customISOs])

  // Cleanup polling intervals on unmount
  useEffect(() => {
    return () => {
      Object.values(pollingIntervalsRef.current).forEach(clearInterval)
    }
  }, [])

  const handleCacheBatch = async () => {
    if (selectedRecommended.length === 0 && !newImageName) return

    const imagesToCache = [...selectedRecommended]
    if (newImageName) imagesToCache.push(newImageName)

    setActionLoading('batch')
    setError(null)
    try {
      await cacheApi.cacheBatchImages(imagesToCache)
      setSuccess(`Started caching ${imagesToCache.length} images in background`)
      setShowCacheModal(false)
      setSelectedRecommended([])
      setNewImageName('')
      setTimeout(() => loadData(), 2000)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to start batch caching')
    } finally {
      setActionLoading(null)
    }
  }

  const handleRemoveImage = (imageId: string, tag: string) => {
    setDeleteConfirm({ type: 'docker', name: tag, id: imageId, isLoading: false })
  }

  const handleDownloadCustomISO = async () => {
    if (!customISOName || !customISOUrl) return

    setActionLoading('custom-iso-download')
    setError(null)
    try {
      const res = await cacheApi.downloadCustomISO(customISOName, customISOUrl)
      const filename = res.data.filename

      // Start polling for download status
      setCustomISODownloadStatus(prev => ({
        ...prev,
        [filename]: { status: 'downloading', filename, name: customISOName, progress_gb: 0 }
      }))
      startCustomISODownloadPolling(filename)

      setSuccess(`Started downloading ${customISOName}`)
      setShowCustomISOModal(false)
      setCustomISOName('')
      setCustomISOUrl('')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to start ISO download')
    } finally {
      setActionLoading(null)
    }
  }

  const handleCancelCustomISODownload = async (filename: string) => {
    setActionLoading(`cancel-custom-${filename}`)
    setError(null)
    try {
      await cacheApi.cancelCustomISODownload(filename)
      setSuccess(`Cancelled download for ${filename}`)
      setCustomISODownloadStatus(prev => {
        const newStatus = { ...prev }
        delete newStatus[filename]
        return newStatus
      })
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to cancel download')
    } finally {
      setActionLoading(null)
    }
  }

  const handleDeleteCustomISO = (filename: string, name: string) => {
    setDeleteConfirm({ type: 'custom-iso', name, id: filename, isLoading: false })
  }

  const handleDeleteWindowsISO = (version: string, name: string, arch?: 'x86_64' | 'arm64') => {
    const archSuffix = arch ? ` (${arch})` : ''
    setDeleteConfirm({ type: 'windows-iso', name: `${name}${archSuffix}`, id: version, arch, isLoading: false })
  }

  const handleDownloadWindowsISO = async (version: WindowsVersion, customUrl?: string, arch?: 'x86_64' | 'arm64') => {
    // Use architecture-specific key for tracking
    const downloadKey = arch ? `${version.version}-${arch}` : version.version
    setActionLoading(`download-windows-${downloadKey}`)
    setError(null)

    try {
      const res = await cacheApi.downloadWindowsISO(version.version, customUrl, arch)

      // Handle no direct download available
      if (res.data.status === 'no_direct_download') {
        setError(res.data.message || 'No direct download available for this version')
        setActionLoading(null)
        return
      }

      // Start polling for download status
      setDownloadStatus(prev => ({
        ...prev,
        [downloadKey]: { status: 'downloading', version: version.version, progress_gb: 0 }
      }))

      // Poll for status
      const pollInterval = setInterval(async () => {
        try {
          const statusRes = await cacheApi.getWindowsISODownloadStatus(version.version, arch)
          setDownloadStatus(prev => ({
            ...prev,
            [downloadKey]: statusRes.data
          }))

          if (statusRes.data.status === 'completed' || statusRes.data.status === 'failed') {
            clearInterval(pollInterval)
            setActionLoading(null)

            if (statusRes.data.status === 'completed') {
              const archLabel = arch ? ` (${arch})` : ''
              setSuccess(`Downloaded ${version.name}${archLabel} ISO successfully!`)
              await loadData()
            } else if (statusRes.data.error) {
              setError(`Download failed: ${statusRes.data.error}`)
            }

            // Clear download status after a delay
            setTimeout(() => {
              setDownloadStatus(prev => {
                const newStatus = { ...prev }
                delete newStatus[downloadKey]
                return newStatus
              })
            }, 5000)
          }
        } catch (err) {
          clearInterval(pollInterval)
          setActionLoading(null)
        }
      }, 2000) // Poll every 2 seconds

    } catch (err: any) {
      const detail = err.response?.data?.detail
      if (typeof detail === 'object' && detail.status === 'no_direct_download') {
        // Show error with download page link
        const msg = detail.message || 'No direct download available'
        if (detail.download_page) {
          setError(`${msg}. Visit the download page to get the ISO manually.`)
        } else {
          setError(msg)
        }
      } else {
        setError(typeof detail === 'string' ? detail : 'Failed to start download')
      }
      setActionLoading(null)
    }
  }

  const handleDownloadLinuxISO = async (version: LinuxVersion, customUrl?: string, arch?: string) => {
    // Use architecture-specific key for tracking
    const downloadKey = arch ? `${version.version}-${arch}` : version.version
    setActionLoading(`download-linux-${downloadKey}`)
    setError(null)

    try {
      const res = await cacheApi.downloadLinuxISO(version.version, customUrl, arch)

      // Handle no direct download available
      if (res.data.status === 'no_direct_download') {
        setError(res.data.message || 'No direct download available for this distribution')
        setActionLoading(null)
        return
      }

      // Start polling for download status
      setLinuxDownloadStatus(prev => ({
        ...prev,
        [downloadKey]: { status: 'downloading', version: version.version, progress_gb: 0 }
      }))

      // Poll for status
      const pollInterval = setInterval(async () => {
        try {
          const statusRes = await cacheApi.getLinuxISODownloadStatus(version.version, arch)
          setLinuxDownloadStatus(prev => ({
            ...prev,
            [downloadKey]: statusRes.data
          }))

          if (statusRes.data.status === 'completed' || statusRes.data.status === 'failed') {
            clearInterval(pollInterval)
            setActionLoading(null)

            if (statusRes.data.status === 'completed') {
              setSuccess(`Downloaded ${version.name} (${arch || 'default'}) ISO successfully!`)
              await loadData()
            } else if (statusRes.data.error) {
              setError(`Download failed: ${statusRes.data.error}`)
            }

            // Clear download status after a delay
            setTimeout(() => {
              setLinuxDownloadStatus(prev => {
                const newStatus = { ...prev }
                delete newStatus[downloadKey]
                return newStatus
              })
            }, 5000)
          }
        } catch (err) {
          clearInterval(pollInterval)
          setActionLoading(null)
        }
      }, 2000) // Poll every 2 seconds

    } catch (err: any) {
      const detail = err.response?.data?.detail
      if (typeof detail === 'object' && detail.status === 'no_direct_download') {
        setError(detail.message || 'No direct download available')
      } else {
        setError(typeof detail === 'string' ? detail : 'Failed to start download')
      }
      setActionLoading(null)
    }
  }

  const handleDeleteLinuxISO = (version: string, arch?: string) => {
    const displayName = arch ? `${version} (${arch})` : version
    const id = arch ? `${version}-${arch}` : version
    setDeleteConfirm({ type: 'linux-iso', name: displayName, id: id, arch: arch, isLoading: false })
  }

  const confirmDelete = async () => {
    if (!deleteConfirm.type) return
    setDeleteConfirm(prev => ({ ...prev, isLoading: true }))
    setError(null)

    try {
      switch (deleteConfirm.type) {
        case 'docker':
          if (deleteConfirm.id) {
            await cacheApi.removeImage(deleteConfirm.id)
            toast.success(`Removed ${deleteConfirm.name}`)
          }
          break
        case 'custom-iso':
          if (deleteConfirm.id) {
            await cacheApi.deleteCustomISO(deleteConfirm.id)
            setCustomISODownloadStatus(prev => {
              const newStatus = { ...prev }
              delete newStatus[deleteConfirm.id!]
              return newStatus
            })
            toast.success(`Deleted custom ISO: ${deleteConfirm.name}`)
          }
          break
        case 'windows-iso':
          if (deleteConfirm.id) {
            await cacheApi.deleteWindowsISO(deleteConfirm.id, deleteConfirm.arch as 'x86_64' | 'arm64' | undefined)
            // Clear download status if exists
            const downloadKey = deleteConfirm.arch ? `${deleteConfirm.id}-${deleteConfirm.arch}` : deleteConfirm.id
            setDownloadStatus(prev => {
              const newStatus = { ...prev }
              delete newStatus[downloadKey]
              return newStatus
            })
            toast.success(`Deleted Windows ISO: ${deleteConfirm.name}`)
          }
          break
        case 'linux-iso':
          if (deleteConfirm.id) {
            // Extract version from id (format: version or version-arch)
            const version = deleteConfirm.arch ? deleteConfirm.id.replace(`-${deleteConfirm.arch}`, '') : deleteConfirm.id
            await cacheApi.deleteLinuxISO(version, deleteConfirm.arch)
            setLinuxDownloadStatus(prev => {
              const newStatus = { ...prev }
              delete newStatus[deleteConfirm.id!]
              return newStatus
            })
            toast.success(`Deleted Linux ISO: ${deleteConfirm.name}`)
          }
          break
      }
      setDeleteConfirm({ type: null, name: '', isLoading: false })
      await loadData()
    } catch (err: any) {
      setDeleteConfirm({ type: null, name: '', isLoading: false })
      toast.error(err.response?.data?.detail || `Failed to delete ${deleteConfirm.name}`)
    }
  }

  const handleCancelLinuxDownload = async (version: string, arch?: string) => {
    const downloadKey = arch ? `${version}-${arch}` : version
    setActionLoading(`cancel-linux-${downloadKey}`)
    setError(null)
    try {
      await cacheApi.cancelLinuxISODownload(version, arch)
      setSuccess(`Cancelled download for ${version}${arch ? ` (${arch})` : ''}`)
      setLinuxDownloadStatus(prev => {
        const newStatus = { ...prev }
        delete newStatus[downloadKey]
        return newStatus
      })
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to cancel download')
    } finally {
      setActionLoading(null)
    }
  }

  const handleCancelWindowsDownload = async (version: string, arch?: 'x86_64' | 'arm64') => {
    const downloadKey = arch ? `${version}-${arch}` : version
    setActionLoading(`cancel-windows-${downloadKey}`)
    setError(null)
    try {
      await cacheApi.cancelWindowsISODownload(version, arch)
      setSuccess(`Cancelled download for ${version}${arch ? ` (${arch})` : ''}`)
      setDownloadStatus(prev => {
        const newStatus = { ...prev }
        delete newStatus[downloadKey]
        return newStatus
      })
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to cancel download')
    } finally {
      setActionLoading(null)
    }
  }

  const handleUploadISO = async () => {
    if (!uploadFile) return

    setActionLoading('upload')
    setError(null)
    try {
      if (showUploadModal === 'windows') {
        if (!uploadVersion) {
          setError('Please select a Windows version')
          setActionLoading(null)
          return
        }
        await cacheApi.uploadWindowsISO(uploadFile, uploadVersion)
        setSuccess(`Uploaded Windows ${uploadVersion} ISO`)
      } else if (showUploadModal === 'linux') {
        if (!uploadVersion) {
          setError('Please select a Linux distribution')
          setActionLoading(null)
          return
        }
        await cacheApi.uploadLinuxISO(uploadFile, uploadVersion)
        setSuccess(`Uploaded Linux ${uploadVersion} ISO`)
      } else {
        if (!uploadName) {
          setError('Please enter a name for the ISO')
          setActionLoading(null)
          return
        }
        await cacheApi.uploadCustomISO(uploadFile, uploadName)
        setSuccess(`Uploaded custom ISO: ${uploadName}`)
      }
      setShowUploadModal(null)
      setUploadFile(null)
      setUploadVersion('')
      setUploadName('')
      await loadData()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to upload ISO')
    } finally {
      setActionLoading(null)
    }
  }

  const tabs = [
    { id: 'overview' as const, name: 'Overview', icon: HardDrive },
    { id: 'docker' as const, name: 'Docker Images', icon: Server },
    { id: 'build' as const, name: 'Build Images', icon: Hammer },
    { id: 'files' as const, name: 'Image Files', icon: FolderEdit },
    { id: 'isos' as const, name: 'Windows ISOs', icon: Monitor },
    { id: 'linux-isos' as const, name: 'Linux ISOs', icon: Terminal },
    { id: 'custom-isos' as const, name: 'Custom ISOs', icon: Download },
  ]

  // Categorize cached Docker images
  const categorizeImages = () => {
    const desktop: CachedImage[] = []       // GUI desktop environments with VNC/RDP/web access
    const server: CachedImage[] = []        // Headless server/CLI images
    const services: CachedImage[] = []      // Purpose-built service containers
    const other: CachedImage[] = []

    // Patterns for categorization
    const servicePatterns = ['nginx', 'httpd', 'apache', 'mysql', 'postgres', 'redis', 'mongo', 'mariadb', 'elasticsearch', 'rabbitmq', 'memcached']
    // Desktop = images with GUI/VNC/RDP/web access
    const desktopPatterns = ['webtop', 'vnc', 'xfce', 'kde', 'lxde', 'xrdp', 'kasm', 'guacamole', 'x11', 'desktop']
    // Server/CLI = headless base OS images
    const serverPatterns = ['alpine', 'centos', 'rocky', 'server', 'kali', 'fedora:', 'debian:', 'ubuntu:']

    images.forEach(img => {
      const tags = img.tags.join(' ').toLowerCase()
      if (tags.includes('dockur/windows') || tags.includes('windows')) {
        // Skip Windows images in Docker section
        return
      }
      if (servicePatterns.some(p => tags.includes(p))) {
        services.push(img)
      } else if (desktopPatterns.some(p => tags.includes(p))) {
        desktop.push(img)
      } else if (serverPatterns.some(p => tags.includes(p))) {
        server.push(img)
      } else {
        other.push(img)
      }
    })

    return { desktop, server, services, other }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    )
  }

  const categorizedImages = categorizeImages()

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Image Cache</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage cached Docker images, Windows ISOs, and golden images for offline deployment
          </p>
        </div>
        <button
          onClick={loadData}
          className="inline-flex items-center px-3 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
        >
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </button>
      </div>

      {/* Alerts */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4 flex items-start">
          <AlertCircle className="h-5 w-5 text-red-500 mt-0.5 mr-3" />
          <div>
            <p className="text-sm text-red-700">{error}</p>
          </div>
          <button onClick={() => setError(null)} className="ml-auto text-red-500 hover:text-red-700">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}
      {success && (
        <div className="bg-green-50 border border-green-200 rounded-md p-4 flex items-start">
          <CheckCircle className="h-5 w-5 text-green-500 mt-0.5 mr-3" />
          <div>
            <p className="text-sm text-green-700">{success}</p>
          </div>
          <button onClick={() => setSuccess(null)} className="ml-auto text-green-500 hover:text-green-700">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={clsx(
                'flex items-center py-4 px-1 border-b-2 font-medium text-sm',
                activeTab === tab.id
                  ? 'border-primary-500 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              )}
            >
              <tab.icon className="h-5 w-5 mr-2" />
              {tab.name}
            </button>
          ))}
        </nav>
      </div>

      {/* Overview Tab */}
      {activeTab === 'overview' && stats && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center">
                <Server className="h-8 w-8 text-blue-500" />
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-500">Docker Images</p>
                  <p className="text-2xl font-semibold text-gray-900">{stats.docker_images.count}</p>
                  <p className="text-sm text-gray-500">{stats.docker_images.total_size_gb} GB</p>
                </div>
              </div>
            </div>
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center">
                <Monitor className="h-8 w-8 text-purple-500" />
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-500">Windows ISOs</p>
                  <p className="text-2xl font-semibold text-gray-900">
                    {windowsVersions?.cached_count || 0}/{windowsVersions?.total_count || 17}
                  </p>
                  <p className="text-sm text-gray-500">{stats.windows_isos.total_size_gb} GB cached</p>
                </div>
              </div>
            </div>
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center">
                <Terminal className="h-8 w-8 text-green-500" />
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-500">Linux ISOs</p>
                  <p className="text-2xl font-semibold text-gray-900">
                    {linuxVersions?.cached_count || 0}/{linuxVersions?.total_count || 0}
                  </p>
                  <p className="text-sm text-gray-500">
                    {linuxVersions?.host_arch === 'arm64' ? 'ARM64' : 'x86_64'} host
                  </p>
                </div>
              </div>
            </div>
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center">
                <Download className="h-8 w-8 text-teal-500" />
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-500">Custom ISOs</p>
                  <p className="text-2xl font-semibold text-gray-900">
                    {customISOs?.total_count || 0}
                  </p>
                  <p className="text-sm text-gray-500">uploaded</p>
                </div>
              </div>
            </div>
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center">
                <HardDrive className="h-8 w-8 text-orange-500" />
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-500">Total Cache</p>
                  <p className="text-2xl font-semibold text-gray-900">{stats.total_cache_size_gb} GB</p>
                </div>
              </div>
            </div>
          </div>

          {/* Quick Actions Section */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-medium text-gray-900">Quick Actions</h3>
              {/* Active Operations Indicator */}
              {(Object.keys(dockerPullStatus).some(k => dockerPullStatus[k].status === 'pulling') ||
                Object.keys(dockerBuildStatus).some(k => dockerBuildStatus[k].status === 'building') ||
                Object.keys(downloadStatus).some(k => downloadStatus[k].status === 'downloading') ||
                Object.keys(linuxDownloadStatus).some(k => linuxDownloadStatus[k].status === 'downloading') ||
                Object.keys(customISODownloadStatus).some(k => customISODownloadStatus[k].status === 'downloading')) && (
                <div className="flex items-center text-sm text-blue-600">
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  <span>
                    {[
                      Object.values(dockerPullStatus).filter(s => s.status === 'pulling').length > 0 &&
                        `${Object.values(dockerPullStatus).filter(s => s.status === 'pulling').length} pulling`,
                      Object.values(dockerBuildStatus).filter(s => s.status === 'building').length > 0 &&
                        `${Object.values(dockerBuildStatus).filter(s => s.status === 'building').length} building`,
                      Object.values(downloadStatus).filter(s => s.status === 'downloading').length > 0 &&
                        `${Object.values(downloadStatus).filter(s => s.status === 'downloading').length} downloading`,
                      Object.values(linuxDownloadStatus).filter(s => s.status === 'downloading').length > 0 &&
                        `${Object.values(linuxDownloadStatus).filter(s => s.status === 'downloading').length} Linux ISOs`,
                      Object.values(customISODownloadStatus).filter(s => s.status === 'downloading').length > 0 &&
                        `${Object.values(customISODownloadStatus).filter(s => s.status === 'downloading').length} custom ISOs`,
                    ].filter(Boolean).join(', ')}
                  </span>
                </div>
              )}
            </div>
            <div className="flex flex-wrap gap-3">
              {/* Refresh All Button */}
              <button
                onClick={handleRefreshAll}
                disabled={isRefreshing}
                className="inline-flex items-center px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 disabled:opacity-50"
              >
                {isRefreshing ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4 mr-2" />
                )}
                Refresh All
              </button>
              {isAdmin && (
                <>
                  <button
                    onClick={() => setShowCacheModal(true)}
                    className="inline-flex items-center px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700"
                  >
                    <Plus className="h-4 w-4 mr-2" />
                    Cache Docker Images
                  </button>
                  <button
                    onClick={() => setShowUploadModal('windows')}
                    className="inline-flex items-center px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700"
                  >
                    <Upload className="h-4 w-4 mr-2" />
                    Upload Windows ISO
                  </button>
                  <button
                    onClick={() => setShowUploadModal('linux')}
                    className="inline-flex items-center px-4 py-2 bg-emerald-600 text-white rounded-md hover:bg-emerald-700"
                  >
                    <Upload className="h-4 w-4 mr-2" />
                    Upload Linux ISO
                  </button>
                  <button
                    onClick={() => setShowUploadModal('custom')}
                    className="inline-flex items-center px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700"
                  >
                    <Upload className="h-4 w-4 mr-2" />
                    Upload Custom ISO
                  </button>
                  <button
                    onClick={handlePruneImages}
                    disabled={isPruning}
                    className="inline-flex items-center px-4 py-2 bg-orange-600 text-white rounded-md hover:bg-orange-700 disabled:opacity-50"
                    title="Remove dangling and unused Docker images"
                  >
                    {isPruning ? (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <Trash2 className="h-4 w-4 mr-2" />
                    )}
                    Prune Unused Images
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Docker Images Tab */}
      {activeTab === 'docker' && recommended && (
        <div className="space-y-6">
          <div className="flex justify-between items-center">
            <div>
              <h3 className="text-lg font-medium text-gray-900">Docker Images</h3>
              <p className="text-sm text-gray-500">
                {images.length} images cached
              </p>
            </div>
            {isAdmin && (
              <button
                onClick={() => setShowCacheModal(true)}
                className="inline-flex items-center px-3 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 text-sm"
              >
                <Plus className="h-4 w-4 mr-2" />
                Custom Image
              </button>
            )}
          </div>

          {/* Info */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex">
              <Info className="h-5 w-5 text-blue-500 mt-0.5 mr-3" />
              <div>
                <h4 className="text-sm font-medium text-blue-800">Docker Image Cache</h4>
                <p className="mt-1 text-sm text-blue-700">
                  Recommended images for cyber range operations. Cached images deploy instantly without network download.
                </p>
              </div>
            </div>
          </div>

          {/* Desktop Images Section */}
          <DockerImageSection
            title="Desktop"
            description="Images with GUI desktop environment (VNC/RDP/Web)"
            images={recommended.desktop}
            cachedImages={images}
            icon={Monitor}
            colorClass="blue"
            onPull={handlePullDockerImage}
            onRemove={handleRemoveImage}
            onCancel={handleCancelDockerPull}
                        pullStatus={dockerPullStatus}
            actionLoading={actionLoading}
            isAdmin={isAdmin}
          />

          {/* Server/CLI Images Section */}
          <DockerImageSection
            title="Server/CLI"
            description="Headless server and CLI images"
            images={recommended.server}
            cachedImages={images}
            icon={Server}
            colorClass="purple"
            onPull={handlePullDockerImage}
            onRemove={handleRemoveImage}
            onCancel={handleCancelDockerPull}
                        pullStatus={dockerPullStatus}
            actionLoading={actionLoading}
            isAdmin={isAdmin}
          />

          {/* Services Images Section */}
          <DockerImageSection
            title="Services"
            description="Purpose-built service containers (databases, web servers, etc.)"
            images={recommended.services}
            cachedImages={images}
            icon={Database}
            colorClass="green"
            onPull={handlePullDockerImage}
            onRemove={handleRemoveImage}
            onCancel={handleCancelDockerPull}
                        pullStatus={dockerPullStatus}
            actionLoading={actionLoading}
            isAdmin={isAdmin}
          />

          {/* Cached Desktop Images (not in recommended list) - Issue #63 */}
          {categorizedImages.desktop.length > 0 && (
            <div className="bg-white shadow rounded-lg overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-200 bg-blue-50">
                <h4 className="text-sm font-medium text-blue-800 flex items-center">
                  <Monitor className="h-4 w-4 mr-2" />
                  Cached Desktop Images ({categorizedImages.desktop.length})
                </h4>
                <p className="text-xs text-blue-600 mt-1">Cached desktop images with GUI/VNC access</p>
              </div>
              <ImageTable images={categorizedImages.desktop} onRemove={handleRemoveImage} actionLoading={actionLoading} isAdmin={isAdmin} />
            </div>
          )}

          {/* Cached Server/CLI Images (not in recommended list) - Issue #63 */}
          {categorizedImages.server.length > 0 && (
            <div className="bg-white shadow rounded-lg overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-200 bg-purple-50">
                <h4 className="text-sm font-medium text-purple-800 flex items-center">
                  <Server className="h-4 w-4 mr-2" />
                  Cached Server/CLI Images ({categorizedImages.server.length})
                </h4>
                <p className="text-xs text-purple-600 mt-1">Cached headless server and CLI images</p>
              </div>
              <ImageTable images={categorizedImages.server} onRemove={handleRemoveImage} actionLoading={actionLoading} isAdmin={isAdmin} />
            </div>
          )}

          {/* Cached Service Images (not in recommended list) - Issue #63 */}
          {categorizedImages.services.length > 0 && (
            <div className="bg-white shadow rounded-lg overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-200 bg-green-50">
                <h4 className="text-sm font-medium text-green-800 flex items-center">
                  <Database className="h-4 w-4 mr-2" />
                  Cached Service Images ({categorizedImages.services.length})
                </h4>
                <p className="text-xs text-green-600 mt-1">Cached database and service containers</p>
              </div>
              <ImageTable images={categorizedImages.services} onRemove={handleRemoveImage} actionLoading={actionLoading} isAdmin={isAdmin} />
            </div>
          )}

          {/* Other Cached Images (not in recommended list) */}
          {categorizedImages.other.length > 0 && (
            <div className="bg-white shadow rounded-lg overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
                <h4 className="text-sm font-medium text-gray-800 flex items-center">
                  <HardDrive className="h-4 w-4 mr-2" />
                  Other Cached ({categorizedImages.other.length})
                </h4>
                <p className="text-xs text-gray-600 mt-1">Additional cached images not in recommended list</p>
              </div>
              <ImageTable images={categorizedImages.other} onRemove={handleRemoveImage} actionLoading={actionLoading} isAdmin={isAdmin} />
            </div>
          )}
        </div>
      )}

      {/* Build Images Tab */}
      {activeTab === 'build' && (
        <div className="space-y-6">
          <div className="flex justify-between items-center">
            <div>
              <h3 className="text-lg font-medium text-gray-900">Build Custom Images</h3>
              <p className="text-sm text-gray-500">
                Build Docker images from Dockerfiles in the images/ directory
              </p>
            </div>
            <button
              onClick={loadData}
              className="inline-flex items-center px-3 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
            >
              <RefreshCw className="h-4 w-4 mr-1" />
              Refresh
            </button>
          </div>

          {/* Active Builds */}
          {Object.keys(dockerBuildStatus).length > 0 && (
            <div className="bg-white shadow rounded-lg overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-200 bg-yellow-50">
                <h4 className="text-sm font-medium text-yellow-800 flex items-center">
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Active Builds ({Object.keys(dockerBuildStatus).length})
                </h4>
              </div>
              <div className="divide-y divide-gray-200">
                {Object.entries(dockerBuildStatus).map(([buildKey, status]) => (
                  <div key={buildKey} className="px-6 py-4">
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="flex items-center">
                          <span className="font-medium text-gray-900">{status.full_tag}</span>
                          <span className={clsx(
                            'ml-2 px-2 py-0.5 text-xs rounded-full',
                            status.status === 'building' && 'bg-yellow-100 text-yellow-800',
                            status.status === 'completed' && 'bg-green-100 text-green-800',
                            status.status === 'failed' && 'bg-red-100 text-red-800',
                            status.status === 'cancelled' && 'bg-gray-100 text-gray-800'
                          )}>
                            {status.status}
                          </span>
                        </div>
                        <div className="mt-1 text-sm text-gray-500">
                          {status.current_step_name}
                        </div>
                        {status.status === 'building' && (
                          <div className="mt-2">
                            <div className="flex items-center text-xs text-gray-500 mb-1">
                              <span>Step {status.current_step || 0}/{status.total_steps || '?'}</span>
                              <span className="mx-2">-</span>
                              <span>{status.progress_percent || 0}%</span>
                            </div>
                            <div className="w-full bg-gray-200 rounded-full h-2">
                              <div
                                className="bg-indigo-600 h-2 rounded-full transition-all duration-300"
                                style={{ width: `${status.progress_percent || 0}%` }}
                              />
                            </div>
                          </div>
                        )}
                        {status.error && (
                          <div className="mt-2 text-sm text-red-600">
                            {status.error}
                          </div>
                        )}
                        {status.logs && status.logs.length > 0 && (
                          <details className="mt-2">
                            <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-700">
                              Show build logs ({status.logs.length} lines)
                            </summary>
                            <pre className="mt-2 p-2 bg-gray-50 rounded text-xs font-mono overflow-x-auto max-h-40">
                              {status.logs.join('\n')}
                            </pre>
                          </details>
                        )}
                      </div>
                      {status.status === 'building' && (
                        <button
                          onClick={() => handleCancelDockerBuild(buildKey)}
                          disabled={actionLoading === `cancel-build-${buildKey}`}
                          className="ml-4 p-2 text-gray-400 hover:text-red-600"
                          title="Cancel build"
                        >
                          {actionLoading === `cancel-build-${buildKey}` ? (
                            <Loader2 className="h-5 w-5 animate-spin" />
                          ) : (
                            <X className="h-5 w-5" />
                          )}
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Available Images to Build */}
          <div className="bg-white shadow rounded-lg overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200">
              <h4 className="text-sm font-medium text-gray-900">
                Available Images ({buildableImages.length})
              </h4>
              <p className="text-xs text-gray-500 mt-1">
                Build these images locally for use in ranges
              </p>
            </div>
            {buildableImages.length > 0 ? (
              <div className="divide-y divide-gray-200">
                {buildableImages.map((image) => {
                  const buildKey = `${image.name}_latest`
                  const isBuilding = dockerBuildStatus[buildKey]?.status === 'building'
                  const isCached = images.some(img => img.tags?.some(t => t.includes(`cyroid/${image.name}`)))

                  return (
                    <div key={image.name} className="px-6 py-4">
                      <div className="flex items-center justify-between">
                        <div className="flex-1">
                          <div className="flex items-center">
                            <Hammer className="h-5 w-5 text-gray-400 mr-3" />
                            <div>
                              <span className="font-medium text-gray-900">cyroid/{image.name}</span>
                              {isCached && (
                                <span className="ml-2 px-2 py-0.5 text-xs bg-green-100 text-green-800 rounded-full">
                                  Cached
                                </span>
                              )}
                            </div>
                          </div>
                          {image.description && (
                            <p className="mt-1 text-sm text-gray-500 ml-8">{image.description}</p>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          {isCached && (
                            <button
                              onClick={() => handleBuildImage(image.name, true)}
                              disabled={isBuilding || actionLoading === `build-${buildKey}`}
                              className="inline-flex items-center px-3 py-1.5 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
                              title="Rebuild without cache"
                            >
                              <RefreshCw className="h-4 w-4 mr-1" />
                              Rebuild
                            </button>
                          )}
                          <button
                            onClick={() => handleBuildImage(image.name, false)}
                            disabled={isBuilding || actionLoading === `build-${buildKey}`}
                            className="inline-flex items-center px-3 py-1.5 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50"
                          >
                            {actionLoading === `build-${buildKey}` || isBuilding ? (
                              <>
                                <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                                Building...
                              </>
                            ) : (
                              <>
                                <Hammer className="h-4 w-4 mr-1" />
                                {isCached ? 'Build' : 'Build'}
                              </>
                            )}
                          </button>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            ) : (
              <div className="px-6 py-12 text-center text-gray-500">
                <Hammer className="h-12 w-12 text-gray-300 mx-auto mb-4" />
                <p className="text-lg font-medium text-gray-900">No buildable images found</p>
                <p className="text-sm mt-1">
                  Add Dockerfiles to the <code className="bg-gray-100 px-1 rounded">images/</code> directory
                </p>
              </div>
            )}
          </div>

          {/* Build Instructions */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex">
              <Info className="h-5 w-5 text-blue-400 flex-shrink-0" />
              <div className="ml-3">
                <h4 className="text-sm font-medium text-blue-800">About Image Building</h4>
                <div className="mt-1 text-sm text-blue-700">
                  <ul className="list-disc list-inside space-y-1">
                    <li>Images are built from Dockerfiles in the <code className="bg-blue-100 px-1 rounded">images/</code> directory</li>
                    <li>Built images are tagged as <code className="bg-blue-100 px-1 rounded">cyroid/[name]:latest</code></li>
                    <li>Use "Rebuild" to force a fresh build without Docker cache</li>
                    <li>Build progress can be monitored - you can navigate away and return</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Image Files Tab */}
      {activeTab === 'files' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <div>
              <h3 className="text-lg font-medium text-gray-900">Image Project Files</h3>
              <p className="text-sm text-gray-500">
                Browse and edit Dockerfiles, scripts, and configuration files for custom images
              </p>
            </div>
          </div>
          <FileBrowser basePath="images" title="" />
        </div>
      )}

      {/* Windows ISOs Tab */}
      {activeTab === 'isos' && windowsVersions && (
        <div className="space-y-6">
          <div className="flex justify-between items-center">
            <div>
              <h3 className="text-lg font-medium text-gray-900">Windows ISOs (dockur/windows)</h3>
              <p className="text-sm text-gray-500">
                {windowsVersions.cached_count} of {windowsVersions.total_count} versions cached
                {windowsVersions.host_arch && (
                  <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700">
                    Host: {windowsVersions.host_arch}
                  </span>
                )}
              </p>
            </div>
            {isAdmin && (
              <button
                onClick={() => setShowUploadModal('windows')}
                className="inline-flex items-center px-3 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700 text-sm"
              >
                <Upload className="h-4 w-4 mr-2" />
                Upload ISO
              </button>
            )}
          </div>

          {/* Cache Directory Info */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex">
              <Info className="h-5 w-5 text-blue-500 mt-0.5 mr-3" />
              <div>
                <h4 className="text-sm font-medium text-blue-800">ISO Cache Directory</h4>
                <p className="mt-1 text-sm text-blue-700">
                  <code className="bg-blue-100 px-2 py-0.5 rounded">{windowsVersions.cache_dir}</code>
                </p>
                <p className="mt-2 text-sm text-blue-700">
                  {windowsVersions.note}
                </p>
                {windowsVersions.arm64_note && (
                  <p className="mt-2 text-sm text-purple-700">
                    {windowsVersions.arm64_note}
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* Desktop Versions */}
          <WindowsVersionSection
            title="Desktop"
            versions={windowsVersions.desktop}
            icon={Monitor}
            colorClass="blue"
            onDelete={handleDeleteWindowsISO}
            onDownload={handleDownloadWindowsISO}
            onCancel={handleCancelWindowsDownload}
            downloadStatus={downloadStatus}
            actionLoading={actionLoading}
            isAdmin={isAdmin}
            hostArch={windowsVersions.host_arch}
          />

          {/* Server Versions */}
          <WindowsVersionSection
            title="Server"
            versions={windowsVersions.server}
            icon={Server}
            colorClass="purple"
            onDelete={handleDeleteWindowsISO}
            onDownload={handleDownloadWindowsISO}
            onCancel={handleCancelWindowsDownload}
            downloadStatus={downloadStatus}
            actionLoading={actionLoading}
            isAdmin={isAdmin}
            hostArch={windowsVersions.host_arch}
          />

          {/* Legacy Versions */}
          <WindowsVersionSection
            title="Legacy"
            versions={windowsVersions.legacy}
            icon={Database}
            colorClass="orange"
            onDelete={handleDeleteWindowsISO}
            onDownload={handleDownloadWindowsISO}
            onCancel={handleCancelWindowsDownload}
            downloadStatus={downloadStatus}
            actionLoading={actionLoading}
            isAdmin={isAdmin}
            hostArch={windowsVersions.host_arch}
          />
        </div>
      )}

      {/* Linux ISOs Tab */}
      {activeTab === 'linux-isos' && linuxVersions && (
        <div className="space-y-6">
          <div className="flex justify-between items-center">
            <div>
              <h3 className="text-lg font-medium text-gray-900">Linux Distributions (qemux/qemu)</h3>
              <p className="text-sm text-gray-500">
                {linuxVersions.cached_count} of {linuxVersions.total_count} distributions cached
                {linuxVersions.host_arch && (
                  <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700">
                    Host: {linuxVersions.host_arch}
                  </span>
                )}
              </p>
            </div>
          </div>

          {/* Cache Directory Info */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex">
              <Info className="h-5 w-5 text-blue-500 mt-0.5 mr-3" />
              <div>
                <h4 className="text-sm font-medium text-blue-800">Linux ISO Cache Directory</h4>
                <p className="mt-1 text-sm text-blue-700">
                  <code className="bg-blue-100 px-2 py-0.5 rounded">{linuxVersions.cache_dir}</code>
                </p>
                <p className="mt-2 text-sm text-blue-700">
                  {linuxVersions.note}
                </p>
                {linuxVersions.arm64_supported_distros && linuxVersions.arm64_supported_distros.length > 0 && (
                  <p className="mt-2 text-sm text-purple-700">
                    ARM64 supported: {linuxVersions.arm64_supported_distros.join(', ')}
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* Desktop Distributions */}
          <LinuxVersionSection
            title="Desktop"
            versions={linuxVersions.desktop}
            icon={Monitor}
            colorClass="blue"
            onDelete={handleDeleteLinuxISO}
            onDownload={handleDownloadLinuxISO}
            onCancel={handleCancelLinuxDownload}
            downloadStatus={linuxDownloadStatus}
            actionLoading={actionLoading}
            isAdmin={isAdmin}
            hostArch={linuxVersions.host_arch}
          />

          {/* Security Distributions (for cyber range training) */}
          <LinuxVersionSection
            title="Security"
            versions={linuxVersions.security}
            icon={AlertCircle}
            colorClass="red"
            onDelete={handleDeleteLinuxISO}
            onDownload={handleDownloadLinuxISO}
            onCancel={handleCancelLinuxDownload}
            downloadStatus={linuxDownloadStatus}
            actionLoading={actionLoading}
            isAdmin={isAdmin}
            hostArch={linuxVersions.host_arch}
          />

          {/* Server Distributions */}
          <LinuxVersionSection
            title="Server"
            versions={linuxVersions.server}
            icon={Server}
            colorClass="purple"
            onDelete={handleDeleteLinuxISO}
            onDownload={handleDownloadLinuxISO}
            onCancel={handleCancelLinuxDownload}
            downloadStatus={linuxDownloadStatus}
            actionLoading={actionLoading}
            isAdmin={isAdmin}
            hostArch={linuxVersions.host_arch}
          />
        </div>
      )}

      {/* Custom ISOs Tab */}
      {activeTab === 'custom-isos' && customISOs && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <div>
              <h3 className="text-lg font-medium text-gray-900">Custom ISOs</h3>
              <p className="text-sm text-gray-500">
                Download or upload custom ISOs from URLs for VM deployment
              </p>
            </div>
            {isAdmin && (
              <div className="flex gap-2">
                <button
                  onClick={() => setShowCustomISOModal(true)}
                  className="inline-flex items-center px-3 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 text-sm"
                >
                  <Download className="h-4 w-4 mr-2" />
                  Download from URL
                </button>
                <button
                  onClick={() => setShowUploadModal('custom')}
                  className="inline-flex items-center px-3 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 text-sm"
                >
                  <Upload className="h-4 w-4 mr-2" />
                  Upload ISO
                </button>
              </div>
            )}
          </div>

          {/* Cache Directory Info */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex">
              <Info className="h-5 w-5 text-blue-500 mt-0.5 mr-3" />
              <div>
                <h4 className="text-sm font-medium text-blue-800">Custom ISO Cache</h4>
                <p className="mt-1 text-sm text-blue-700">
                  <code className="bg-blue-100 px-2 py-0.5 rounded">{customISOs.cache_dir}</code>
                </p>
              </div>
            </div>
          </div>

          {/* Active Downloads */}
          {Object.keys(customISODownloadStatus).length > 0 && (
            <div className="bg-white shadow rounded-lg overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-200 bg-blue-50">
                <h4 className="text-sm font-medium text-blue-800 flex items-center">
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Active Downloads ({Object.keys(customISODownloadStatus).length})
                </h4>
              </div>
              <div className="p-4 space-y-4">
                {Object.entries(customISODownloadStatus).map(([filename, status]) => (
                  <div key={filename} className="border rounded-lg p-4 bg-blue-50 border-blue-200">
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-gray-900">{status.name || filename}</p>
                        <div className="text-xs text-gray-500 font-mono mt-1">{filename}</div>
                      </div>
                      <div className="flex items-center gap-1 ml-2 flex-shrink-0">
                        <div className="flex items-center gap-1 text-blue-600">
                          <Loader2 className="h-4 w-4 animate-spin flex-shrink-0" />
                          <span className="text-xs font-medium">
                            {status.progress_percent ? `${status.progress_percent}%` : 'Starting...'}
                          </span>
                        </div>
                      </div>
                    </div>
                    {/* Download progress bar */}
                    <div className="mt-3 space-y-1.5">
                      <div className="flex justify-between items-center text-xs">
                        <span className="text-blue-700 font-medium">
                          {status.progress_gb?.toFixed(2) || '0.00'} GB
                          {status.total_gb ? ` / ${status.total_gb.toFixed(2)} GB` : ''}
                        </span>
                        <div className="flex items-center gap-2">
                          {status.progress_percent && (
                            <span className="text-blue-600 font-semibold">{status.progress_percent}%</span>
                          )}
                          {isAdmin && (
                            <button
                              onClick={() => handleCancelCustomISODownload(filename)}
                              disabled={actionLoading === `cancel-custom-${filename}`}
                              className="text-red-500 hover:text-red-700 p-0.5 rounded hover:bg-red-50"
                              title="Cancel download"
                            >
                              <X className="h-4 w-4" />
                            </button>
                          )}
                        </div>
                      </div>
                      <div className="w-full bg-blue-100 rounded-full h-2.5 overflow-hidden">
                        {status.total_bytes && status.progress_bytes ? (
                          <div
                            className="bg-gradient-to-r from-blue-500 to-blue-600 h-2.5 rounded-full transition-all duration-500 ease-out"
                            style={{ width: `${(status.progress_bytes / status.total_bytes) * 100}%` }}
                          />
                        ) : (
                          <div className="bg-gradient-to-r from-blue-400 via-blue-500 to-blue-400 h-2.5 rounded-full animate-pulse w-full opacity-60" />
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Custom ISOs List */}
          <div className="bg-white shadow rounded-lg overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200">
              <h4 className="text-sm font-medium text-gray-900">
                Cached Custom ISOs ({customISOs.total_count})
              </h4>
            </div>
            {customISOs.isos.length > 0 ? (
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Size</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Source</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {customISOs.isos.map((iso) => (
                    <tr key={iso.filename}>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-medium text-gray-900">{iso.name}</div>
                        <div className="text-xs text-gray-500 font-mono">{iso.filename}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {iso.size_gb} GB
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500">
                        {iso.url?.startsWith('uploaded:') ? (
                          <span className="text-green-600">Uploaded locally</span>
                        ) : iso.url ? (
                          <a href={iso.url} target="_blank" rel="noopener noreferrer"
                            className="inline-flex items-center text-primary-600 hover:text-primary-700 max-w-[200px] truncate">
                            <Link className="h-3 w-3 mr-1 flex-shrink-0" />
                            <span className="truncate">{iso.url}</span>
                          </a>
                        ) : 'Unknown'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right">
                        {isAdmin && (
                          <button
                            onClick={() => handleDeleteCustomISO(iso.filename, iso.name)}
                            disabled={actionLoading === `custom-iso-${iso.filename}`}
                            className="text-red-600 hover:text-red-900 disabled:opacity-50"
                          >
                            {actionLoading === `custom-iso-${iso.filename}` ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <Trash2 className="h-4 w-4" />
                            )}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="px-6 py-8 text-center text-gray-500">
                <Download className="h-12 w-12 text-gray-300 mx-auto mb-3" />
                <p>No custom ISOs cached yet.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Upload ISO Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex items-center justify-center min-h-screen px-4">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75" onClick={() => setShowUploadModal(null)} />
            <div className="relative bg-white rounded-lg shadow-xl max-w-lg w-full">
              <div className="px-6 py-4 border-b border-gray-200">
                <h3 className="text-lg font-medium text-gray-900">
                  Upload {showUploadModal === 'windows' ? 'Windows' : showUploadModal === 'linux' ? 'Linux' : 'Custom'} ISO
                </h3>
              </div>
              <div className="px-6 py-4 space-y-4">
                {showUploadModal === 'windows' && windowsVersions && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Windows Version</label>
                    <select
                      value={uploadVersion}
                      onChange={(e) => setUploadVersion(e.target.value)}
                      className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
                    >
                      <option value="">Select version...</option>
                      <optgroup label="Desktop">
                        {windowsVersions.desktop.filter(v => !v.cached).map(v => (
                          <option key={v.version} value={v.version}>{v.name} ({v.version})</option>
                        ))}
                      </optgroup>
                      <optgroup label="Server">
                        {windowsVersions.server.filter(v => !v.cached).map(v => (
                          <option key={v.version} value={v.version}>{v.name} ({v.version})</option>
                        ))}
                      </optgroup>
                      <optgroup label="Legacy">
                        {windowsVersions.legacy.filter(v => !v.cached).map(v => (
                          <option key={v.version} value={v.version}>{v.name} ({v.version})</option>
                        ))}
                      </optgroup>
                    </select>
                  </div>
                )}

                {showUploadModal === 'linux' && linuxVersions && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Linux Distribution</label>
                    <select
                      value={uploadVersion}
                      onChange={(e) => setUploadVersion(e.target.value)}
                      className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
                    >
                      <option value="">Select distribution...</option>
                      <optgroup label="Desktop">
                        {linuxVersions.desktop.filter(v => !v.cached).map(v => (
                          <option key={v.version} value={v.version}>{v.name}</option>
                        ))}
                      </optgroup>
                      <optgroup label="Security">
                        {linuxVersions.security.filter(v => !v.cached).map(v => (
                          <option key={v.version} value={v.version}>{v.name}</option>
                        ))}
                      </optgroup>
                      <optgroup label="Server">
                        {linuxVersions.server.filter(v => !v.cached).map(v => (
                          <option key={v.version} value={v.version}>{v.name}</option>
                        ))}
                      </optgroup>
                    </select>
                    <p className="mt-1 text-xs text-gray-500">
                      Select a distribution to associate with the uploaded ISO
                    </p>
                  </div>
                )}

                {showUploadModal === 'custom' && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">ISO Name</label>
                    <input
                      type="text"
                      value={uploadName}
                      onChange={(e) => setUploadName(e.target.value)}
                      placeholder="e.g., Ubuntu 22.04 Server"
                      className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
                    />
                  </div>
                )}

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">ISO File</label>
                  <div className="flex items-center gap-3">
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".iso"
                      onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                      className="hidden"
                    />
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      className="px-4 py-2 border border-gray-300 rounded-md text-sm hover:bg-gray-50"
                    >
                      Choose File
                    </button>
                    <span className="text-sm text-gray-500 truncate">
                      {uploadFile ? uploadFile.name : 'No file chosen'}
                    </span>
                  </div>
                  {uploadFile && (
                    <p className="mt-1 text-xs text-gray-500">
                      Size: {(uploadFile.size / (1024 * 1024 * 1024)).toFixed(2)} GB
                    </p>
                  )}
                </div>

                <div className="bg-yellow-50 border border-yellow-200 rounded-md p-3">
                  <div className="flex">
                    <AlertCircle className="h-4 w-4 text-yellow-500 mt-0.5 mr-2" />
                    <p className="text-xs text-yellow-700">
                      Large ISO files may take several minutes to upload depending on file size and connection speed.
                    </p>
                  </div>
                </div>
              </div>
              <div className="px-6 py-4 border-t border-gray-200 flex justify-end space-x-3">
                <button
                  onClick={() => {
                    setShowUploadModal(null)
                    setUploadFile(null)
                    setUploadVersion('')
                    setUploadName('')
                  }}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleUploadISO}
                  disabled={actionLoading === 'upload' || !uploadFile || (showUploadModal === 'windows' || showUploadModal === 'linux' ? !uploadVersion : !uploadName)}
                  className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-md hover:bg-primary-700 disabled:opacity-50"
                >
                  {actionLoading === 'upload' ? (
                    <>
                      <Loader2 className="inline h-4 w-4 mr-2 animate-spin" />
                      Uploading...
                    </>
                  ) : (
                    <>
                      <Upload className="inline h-4 w-4 mr-2" />
                      Upload
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Download Custom ISO Modal */}
      {showCustomISOModal && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex items-center justify-center min-h-screen px-4">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75" onClick={() => setShowCustomISOModal(false)} />
            <div className="relative bg-white rounded-lg shadow-xl max-w-lg w-full">
              <div className="px-6 py-4 border-b border-gray-200">
                <h3 className="text-lg font-medium text-gray-900">Download Custom ISO</h3>
              </div>
              <div className="px-6 py-4 space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">ISO Name</label>
                  <input
                    type="text"
                    value={customISOName}
                    onChange={(e) => setCustomISOName(e.target.value)}
                    placeholder="e.g., Ubuntu 22.04 Server"
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Download URL</label>
                  <input
                    type="url"
                    value={customISOUrl}
                    onChange={(e) => setCustomISOUrl(e.target.value)}
                    placeholder="https://releases.ubuntu.com/22.04/ubuntu-22.04.3-live-server-amd64.iso"
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
                  />
                </div>
              </div>
              <div className="px-6 py-4 border-t border-gray-200 flex justify-end space-x-3">
                <button
                  onClick={() => { setShowCustomISOModal(false); setCustomISOName(''); setCustomISOUrl(''); }}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleDownloadCustomISO}
                  disabled={actionLoading === 'custom-iso-download' || !customISOName || !customISOUrl}
                  className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-md hover:bg-primary-700 disabled:opacity-50"
                >
                  {actionLoading === 'custom-iso-download' ? (
                    <><Loader2 className="inline h-4 w-4 mr-2 animate-spin" />Starting...</>
                  ) : (
                    <><Download className="inline h-4 w-4 mr-2" />Download</>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Cache Docker Images Modal */}
      {showCacheModal && recommended && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex items-center justify-center min-h-screen px-4">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75" onClick={() => setShowCacheModal(false)} />
            <div className="relative bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] overflow-y-auto">
              <div className="px-6 py-4 border-b border-gray-200 sticky top-0 bg-white">
                <h3 className="text-lg font-medium text-gray-900">Cache Docker Images</h3>
              </div>
              <div className="px-6 py-4 space-y-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Custom Image Name</label>
                  <input
                    type="text"
                    value={newImageName}
                    onChange={(e) => setNewImageName(e.target.value)}
                    placeholder="e.g., nginx:latest"
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
                  />
                </div>

                {/* Desktop Images */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    <Monitor className="inline h-4 w-4 mr-1" /> Desktop Images
                    <span className="text-xs text-gray-500 ml-2">(with VNC/RDP/Web access)</span>
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    {recommended.desktop.map((img) => (
                      <ImageCheckbox key={img.image} img={img} selected={selectedRecommended} setSelected={setSelectedRecommended} />
                    ))}
                  </div>
                </div>

                {/* Server/CLI Images */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    <Server className="inline h-4 w-4 mr-1" /> Server/CLI Images
                    <span className="text-xs text-gray-500 ml-2">(headless)</span>
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    {recommended.server.map((img) => (
                      <ImageCheckbox key={img.image} img={img} selected={selectedRecommended} setSelected={setSelectedRecommended} />
                    ))}
                  </div>
                </div>

                {/* Service Images */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    <Database className="inline h-4 w-4 mr-1" /> Service Images
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    {recommended.services.map((img) => (
                      <ImageCheckbox key={img.image} img={img} selected={selectedRecommended} setSelected={setSelectedRecommended} />
                    ))}
                  </div>
                </div>
              </div>
              <div className="px-6 py-4 border-t border-gray-200 flex justify-end space-x-3 sticky bottom-0 bg-white">
                <button
                  onClick={() => setShowCacheModal(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleCacheBatch}
                  disabled={actionLoading === 'batch' || (selectedRecommended.length === 0 && !newImageName)}
                  className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-md hover:bg-primary-700 disabled:opacity-50"
                >
                  {actionLoading === 'batch' ? (
                    <><Loader2 className="inline h-4 w-4 mr-2 animate-spin" />Caching...</>
                  ) : (
                    `Cache ${selectedRecommended.length + (newImageName ? 1 : 0)} Images`
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        isOpen={deleteConfirm.type !== null}
        title={
          deleteConfirm.type === 'docker' ? 'Remove Docker Image' :
          deleteConfirm.type === 'windows-iso' ? 'Delete Windows ISO' :
          deleteConfirm.type === 'linux-iso' ? 'Delete Linux ISO' :
          deleteConfirm.type === 'custom-iso' ? 'Delete Custom ISO' : 'Delete'
        }
        message={`Are you sure you want to delete "${deleteConfirm.name}"? This action cannot be undone.`}
        confirmLabel="Delete"
        variant="danger"
        onConfirm={confirmDelete}
        onCancel={() => setDeleteConfirm({ type: null, name: '', isLoading: false })}
        isLoading={deleteConfirm.isLoading}
      />
    </div>
  )
}

// Helper Components

function DockerImageSection({ title, description, images, cachedImages, icon: Icon, colorClass, onPull, onRemove, onCancel, pullStatus, actionLoading, isAdmin }: {
  title: string
  description: string
  images: RecommendedImage[]
  cachedImages: CachedImage[]
  icon: typeof Monitor
  colorClass: string
  onPull: (image: string) => void
  onRemove: (id: string, tag: string) => void
  onCancel: (imageKey: string) => void
  pullStatus: Record<string, DockerPullStatus>
  actionLoading: string | null
  isAdmin: boolean
}) {
  const bgClass = `bg-${colorClass}-50`
  const textClass = `text-${colorClass}-800`

  // Check if an image is cached
  const isImageCached = (imageName: string): CachedImage | undefined => {
    return cachedImages.find(cached =>
      cached.tags.some(tag => tag === imageName || tag.startsWith(imageName.split(':')[0]))
    )
  }

  if (!images || images.length === 0) return null

  return (
    <div className="bg-white shadow rounded-lg overflow-hidden">
      <div className={clsx("px-6 py-4 border-b border-gray-200", bgClass)}>
        <h4 className={clsx("text-sm font-medium flex items-center", textClass)}>
          <Icon className="h-4 w-4 mr-2" />
          {title} ({images.length})
        </h4>
        <p className={clsx("text-xs mt-1", textClass.replace('800', '600'))}>{description}</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 p-4">
        {images.filter(img => img.image).map((img) => {
          const imageName = img.image!
          const imageKey = imageName.replace(/\//g, '_').replace(/:/g, '_')
          const cached = isImageCached(imageName)
          const pullState = pullStatus[imageKey]
          const isPulling = pullState?.status === 'pulling'
          const isLoading = actionLoading === `pull-${imageKey}`

          return (
            <div key={imageName} className={clsx(
              "border rounded-lg p-4",
              cached ? "bg-green-50 border-green-200" :
              isPulling ? "bg-blue-50 border-blue-200" : "hover:bg-gray-50"
            )}>
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-gray-900 truncate" title={img.name || imageName}>{img.name || imageName}</p>
                  <p className="text-xs text-gray-600 truncate" title={imageName}>{imageName}</p>
                  <p className="text-xs text-gray-500 mt-1 line-clamp-2">{img.description}</p>
                </div>
                <div className="flex items-center gap-1 ml-2 flex-shrink-0">
                  {isPulling ? (
                    <div className="flex items-center gap-1 text-blue-600">
                      <Loader2 className="h-4 w-4 animate-spin flex-shrink-0" />
                      <span className="text-xs font-medium">
                        {pullState.progress_percent ? `${pullState.progress_percent}%` : 'Starting...'}
                      </span>
                    </div>
                  ) : cached ? (
                    <>
                      <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                        <Check className="h-3 w-3 mr-1" />
                        Cached
                      </span>
                      {isAdmin && (
                        <button
                          onClick={() => onRemove(cached.id, cached.tags[0] || cached.id)}
                          disabled={actionLoading === cached.id}
                          className="text-red-600 hover:text-red-900 disabled:opacity-50 p-1"
                          title="Remove cached image"
                        >
                          {actionLoading === cached.id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Trash2 className="h-4 w-4" />
                          )}
                        </button>
                      )}
                    </>
                  ) : isAdmin ? (
                    <button
                      onClick={() => onPull(imageName)}
                      disabled={isLoading}
                      className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-blue-100 text-blue-700 hover:bg-blue-200 disabled:opacity-50"
                      title="Pull image"
                    >
                      {isLoading ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : (
                        <>
                          <Download className="h-3 w-3 mr-1" />
                          Pull
                        </>
                      )}
                    </button>
                  ) : (
                    <span className="text-xs text-gray-400">Not cached</span>
                  )}
                </div>
              </div>
              {/* Pull progress bar */}
              {isPulling && pullState && (
                <div className="mt-3 space-y-1.5">
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-blue-700 font-medium">
                      {pullState.layers_completed || 0} / {pullState.layers_total || '?'} layers
                    </span>
                    <div className="flex items-center gap-2">
                      {pullState.progress_percent !== undefined && (
                        <span className="text-blue-600 font-semibold">{pullState.progress_percent}%</span>
                      )}
                      {isAdmin && (
                        <button
                          onClick={() => onCancel(imageKey)}
                          disabled={actionLoading === `cancel-docker-${imageKey}`}
                          className="text-red-500 hover:text-red-700 p-0.5 rounded hover:bg-red-50"
                          title="Cancel pull"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      )}
                    </div>
                  </div>
                  <div className="w-full bg-blue-100 rounded-full h-2.5 overflow-hidden">
                    {pullState.progress_percent !== undefined && pullState.progress_percent > 0 ? (
                      <div
                        className="bg-gradient-to-r from-blue-500 to-blue-600 h-2.5 rounded-full transition-all duration-500 ease-out"
                        style={{ width: `${pullState.progress_percent}%` }}
                      />
                    ) : (
                      <div className="bg-gradient-to-r from-blue-400 via-blue-500 to-blue-400 h-2.5 rounded-full animate-pulse w-full opacity-60" />
                    )}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function ImageTable({ images, onRemove, actionLoading, isAdmin }: {
  images: CachedImage[]
  onRemove: (id: string, tag: string) => void
  actionLoading: string | null
  isAdmin: boolean
}) {
  return (
    <table className="min-w-full divide-y divide-gray-200">
      <thead className="bg-gray-50">
        <tr>
          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Image</th>
          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Size</th>
          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Created</th>
          {isAdmin && <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>}
        </tr>
      </thead>
      <tbody className="bg-white divide-y divide-gray-200">
        {images.map((image) => (
          <tr key={image.id}>
            <td className="px-6 py-4 whitespace-nowrap">
              <div className="text-sm font-medium text-gray-900">{image.tags[0] || image.id.substring(0, 12)}</div>
              {image.tags.length > 1 && <div className="text-xs text-gray-500">+{image.tags.length - 1} more</div>}
            </td>
            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{image.size_gb} GB</td>
            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
              {image.created ? new Date(image.created).toLocaleDateString() : 'Unknown'}
            </td>
            {isAdmin && (
              <td className="px-6 py-4 whitespace-nowrap text-right">
                <button
                  onClick={() => onRemove(image.id, image.tags[0] || image.id)}
                  disabled={actionLoading === image.id}
                  className="text-red-600 hover:text-red-900 disabled:opacity-50"
                  title="Remove image"
                >
                  {actionLoading === image.id ? <Loader2 className="h-4 w-4 animate-spin inline" /> : <Trash2 className="h-4 w-4 inline" />}
                </button>
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function WindowsVersionSection({ title, versions, icon: Icon, colorClass, onDelete, onDownload, onCancel, downloadStatus, actionLoading, isAdmin, hostArch }: {
  title: string
  versions: WindowsVersion[]
  icon: typeof Monitor
  colorClass: string
  onDelete: (version: string, name: string, arch?: 'x86_64' | 'arm64') => void
  onDownload: (version: WindowsVersion, customUrl?: string, arch?: 'x86_64' | 'arm64') => Promise<void>
  onCancel: (version: string, arch?: 'x86_64' | 'arm64') => Promise<void>
  downloadStatus: Record<string, WindowsISODownloadStatus>
  actionLoading: string | null
  isAdmin: boolean
  hostArch?: 'x86_64' | 'arm64'
}) {
  const bgClass = `bg-${colorClass}-50`
  const textClass = `text-${colorClass}-800`
  const badgeBgClass = `bg-${colorClass}-100`
  const badgeTextClass = `text-${colorClass}-800`

  return (
    <div className="bg-white shadow rounded-lg overflow-hidden">
      <div className={clsx("px-6 py-4 border-b border-gray-200", bgClass)}>
        <h4 className={clsx("text-sm font-medium flex items-center", textClass)}>
          <Icon className="h-4 w-4 mr-2" />
          {title} ({versions.length})
        </h4>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 p-4">
        {versions.map((v) => {
          // Check for architecture-specific downloads
          const x86Key = `${v.version}-x86_64`
          const arm64Key = `${v.version}-arm64`
          const x86Status = downloadStatus[x86Key] || downloadStatus[v.version]
          const arm64Status = downloadStatus[arm64Key]
          const isDownloadingX86 = x86Status?.status === 'downloading'
          const isDownloadingArm64 = arm64Status?.status === 'downloading'

          // Architecture-specific loading states
          const isLoadingX86 = actionLoading === `download-windows-${x86Key}` ||
                              actionLoading === `download-windows-${v.version}` ||
                              actionLoading === `cancel-windows-${x86Key}` ||
                              actionLoading === `cancel-windows-${v.version}`
          const isLoadingArm64 = actionLoading === `download-windows-${arm64Key}` ||
                                actionLoading === `cancel-windows-${arm64Key}`

          // Check cached status
          const cachedX86 = v.cached_x86_64 || (hostArch === 'x86_64' && v.cached)
          const cachedArm64 = v.cached_arm64 || (hostArch === 'arm64' && v.cached)

          return (
            <div key={v.version} className={clsx(
              "border rounded-lg p-4",
              (cachedX86 || cachedArm64) ? "bg-green-50 border-green-200" :
              (isDownloadingX86 || isDownloadingArm64) ? "bg-blue-50 border-blue-200" : "hover:bg-gray-50"
            )}>
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-gray-900 truncate">{v.name}</p>
                  <div className="flex items-center gap-2 mt-1 flex-wrap">
                    <code className={clsx("px-2 py-0.5 rounded text-xs font-mono", badgeBgClass, badgeTextClass)}>
                      {v.version}
                    </code>
                    <span className="text-sm text-gray-500">{v.size_gb} GB</span>
                    {v.arm64_available && (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-700" title="ARM64 version available">
                        ARM64
                      </span>
                    )}
                  </div>

                  {/* Architecture-specific cache status */}
                  <div className="flex items-center gap-2 mt-2 flex-wrap">
                    {cachedX86 && (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
                        <Check className="h-2.5 w-2.5 mr-0.5" />
                        x86_64
                      </span>
                    )}
                    {cachedArm64 && (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
                        <Check className="h-2.5 w-2.5 mr-0.5" />
                        ARM64
                      </span>
                    )}
                  </div>

                  {/* x86_64 Download progress */}
                  {isDownloadingX86 && x86Status && (
                    <div className="mt-3 space-y-1.5">
                      <div className="flex justify-between items-center text-xs">
                        <span className="text-blue-700 font-medium">
                          x86_64: {x86Status.progress_gb?.toFixed(2) || '0.00'} GB
                          {x86Status.total_gb ? ` / ${x86Status.total_gb.toFixed(2)} GB` : ''}
                        </span>
                        <div className="flex items-center gap-2">
                          {x86Status.progress_percent && (
                            <span className="text-blue-600 font-semibold">{x86Status.progress_percent}%</span>
                          )}
                          {isAdmin && (
                            <button
                              onClick={() => onCancel(v.version, 'x86_64')}
                              disabled={actionLoading === `cancel-windows-${x86Key}`}
                              className="text-red-500 hover:text-red-700 p-0.5 rounded hover:bg-red-50"
                              title="Cancel download"
                            >
                              <X className="h-4 w-4" />
                            </button>
                          )}
                        </div>
                      </div>
                      <div className="w-full bg-blue-100 rounded-full h-2 overflow-hidden">
                        {x86Status.total_bytes && x86Status.progress_bytes ? (
                          <div
                            className="bg-gradient-to-r from-blue-500 to-blue-600 h-2 rounded-full transition-all duration-500 ease-out"
                            style={{ width: `${x86Status.progress_percent || 0}%` }}
                          />
                        ) : (
                          <div className="bg-gradient-to-r from-blue-400 via-blue-500 to-blue-400 h-2 rounded-full animate-pulse w-full opacity-60" />
                        )}
                      </div>
                    </div>
                  )}

                  {/* ARM64 Download progress */}
                  {isDownloadingArm64 && arm64Status && (
                    <div className="mt-3 space-y-1.5">
                      <div className="flex justify-between items-center text-xs">
                        <span className="text-purple-700 font-medium">
                          ARM64: {arm64Status.progress_gb?.toFixed(2) || '0.00'} GB
                          {arm64Status.total_gb ? ` / ${arm64Status.total_gb.toFixed(2)} GB` : ''}
                        </span>
                        <div className="flex items-center gap-2">
                          {arm64Status.progress_percent && (
                            <span className="text-purple-600 font-semibold">{arm64Status.progress_percent}%</span>
                          )}
                          {isAdmin && (
                            <button
                              onClick={() => onCancel(v.version, 'arm64')}
                              disabled={actionLoading === `cancel-windows-${arm64Key}`}
                              className="text-red-500 hover:text-red-700 p-0.5 rounded hover:bg-red-50"
                              title="Cancel download"
                            >
                              <X className="h-4 w-4" />
                            </button>
                          )}
                        </div>
                      </div>
                      <div className="w-full bg-purple-100 rounded-full h-2 overflow-hidden">
                        {arm64Status.total_bytes && arm64Status.progress_bytes ? (
                          <div
                            className="bg-gradient-to-r from-purple-500 to-purple-600 h-2 rounded-full transition-all duration-500 ease-out"
                            style={{ width: `${arm64Status.progress_percent || 0}%` }}
                          />
                        ) : (
                          <div className="bg-gradient-to-r from-purple-400 via-purple-500 to-purple-400 h-2 rounded-full animate-pulse w-full opacity-60" />
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Action buttons */}
              <div className="mt-3 flex items-center gap-2 flex-wrap">
                {/* x86_64 actions */}
                {cachedX86 ? (
                  <div className="flex items-center gap-1">
                    <span className="text-xs text-gray-500">x86_64</span>
                    {isAdmin && (
                      <button
                        onClick={() => onDelete(v.version, v.name, 'x86_64')}
                        disabled={isLoadingX86}
                        className="p-1 text-red-600 hover:bg-red-50 rounded"
                        title="Delete x86_64 ISO"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                ) : isDownloadingX86 ? (
                  <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                    <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                    x86_64
                  </span>
                ) : v.download_url && isAdmin ? (
                  <button
                    onClick={() => onDownload(v, undefined, 'x86_64')}
                    disabled={isLoadingX86}
                    className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-blue-50 text-blue-700 hover:bg-blue-100"
                  >
                    {isLoadingX86 ? (
                      <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                    ) : (
                      <Download className="h-3 w-3 mr-1" />
                    )}
                    x86_64
                  </button>
                ) : (
                  <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-600" title="Auto-downloaded on first use">
                    x86_64 (auto)
                  </span>
                )}

                {/* ARM64 actions (only if available) */}
                {v.arm64_available && (
                  <>
                    {cachedArm64 ? (
                      <div className="flex items-center gap-1">
                        <span className="text-xs text-gray-500">ARM64</span>
                        {isAdmin && (
                          <button
                            onClick={() => onDelete(v.version, v.name, 'arm64')}
                            disabled={isLoadingArm64}
                            className="p-1 text-red-600 hover:bg-red-50 rounded"
                            title="Delete ARM64 ISO"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </div>
                    ) : isDownloadingArm64 ? (
                      <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                        <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                        ARM64
                      </span>
                    ) : v.arm64_has_url && isAdmin ? (
                      <button
                        onClick={() => onDownload(v, undefined, 'arm64')}
                        disabled={isLoadingArm64}
                        className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-purple-50 text-purple-700 hover:bg-purple-100"
                      >
                        {isLoadingArm64 ? (
                          <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                        ) : (
                          <Download className="h-3 w-3 mr-1" />
                        )}
                        ARM64
                      </button>
                    ) : (
                      <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-600" title="ARM64 ISO built on first use (no direct download)">
                        ARM64 (auto)
                      </span>
                    )}
                  </>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function ImageCheckbox({ img, selected, setSelected }: {
  img: { name?: string; image?: string; description: string; cached?: boolean }
  selected: string[]
  setSelected: (s: string[]) => void
}) {
  if (!img.image) return null
  const isSelected = selected.includes(img.image)
  const isCached = img.cached

  return (
    <label className={clsx(
      "flex items-center p-2 border rounded cursor-pointer",
      isCached ? "bg-green-50 border-green-200" : "hover:bg-gray-50",
      isSelected && !isCached && "bg-primary-50 border-primary-200"
    )}>
      <input
        type="checkbox"
        checked={isSelected}
        disabled={isCached}
        onChange={(e) => {
          if (e.target.checked) {
            setSelected([...selected, img.image!])
          } else {
            setSelected(selected.filter((i) => i !== img.image))
          }
        }}
        className="mr-2"
      />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate" title={img.name || img.image}>{img.name || img.image}</p>
        <p className="text-xs text-gray-500 truncate" title={img.image}>{img.image}</p>
      </div>
      {isCached && (
        <Check className="h-4 w-4 text-green-600 ml-2 flex-shrink-0" />
      )}
    </label>
  )
}

function LinuxVersionSection({ title, versions, icon: Icon, colorClass, onDelete, onDownload, onCancel, downloadStatus, actionLoading, isAdmin, hostArch }: {
  title: string
  versions: LinuxVersion[]
  icon: typeof Monitor
  colorClass: string
  onDelete: (version: string, arch?: string) => void
  onDownload: (version: LinuxVersion, customUrl?: string, arch?: string) => Promise<void>
  onCancel: (version: string, arch?: string) => Promise<void>
  downloadStatus: Record<string, LinuxISODownloadStatus>
  actionLoading: string | null
  isAdmin: boolean
  hostArch?: 'x86_64' | 'arm64'
}) {
  const bgClass = `bg-${colorClass}-50`
  const textClass = `text-${colorClass}-800`
  const badgeBgClass = `bg-${colorClass}-100`
  const badgeTextClass = `text-${colorClass}-800`

  return (
    <div className="bg-white shadow rounded-lg overflow-hidden">
      <div className={clsx("px-6 py-4 border-b border-gray-200", bgClass)}>
        <h4 className={clsx("text-sm font-medium flex items-center", textClass)}>
          <Icon className="h-4 w-4 mr-2" />
          {title} ({versions.length})
        </h4>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 p-4">
        {versions.map((v) => {
          // Check for architecture-specific downloads
          const x86Key = `${v.version}-x86_64`
          const arm64Key = `${v.version}-arm64`
          const x86Status = downloadStatus[x86Key] || downloadStatus[v.version]
          const arm64Status = downloadStatus[arm64Key]
          const isDownloadingX86 = x86Status?.status === 'downloading'
          const isDownloadingArm64 = arm64Status?.status === 'downloading'

          // Architecture-specific loading states
          const isLoadingX86 = actionLoading === `download-linux-${x86Key}` ||
                              actionLoading === `delete-linux-${x86Key}` ||
                              actionLoading === `download-linux-${v.version}` ||
                              actionLoading === `delete-linux-${v.version}`
          const isLoadingArm64 = actionLoading === `download-linux-${arm64Key}` ||
                                actionLoading === `delete-linux-${arm64Key}`

          // Check cached status
          const cachedX86 = v.cached_x86_64 || (hostArch === 'x86_64' && v.cached)
          const cachedArm64 = v.cached_arm64 || (hostArch === 'arm64' && v.cached)

          return (
            <div key={v.version} className={clsx(
              "border rounded-lg p-4",
              (cachedX86 || cachedArm64) ? "bg-green-50 border-green-200" : "hover:bg-gray-50"
            )}>
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-gray-900 truncate">{v.name}</p>
                  <div className="flex items-center gap-2 mt-1 flex-wrap">
                    <code className={clsx("px-2 py-0.5 rounded text-xs font-mono", badgeBgClass, badgeTextClass)}>
                      {v.version}
                    </code>
                    <span className="text-sm text-gray-500">{v.size_gb} GB</span>
                    {v.arm64_available && (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-700" title="ARM64 version available">
                        ARM64
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-500 mt-2">{v.description}</p>

                  {/* Architecture-specific cache status */}
                  <div className="flex items-center gap-2 mt-2 flex-wrap">
                    {cachedX86 && (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
                        <Check className="h-2.5 w-2.5 mr-0.5" />
                        x86_64
                      </span>
                    )}
                    {cachedArm64 && (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
                        <Check className="h-2.5 w-2.5 mr-0.5" />
                        ARM64
                      </span>
                    )}
                  </div>

                  {/* x86_64 Download progress */}
                  {isDownloadingX86 && x86Status && (
                    <div className="mt-3 space-y-1.5">
                      <div className="flex justify-between items-center text-xs">
                        <span className="text-blue-700 font-medium">
                          x86_64: {x86Status.progress_gb?.toFixed(2) || '0.00'} GB
                          {x86Status.total_gb ? ` / ${x86Status.total_gb.toFixed(2)} GB` : ''}
                        </span>
                        <div className="flex items-center gap-2">
                          {x86Status.progress_percent && (
                            <span className="text-blue-600 font-semibold">{x86Status.progress_percent}%</span>
                          )}
                          {isAdmin && (
                            <button
                              onClick={() => onCancel(v.version, 'x86_64')}
                              disabled={actionLoading === `cancel-linux-${x86Key}`}
                              className="text-red-500 hover:text-red-700 p-0.5 rounded hover:bg-red-50"
                              title="Cancel download"
                            >
                              <X className="h-4 w-4" />
                            </button>
                          )}
                        </div>
                      </div>
                      <div className="w-full bg-blue-100 rounded-full h-2 overflow-hidden">
                        {x86Status.total_bytes && x86Status.progress_bytes ? (
                          <div
                            className="bg-gradient-to-r from-blue-500 to-blue-600 h-2 rounded-full transition-all duration-500 ease-out"
                            style={{ width: `${x86Status.progress_percent || 0}%` }}
                          />
                        ) : (
                          <div className="bg-gradient-to-r from-blue-400 via-blue-500 to-blue-400 h-2 rounded-full animate-pulse w-full opacity-60" />
                        )}
                      </div>
                    </div>
                  )}

                  {/* ARM64 Download progress */}
                  {isDownloadingArm64 && arm64Status && (
                    <div className="mt-3 space-y-1.5">
                      <div className="flex justify-between items-center text-xs">
                        <span className="text-purple-700 font-medium">
                          ARM64: {arm64Status.progress_gb?.toFixed(2) || '0.00'} GB
                          {arm64Status.total_gb ? ` / ${arm64Status.total_gb.toFixed(2)} GB` : ''}
                        </span>
                        <div className="flex items-center gap-2">
                          {arm64Status.progress_percent && (
                            <span className="text-purple-600 font-semibold">{arm64Status.progress_percent}%</span>
                          )}
                          {isAdmin && (
                            <button
                              onClick={() => onCancel(v.version, 'arm64')}
                              disabled={actionLoading === `cancel-linux-${arm64Key}`}
                              className="text-red-500 hover:text-red-700 p-0.5 rounded hover:bg-red-50"
                              title="Cancel download"
                            >
                              <X className="h-4 w-4" />
                            </button>
                          )}
                        </div>
                      </div>
                      <div className="w-full bg-purple-100 rounded-full h-2 overflow-hidden">
                        {arm64Status.total_bytes && arm64Status.progress_bytes ? (
                          <div
                            className="bg-gradient-to-r from-purple-500 to-purple-600 h-2 rounded-full transition-all duration-500 ease-out"
                            style={{ width: `${arm64Status.progress_percent || 0}%` }}
                          />
                        ) : (
                          <div className="bg-gradient-to-r from-purple-400 via-purple-500 to-purple-400 h-2 rounded-full animate-pulse w-full opacity-60" />
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Action buttons */}
              <div className="mt-3 flex items-center gap-2 flex-wrap">
                {/* x86_64 actions */}
                {cachedX86 ? (
                  <div className="flex items-center gap-1">
                    {isAdmin && (
                      <button
                        onClick={() => onDelete(v.version, 'x86_64')}
                        disabled={isLoadingX86}
                        className="p-1 text-red-600 hover:bg-red-50 rounded"
                        title="Delete x86_64 ISO"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                ) : isDownloadingX86 ? (
                  <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                    <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                    x86_64
                  </span>
                ) : v.download_url ? (
                  isAdmin && (
                    <button
                      onClick={() => onDownload(v, undefined, 'x86_64')}
                      disabled={isLoadingX86}
                      className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-blue-50 text-blue-700 hover:bg-blue-100"
                    >
                      {isLoadingX86 ? (
                        <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                      ) : (
                        <Download className="h-3 w-3 mr-1" />
                      )}
                      x86_64
                    </button>
                  )
                ) : (
                  <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-600" title={v.download_note}>
                    Auto-download
                  </span>
                )}

                {/* ARM64 actions (only if available) */}
                {v.arm64_available && (
                  <>
                    {cachedArm64 ? (
                      <div className="flex items-center gap-1">
                        {isAdmin && (
                          <button
                            onClick={() => onDelete(v.version, 'arm64')}
                            disabled={isLoadingArm64}
                            className="p-1 text-red-600 hover:bg-red-50 rounded"
                            title="Delete ARM64 ISO"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </div>
                    ) : isDownloadingArm64 ? (
                      <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                        <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                        ARM64
                      </span>
                    ) : (
                      isAdmin && (
                        <button
                          onClick={() => onDownload(v, undefined, 'arm64')}
                          disabled={isLoadingArm64}
                          className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-purple-50 text-purple-700 hover:bg-purple-100"
                        >
                          {isLoadingArm64 ? (
                            <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                          ) : (
                            <Download className="h-3 w-3 mr-1" />
                          )}
                          ARM64
                        </button>
                      )
                    )}
                  </>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
