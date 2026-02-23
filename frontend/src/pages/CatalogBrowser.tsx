// frontend/src/pages/CatalogBrowser.tsx
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  catalogApi,
  type CatalogItemSummary,
  type CatalogItemType,
  type CatalogSource,
} from '../services/api'
import { useAuthStore } from '../stores/authStore'
import { toast } from '../stores/toastStore'
import {
  Loader2,
  Search,
  RefreshCw,
  Store,
  Package,
  FileText,
  Server,
  Layers,
  BookOpen,
  Download,
  Check,
  ArrowUpCircle,
  X,
  AlertCircle,
  ChevronDown,
  Tag,
  HardDrive,
} from 'lucide-react'
import clsx from 'clsx'

type FilterTab = 'all' | CatalogItemType

const TYPE_TABS: { key: FilterTab; label: string; icon: React.ElementType }[] = [
  { key: 'all', label: 'All', icon: Package },
  { key: 'blueprint', label: 'Blueprints', icon: Layers },
  { key: 'scenario', label: 'Scenarios', icon: FileText },
  { key: 'image', label: 'Images', icon: Server },
  { key: 'base_image', label: 'Base Images', icon: HardDrive },
  { key: 'content', label: 'Content', icon: BookOpen },
]

const TYPE_BADGE_COLORS: Record<CatalogItemType, string> = {
  blueprint: 'bg-indigo-100 text-indigo-800',
  scenario: 'bg-emerald-100 text-emerald-800',
  image: 'bg-blue-100 text-blue-800',
  base_image: 'bg-orange-100 text-orange-800',
  content: 'bg-pink-100 text-pink-800',
}

