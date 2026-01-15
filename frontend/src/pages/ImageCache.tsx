// frontend/src/pages/ImageCache.tsx
import { useState, useEffect, useRef } from 'react'
import { cacheApi, DockerPullStatus } from '../services/api'
import { useAuthStore } from '../stores/authStore'
import type {
  CachedImage,
  AllSnapshotsStatus,
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
  Database,
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
} from 'lucide-react'
import clsx from 'clsx'

type TabType = 'overview' | 'docker' | 'isos' | 'linux-isos' | 'custom-isos' | 'snapshots'

export default function ImageCache() {
  const { user } = useAuthStore()
  const isAdmin = user?.roles?.includes('admin') ?? false
  const [activeTab, setActiveTab] = useState<TabType>('overview')
  const [stats, setStats] = useState<CacheStats | null>(null)
  const [images, setImages] = useState<CachedImage[]>([])
  const [allSnapshots, setAllSnapshots] = useState<AllSnapshotsStatus | null>(null)
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
  const [showUploadModal, setShowUploadModal] = useState<'windows' | 'custom' | null>(null)
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

  const loadData = async () => {
    setLoading(true)
    setError(null)
    try {
      const [statsRes, imagesRes, snapshotsRes, recommendedRes, windowsRes, linuxRes, customISOsRes] = await Promise.all([
        cacheApi.getStats(),
        cacheApi.listImages(),
        cacheApi.getAllSnapshots(),
        cacheApi.getRecommendedImages(),
        cacheApi.getWindowsVersions(),
        cacheApi.getLinuxVersions(),
        cacheApi.listCustomISOs(),
      ])
      setStats(statsRes.data)
      setImages(imagesRes.data)
      setAllSnapshots(snapshotsRes.data)
      setRecommended(recommendedRes.data)
      setWindowsVersions(windowsRes.data)
      setLinuxVersions(linuxRes.data)
      setCustomISOs(customISOsRes.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load cache data')
    } finally {
      setLoading(false)
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

  useEffect(() => {
    loadData()
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

  const handleRemoveImage = async (imageId: string, tag: string) => {
    if (!confirm(`Remove cached image ${tag}?`)) return

    setActionLoading(imageId)
    setError(null)
    try {
      await cacheApi.removeImage(imageId)
      setSuccess(`Removed ${tag}`)
      await loadData()
    } catch (err: any) {
      setError(err.response?.data?.detail || `Failed to remove ${tag}`)
    } finally {
      setActionLoading(null)
    }
  }

  const handleDeleteSnapshot = async (snapshotType: 'windows' | 'docker', name: string) => {
    const typeLabel = snapshotType === 'windows' ? 'Windows golden image' : 'Docker snapshot'
    if (!confirm(`Delete ${typeLabel} "${name}"? This cannot be undone.`)) return

    setActionLoading(`snapshot-${snapshotType}-${name}`)
    setError(null)
    try {
      await cacheApi.deleteSnapshot(snapshotType, name)
      setSuccess(`Deleted ${typeLabel}: ${name}`)
      await loadData()
    } catch (err: any) {
      setError(err.response?.data?.detail || `Failed to delete ${name}`)
    } finally {
      setActionLoading(null)
    }
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

  const handleDeleteCustomISO = async (filename: string, name: string) => {
    if (!confirm(`Delete custom ISO "${name}"? This cannot be undone.`)) return

    setActionLoading(`custom-iso-${filename}`)
    setError(null)
    try {
      await cacheApi.deleteCustomISO(filename)
      setSuccess(`Deleted custom ISO: ${name}`)
      // Clear download status
      setCustomISODownloadStatus(prev => {
        const newStatus = { ...prev }
        delete newStatus[filename]
        return newStatus
      })
      await loadData()
    } catch (err: any) {
      setError(err.response?.data?.detail || `Failed to delete ${name}`)
    } finally {
      setActionLoading(null)
    }
  }

  const handleDeleteWindowsISO = async (version: string, name: string) => {
    if (!confirm(`Delete Windows ISO "${name}" (${version})? This cannot be undone.`)) return

    setActionLoading(`windows-iso-${version}`)
    setError(null)
    try {
      await cacheApi.deleteWindowsISO(version)
      setSuccess(`Deleted Windows ISO: ${name}`)
      await loadData()
    } catch (err: any) {
      setError(err.response?.data?.detail || `Failed to delete ${name}`)
    } finally {
      setActionLoading(null)
    }
  }

  const handleDownloadWindowsISO = async (version: WindowsVersion, customUrl?: string) => {
    setActionLoading(`download-${version.version}`)
    setError(null)

    try {
      const res = await cacheApi.downloadWindowsISO(version.version, customUrl)

      // Handle no direct download available
      if (res.data.status === 'no_direct_download') {
        setError(res.data.message || 'No direct download available for this version')
        setActionLoading(null)
        return
      }

      // Start polling for download status
      setDownloadStatus(prev => ({
        ...prev,
        [version.version]: { status: 'downloading', version: version.version, progress_gb: 0 }
      }))

      // Poll for status
      const pollInterval = setInterval(async () => {
        try {
          const statusRes = await cacheApi.getWindowsISODownloadStatus(version.version)
          setDownloadStatus(prev => ({
            ...prev,
            [version.version]: statusRes.data
          }))

          if (statusRes.data.status === 'completed' || statusRes.data.status === 'failed') {
            clearInterval(pollInterval)
            setActionLoading(null)

            if (statusRes.data.status === 'completed') {
              setSuccess(`Downloaded ${version.name} ISO successfully!`)
              await loadData()
            } else if (statusRes.data.error) {
              setError(`Download failed: ${statusRes.data.error}`)
            }

            // Clear download status after a delay
            setTimeout(() => {
              setDownloadStatus(prev => {
                const newStatus = { ...prev }
                delete newStatus[version.version]
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

  const handleDownloadLinuxISO = async (version: LinuxVersion, customUrl?: string) => {
    setActionLoading(`download-linux-${version.version}`)
    setError(null)

    try {
      const res = await cacheApi.downloadLinuxISO(version.version, customUrl)

      // Handle no direct download available
      if (res.data.status === 'no_direct_download') {
        setError(res.data.message || 'No direct download available for this distribution')
        setActionLoading(null)
        return
      }

      // Start polling for download status
      setLinuxDownloadStatus(prev => ({
        ...prev,
        [version.version]: { status: 'downloading', version: version.version, progress_gb: 0 }
      }))

      // Poll for status
      const pollInterval = setInterval(async () => {
        try {
          const statusRes = await cacheApi.getLinuxISODownloadStatus(version.version)
          setLinuxDownloadStatus(prev => ({
            ...prev,
            [version.version]: statusRes.data
          }))

          if (statusRes.data.status === 'completed' || statusRes.data.status === 'failed') {
            clearInterval(pollInterval)
            setActionLoading(null)

            if (statusRes.data.status === 'completed') {
              setSuccess(`Downloaded ${version.name} ISO successfully!`)
              await loadData()
            } else if (statusRes.data.error) {
              setError(`Download failed: ${statusRes.data.error}`)
            }

            // Clear download status after a delay
            setTimeout(() => {
              setLinuxDownloadStatus(prev => {
                const newStatus = { ...prev }
                delete newStatus[version.version]
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

  const handleDeleteLinuxISO = async (version: string) => {
    if (!confirm(`Delete Linux ISO for ${version}?`)) return

    setActionLoading(`delete-linux-${version}`)
    setError(null)
    try {
      await cacheApi.deleteLinuxISO(version)
      setSuccess(`Deleted Linux ISO: ${version}`)
      // Clear download status
      setLinuxDownloadStatus(prev => {
        const newStatus = { ...prev }
        delete newStatus[version]
        return newStatus
      })
      await loadData()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete ISO')
    } finally {
      setActionLoading(null)
    }
  }

  const handleCancelLinuxDownload = async (version: string) => {
    setActionLoading(`cancel-linux-${version}`)
    setError(null)
    try {
      await cacheApi.cancelLinuxISODownload(version)
      setSuccess(`Cancelled download for ${version}`)
      setLinuxDownloadStatus(prev => {
        const newStatus = { ...prev }
        delete newStatus[version]
        return newStatus
      })
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to cancel download')
    } finally {
      setActionLoading(null)
    }
  }

  const handleCancelWindowsDownload = async (version: string) => {
    setActionLoading(`cancel-windows-${version}`)
    setError(null)
    try {
      await cacheApi.cancelWindowsISODownload(version)
      setSuccess(`Cancelled download for ${version}`)
      setDownloadStatus(prev => {
        const newStatus = { ...prev }
        delete newStatus[version]
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
    { id: 'isos' as const, name: 'Windows ISOs', icon: Monitor },
    { id: 'linux-isos' as const, name: 'Linux ISOs', icon: Terminal },
    { id: 'custom-isos' as const, name: 'Custom ISOs', icon: Download },
    { id: 'snapshots' as const, name: 'Snapshots', icon: Database },
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
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
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
                <Database className="h-8 w-8 text-green-500" />
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-500">Snapshots</p>
                  <p className="text-2xl font-semibold text-gray-900">
                    {(allSnapshots?.total_windows || 0) + (allSnapshots?.total_docker || 0)}
                  </p>
                  <p className="text-sm text-gray-500">
                    {allSnapshots?.total_windows || 0} Windows, {allSnapshots?.total_docker || 0} Docker
                  </p>
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

          {isAdmin && (
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Quick Actions</h3>
            <div className="flex flex-wrap gap-3">
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
                onClick={() => setShowUploadModal('custom')}
                className="inline-flex items-center px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700"
              >
                <Upload className="h-4 w-4 mr-2" />
                Upload Custom ISO
              </button>
            </div>
          </div>
          )}
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

      {/* Windows ISOs Tab */}
      {activeTab === 'isos' && windowsVersions && (
        <div className="space-y-6">
          <div className="flex justify-between items-center">
            <div>
              <h3 className="text-lg font-medium text-gray-900">Windows ISOs</h3>
              <p className="text-sm text-gray-500">
                {windowsVersions.cached_count} of {windowsVersions.total_count} versions cached
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
          />
        </div>
      )}

      {/* Linux ISOs Tab */}
      {activeTab === 'linux-isos' && linuxVersions && (
        <div className="space-y-6">
          <div className="flex justify-between items-center">
            <div>
              <h3 className="text-lg font-medium text-gray-900">Linux Distributions (qemus/qemu)</h3>
              <p className="text-sm text-gray-500">
                {linuxVersions.cached_count} of {linuxVersions.total_count} distributions cached
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

      {/* Snapshots Tab - Both Windows Golden Images and Docker Snapshots */}
      {activeTab === 'snapshots' && allSnapshots && (
        <div className="space-y-6">
          <div className="flex justify-between items-center">
            <div>
              <h3 className="text-lg font-medium text-gray-900">VM Snapshots</h3>
              <p className="text-sm text-gray-500">
                Pre-configured VM templates for instant deployment
              </p>
            </div>
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex">
              <Info className="h-5 w-5 text-blue-500 mt-0.5 mr-3" />
              <div>
                <h4 className="text-sm font-medium text-blue-800">Creating Snapshots</h4>
                <ol className="mt-2 text-sm text-blue-700 list-decimal list-inside space-y-1">
                  <li>Deploy and configure a VM (Windows or Linux)</li>
                  <li>Install required software and configure settings</li>
                  <li>From the VM details page, use "Create Snapshot" action</li>
                  <li>New VMs can be instantly cloned from the snapshot</li>
                </ol>
              </div>
            </div>
          </div>

          {/* Windows Golden Images Section */}
          <div className="bg-white shadow rounded-lg overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200 bg-purple-50">
              <h4 className="text-sm font-medium text-purple-800 flex items-center">
                <Monitor className="h-4 w-4 mr-2" />
                Windows Golden Images ({allSnapshots.total_windows})
              </h4>
              <p className="text-xs text-purple-600 mt-1">Full disk snapshots for Windows VMs</p>
            </div>
            {allSnapshots.windows_golden_images.length > 0 ? (
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Size</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Path</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {allSnapshots.windows_golden_images.map((golden) => (
                    <tr key={golden.name}>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        {golden.name}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {golden.size_gb} GB
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 font-mono text-xs">
                        {golden.path}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right">
                        {isAdmin && (
                          <button
                            onClick={() => handleDeleteSnapshot('windows', golden.name)}
                            disabled={actionLoading === `snapshot-windows-${golden.name}`}
                            className="text-red-600 hover:text-red-900 disabled:opacity-50"
                            title="Delete snapshot"
                          >
                            {actionLoading === `snapshot-windows-${golden.name}` ? (
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
                <Monitor className="h-10 w-10 text-gray-300 mx-auto mb-2" />
                No Windows golden images yet. Create one from a running Windows VM.
              </div>
            )}
          </div>

          {/* Docker Container Snapshots Section */}
          <div className="bg-white shadow rounded-lg overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200 bg-green-50">
              <h4 className="text-sm font-medium text-green-800 flex items-center">
                <Server className="h-4 w-4 mr-2" />
                Docker Snapshots ({allSnapshots.total_docker})
              </h4>
              <p className="text-xs text-green-600 mt-1">Container commits for Linux VMs and custom containers</p>
            </div>
            {allSnapshots.docker_snapshots.length > 0 ? (
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Image ID</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Size</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Created</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {allSnapshots.docker_snapshots.map((snapshot) => {
                    // Extract name from tags (e.g., "cyroid/snapshot/my-snapshot:latest" -> "my-snapshot")
                    const fullTag = snapshot.tags[0] || snapshot.short_id
                    const snapshotName = fullTag.includes('cyroid/snapshot/')
                      ? fullTag.replace('cyroid/snapshot/', '').replace(':latest', '')
                      : fullTag
                    return (
                      <tr key={snapshot.id}>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                          {snapshotName}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 font-mono">
                          {snapshot.short_id}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {snapshot.size_gb} GB
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {snapshot.created ? new Date(snapshot.created).toLocaleDateString() : 'Unknown'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-right">
                          {isAdmin && (
                            <button
                              onClick={() => handleDeleteSnapshot('docker', snapshotName)}
                              disabled={actionLoading === `snapshot-docker-${snapshotName}`}
                              className="text-red-600 hover:text-red-900 disabled:opacity-50"
                              title="Delete snapshot"
                            >
                              {actionLoading === `snapshot-docker-${snapshotName}` ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <Trash2 className="h-4 w-4" />
                              )}
                            </button>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            ) : (
              <div className="px-6 py-8 text-center text-gray-500">
                <Server className="h-10 w-10 text-gray-300 mx-auto mb-2" />
                No Docker snapshots yet. Create one from a running Linux VM or container.
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
                  Upload {showUploadModal === 'windows' ? 'Windows' : 'Custom'} ISO
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
                  disabled={actionLoading === 'upload' || !uploadFile || (showUploadModal === 'windows' ? !uploadVersion : !uploadName)}
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
                  <p className="font-medium text-gray-900 truncate" title={imageName}>{imageName}</p>
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
                >
                  {actionLoading === image.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                </button>
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function WindowsVersionSection({ title, versions, icon: Icon, colorClass, onDelete, onDownload, onCancel, downloadStatus, actionLoading, isAdmin }: {
  title: string
  versions: WindowsVersion[]
  icon: typeof Monitor
  colorClass: string
  onDelete: (version: string, name: string) => void
  onDownload: (version: WindowsVersion) => void
  onCancel: (version: string) => void
  downloadStatus: Record<string, WindowsISODownloadStatus>
  actionLoading: string | null
  isAdmin: boolean
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
          const dlStatus = downloadStatus[v.version]
          const isDownloading = dlStatus?.status === 'downloading'

          return (
            <div key={v.version} className={clsx(
              "border rounded-lg p-4",
              v.cached ? "bg-green-50 border-green-200" :
              isDownloading ? "bg-blue-50 border-blue-200" : "hover:bg-gray-50"
            )}>
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-gray-900 truncate">{v.name}</p>
                  <div className="flex items-center gap-2 mt-1 flex-wrap">
                    <code className={clsx("px-2 py-0.5 rounded text-xs font-mono", badgeBgClass, badgeTextClass)}>
                      {v.version}
                    </code>
                    <span className="text-sm text-gray-500">{v.size_gb} GB</span>
                  </div>
                </div>
                <div className="flex items-center gap-1 ml-2 flex-shrink-0">
                  {isDownloading ? (
                    <div className="flex items-center gap-1 text-blue-600">
                      <Loader2 className="h-4 w-4 animate-spin flex-shrink-0" />
                      <span className="text-xs font-medium">
                        {dlStatus.progress_percent ? `${dlStatus.progress_percent}%` : 'Starting...'}
                      </span>
                    </div>
                  ) : v.cached ? (
                    <>
                      <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                        <Check className="h-3 w-3 mr-1" />
                        Cached
                      </span>
                      {isAdmin && (
                        <button
                          onClick={() => onDelete(v.version, v.name)}
                          disabled={actionLoading === `windows-iso-${v.version}`}
                          className="text-red-600 hover:text-red-900 disabled:opacity-50 p-1"
                          title="Delete cached ISO"
                        >
                          {actionLoading === `windows-iso-${v.version}` ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Trash2 className="h-4 w-4" />
                          )}
                        </button>
                      )}
                    </>
                  ) : isAdmin ? (
                    <button
                      onClick={() => onDownload(v)}
                      disabled={actionLoading === `download-${v.version}`}
                      className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-blue-100 text-blue-700 hover:bg-blue-200 disabled:opacity-50"
                      title="Download ISO"
                    >
                      {actionLoading === `download-${v.version}` ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : (
                        <>
                          <Download className="h-3 w-3 mr-1" />
                          Download
                        </>
                      )}
                    </button>
                  ) : (
                    <span className="text-xs text-gray-400">Not cached</span>
                  )}
                </div>
              </div>
              {/* Download progress bar */}
              {isDownloading && (
                <div className="mt-3 space-y-1.5">
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-blue-700 font-medium">
                      {dlStatus.progress_gb?.toFixed(2) || '0.00'} GB
                      {dlStatus.total_gb ? ` / ${dlStatus.total_gb.toFixed(2)} GB` : ''}
                    </span>
                    <div className="flex items-center gap-2">
                      {dlStatus.progress_percent && (
                        <span className="text-blue-600 font-semibold">{dlStatus.progress_percent}%</span>
                      )}
                      {isAdmin && (
                        <button
                          onClick={() => onCancel(v.version)}
                          disabled={actionLoading === `cancel-windows-${v.version}`}
                          className="text-red-500 hover:text-red-700 p-0.5 rounded hover:bg-red-50"
                          title="Cancel download"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      )}
                    </div>
                  </div>
                  <div className="w-full bg-blue-100 rounded-full h-2.5 overflow-hidden">
                    {dlStatus.total_bytes && dlStatus.progress_bytes ? (
                      <div
                        className="bg-gradient-to-r from-blue-500 to-blue-600 h-2.5 rounded-full transition-all duration-500 ease-out"
                        style={{ width: `${(dlStatus.progress_bytes / dlStatus.total_bytes) * 100}%` }}
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

function ImageCheckbox({ img, selected, setSelected }: {
  img: { image?: string; description: string; cached?: boolean }
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
        <p className="text-sm font-medium truncate">{img.image}</p>
        <p className="text-xs text-gray-500 truncate">{img.description}</p>
      </div>
      {isCached && (
        <Check className="h-4 w-4 text-green-600 ml-2 flex-shrink-0" />
      )}
    </label>
  )
}

function LinuxVersionSection({ title, versions, icon: Icon, colorClass, onDelete, onDownload, onCancel, downloadStatus, actionLoading, isAdmin }: {
  title: string
  versions: LinuxVersion[]
  icon: typeof Monitor
  colorClass: string
  onDelete: (version: string) => Promise<void>
  onDownload: (version: LinuxVersion, customUrl?: string) => Promise<void>
  onCancel: (version: string) => Promise<void>
  downloadStatus: Record<string, LinuxISODownloadStatus>
  actionLoading: string | null
  isAdmin: boolean
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
          const status = downloadStatus[v.version]
          const isDownloading = status?.status === 'downloading'
          const isLoading = actionLoading === `download-linux-${v.version}` || actionLoading === `delete-linux-${v.version}`

          return (
            <div key={v.version} className={clsx(
              "border rounded-lg p-4",
              v.cached ? "bg-green-50 border-green-200" : "hover:bg-gray-50"
            )}>
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-gray-900 truncate">{v.name}</p>
                  <div className="flex items-center gap-2 mt-1 flex-wrap">
                    <code className={clsx("px-2 py-0.5 rounded text-xs font-mono", badgeBgClass, badgeTextClass)}>
                      {v.version}
                    </code>
                    <span className="text-sm text-gray-500">{v.size_gb} GB</span>
                  </div>
                  <p className="text-xs text-gray-500 mt-2">{v.description}</p>

                  {/* Download progress */}
                  {isDownloading && status && (
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
                              onClick={() => onCancel(v.version)}
                              disabled={actionLoading === `cancel-linux-${v.version}`}
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
                            style={{ width: `${status.progress_percent || 0}%` }}
                          />
                        ) : (
                          <div className="bg-gradient-to-r from-blue-400 via-blue-500 to-blue-400 h-2.5 rounded-full animate-pulse w-full opacity-60" />
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Action buttons */}
              <div className="mt-3 flex items-center gap-2">
                {v.cached ? (
                  <>
                    <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                      <Check className="h-3 w-3 mr-1" />
                      Cached
                    </span>
                    {isAdmin && (
                      <button
                        onClick={() => onDelete(v.version)}
                        disabled={isLoading}
                        className="p-1 text-red-600 hover:bg-red-50 rounded"
                        title="Delete ISO"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    )}
                  </>
                ) : isDownloading ? (
                  <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                    <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                    Downloading
                  </span>
                ) : v.download_url ? (
                  isAdmin && (
                    <button
                      onClick={() => onDownload(v)}
                      disabled={isLoading}
                      className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-blue-50 text-blue-700 hover:bg-blue-100"
                    >
                      {isLoading ? (
                        <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                      ) : (
                        <Download className="h-3 w-3 mr-1" />
                      )}
                      Download
                    </button>
                  )
                ) : (
                  <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-600" title={v.download_note}>
                    Auto-download
                  </span>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