export default function CatalogBrowser() {
  const { user } = useAuthStore()
  const isAdmin = user?.roles?.includes('admin') ?? false

  // Data
  const [items, setItems] = useState<CatalogItemSummary[]>([])
  const [sources, setSources] = useState<CatalogSource[]>([])
  const [loading, setLoading] = useState(true)

  // Filters
  const [activeTab, setActiveTab] = useState<FilterTab>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedSource, setSelectedSource] = useState<string>('')
  const [selectedTags, setSelectedTags] = useState<string[]>([])

  // Installing state
  const [installingItemId, setInstallingItemId] = useState<string | null>(null)

  // Collect all unique tags from items
  const allTags = Array.from(new Set(items.flatMap((item) => item.tags))).sort()

  const fetchSources = async () => {
    try {
      const res = await catalogApi.listSources()
      setSources(res.data)
    } catch {
      // Non-critical: sources dropdown just won't appear
    }
  }

  const fetchItems = async () => {
    setLoading(true)
    try {
      const params: Record<string, string> = {}
      if (activeTab !== 'all') params.item_type = activeTab
      if (selectedSource) params.source_id = selectedSource
      if (searchQuery.trim()) params.search = searchQuery.trim()
      if (selectedTags.length > 0) params.tags = selectedTags.join(',')

      const res = await catalogApi.listItems(params)
      setItems(res.data)
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to load catalog items')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchSources()
  }, [])

  useEffect(() => {
    fetchItems()
  }, [activeTab, selectedSource, selectedTags])

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      fetchItems()
    }, 300)
    return () => clearTimeout(timer)
  }, [searchQuery])

  const handleInstall = async (item: CatalogItemSummary) => {
    // Find which source this item belongs to
    const sourceId = sources.length === 1
      ? sources[0].id
      : selectedSource || sources[0]?.id

    if (!sourceId) {
      toast.error('No catalog source available')
      return
    }

    setInstallingItemId(item.id)
    try {
      await catalogApi.installItem(item.id, {
        source_id: sourceId,
        build_images: true,
      })
      toast.success(`Installed "${item.name}" successfully`)
      // Refresh items to update install status
      fetchItems()
    } catch (err: any) {
      toast.error(err.response?.data?.detail || `Failed to install "${item.name}"`)
    } finally {
      setInstallingItemId(null)
    }
  }

  const toggleTag = (tag: string) => {
    setSelectedTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    )
  }

  const getStatusBadge = (item: CatalogItemSummary) => {
    if (item.update_available) {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800">
          <ArrowUpCircle className="h-3 w-3 mr-1" />
          Update Available
        </span>
      )
    }
    if (item.installed) {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
          <Check className="h-3 w-3 mr-1" />
          Installed {item.installed_version && `v${item.installed_version}`}
        </span>
      )
    }
    return null
  }

  const getActionButton = (item: CatalogItemSummary) => {
    if (installingItemId === item.id) {
      return (
        <button disabled className="inline-flex items-center px-3 py-1.5 text-sm font-medium rounded-md text-white bg-primary-400 cursor-not-allowed">
          <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
          Installing...
        </button>
      )
    }

    if (item.update_available && isAdmin) {
      return (
        <button
          onClick={(e) => { e.preventDefault(); handleInstall(item) }}
          className="inline-flex items-center px-3 py-1.5 text-sm font-medium rounded-md text-white bg-amber-600 hover:bg-amber-700"
        >
          <ArrowUpCircle className="h-4 w-4 mr-1.5" />
          Update
        </button>
      )
    }

    if (item.installed) {
      return (
        <span className="inline-flex items-center px-3 py-1.5 text-sm font-medium rounded-md text-green-700 bg-green-50 border border-green-200">
          <Check className="h-4 w-4 mr-1.5" />
          Installed
        </span>
      )
    }

    if (isAdmin) {
      return (
        <button
          onClick={(e) => { e.preventDefault(); handleInstall(item) }}
          className="inline-flex items-center px-3 py-1.5 text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700"
        >
          <Download className="h-4 w-4 mr-1.5" />
          Install
        </button>
      )
    }

    return null
  }

  // Determine the source_id for linking to detail pages
  const getItemSourceId = (): string => {
    if (selectedSource) return selectedSource
    if (sources.length === 1) return sources[0].id
    return sources.find((s) => s.enabled)?.id || sources[0]?.id || ''
  }

  return (
    <div>
      {/* Header */}
      <div className="sm:flex sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Store className="h-7 w-7" />
            Content Catalog
          </h1>
          <p className="mt-2 text-sm text-gray-700">
            Browse and install training content from catalog sources.
          </p>
        </div>
        <div className="mt-4 sm:mt-0 flex items-center space-x-3">
          {/* Source selector (only if multiple sources) */}
          {sources.length > 1 && (
            <div className="relative">
              <select
                value={selectedSource}
                onChange={(e) => setSelectedSource(e.target.value)}
                className="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm pr-10"
              >
                <option value="">All Sources</option>
                {sources.filter((s) => s.enabled).map((source) => (
                  <option key={source.id} value={source.id}>
                    {source.name} ({source.item_count})
                  </option>
                ))}
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
            </div>
          )}

          <button
            onClick={() => fetchItems()}
            disabled={loading}
            className="p-2 text-gray-400 hover:text-gray-600 disabled:opacity-50"
            title="Refresh catalog"
          >
            <RefreshCw className={clsx('h-5 w-5', loading && 'animate-spin')} />
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="mt-6 space-y-4">
        {/* Type Tabs */}
        <div className="border-b border-gray-200">
          <nav className="-mb-px flex space-x-8" aria-label="Item type filter">
            {TYPE_TABS.map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                onClick={() => setActiveTab(key)}
                className={clsx(
                  'flex items-center whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm',
                  activeTab === key
                    ? 'border-primary-500 text-primary-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                )}
              >
                <Icon className={clsx('mr-2 h-5 w-5', activeTab === key ? 'text-primary-500' : 'text-gray-400')} />
                {label}
              </button>
            ))}
          </nav>
        </div>

        {/* Search + Tag Chips */}
        <div className="flex flex-col sm:flex-row gap-4">
          {/* Search */}
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search catalog items..."
              className="block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>

          {/* Tag chips */}
          {allTags.length > 0 && (
            <div className="flex flex-wrap gap-2 items-center">
              <Tag className="h-4 w-4 text-gray-400" />
              {allTags.map((tag) => (
                <button
                  key={tag}
                  onClick={() => toggleTag(tag)}
                  className={clsx(
                    'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium transition-colors',
                    selectedTags.includes(tag)
                      ? 'bg-primary-100 text-primary-800 ring-1 ring-primary-300'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  )}
                >
                  {tag}
                </button>
              ))}
              {selectedTags.length > 0 && (
                <button
                  onClick={() => setSelectedTags([])}
                  className="text-xs text-gray-500 hover:text-gray-700 underline"
                >
                  Clear tags
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
        </div>
      ) : items.length === 0 ? (
        <div className="mt-12 text-center bg-white shadow rounded-lg p-8">
          {sources.length === 0 ? (
            <>
              <AlertCircle className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-4 text-lg font-medium text-gray-900">No Catalog Sources Configured</h3>
              <p className="mt-2 text-sm text-gray-500 max-w-md mx-auto">
                Add a catalog source in the Admin settings to browse available training content.
              </p>
              {isAdmin && (
                <div className="mt-6">
                  <Link
                    to="/admin"
                    className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700"
                  >
                    Go to Admin Settings
                  </Link>
                </div>
              )}
            </>
          ) : (
            <>
              <Package className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-4 text-lg font-medium text-gray-900">No Items Found</h3>
              <p className="mt-2 text-sm text-gray-500 max-w-md mx-auto">
                {searchQuery || selectedTags.length > 0
                  ? 'Try adjusting your search or filters.'
                  : 'No items available in the configured catalog sources. Try syncing a source.'}
              </p>
            </>
          )}
        </div>
      ) : (
        <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((item) => (
            <Link
              key={item.id}
              to={`/catalog/${getItemSourceId()}/${encodeURIComponent(item.id)}`}
              className="block bg-white overflow-hidden shadow rounded-lg hover:shadow-md transition-shadow"
            >
              <div className="p-5">
                {/* Header: type badge + status */}
                <div className="flex items-center justify-between mb-3">
                  <span className={clsx(
                    'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium capitalize',
                    TYPE_BADGE_COLORS[item.type]
                  )}>
                    {item.type}
                  </span>
                  {getStatusBadge(item)}
                </div>

                {/* Name + Description */}
                <h3 className="text-lg font-medium text-gray-900">{item.name}</h3>
                {item.description && (
                  <p className="mt-1 text-sm text-gray-600 line-clamp-2">{item.description}</p>
                )}

                {/* Tags */}
                {item.tags.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1">
                    {item.tags.map((tag) => (
                      <span
                        key={tag}
                        className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}

                {/* Metadata row */}
                <div className="mt-3 flex items-center gap-4 text-xs text-gray-500">
                  <span>v{item.version}</span>
                  {(item.requires_images.length + (item.requires_base_images?.length || 0)) > 0 && (
                    <span>{item.requires_images.length + (item.requires_base_images?.length || 0)} image{(item.requires_images.length + (item.requires_base_images?.length || 0)) !== 1 && 's'}</span>
                  )}
                  {item.includes_msel && <span>MSEL</span>}
                  {item.includes_content && <span>Walkthrough</span>}
                </div>
              </div>

              {/* Action footer */}
              <div className="bg-gray-50 px-5 py-3 flex justify-end">
                {getActionButton(item)}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
