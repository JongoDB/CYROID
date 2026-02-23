// frontend/src/pages/CatalogItemDetail.tsx
import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  catalogApi,
  type CatalogItemDetail as CatalogItemDetailType,
} from '../services/api'
import { useAuthStore } from '../stores/authStore'
import { toast } from '../stores/toastStore'
import {
  Loader2,
  ArrowLeft,
  Download,
  Check,
  ArrowUpCircle,
  Server,
  FileText,
  Layers,
  BookOpen,
  Package,
  Tag,
  Hash,
  HardDrive,
} from 'lucide-react'
import clsx from 'clsx'

const TYPE_BADGE_COLORS: Record<string, string> = {
  blueprint: 'bg-indigo-100 text-indigo-800',
  scenario: 'bg-emerald-100 text-emerald-800',
  image: 'bg-blue-100 text-blue-800',
  base_image: 'bg-orange-100 text-orange-800',
  content: 'bg-pink-100 text-pink-800',
}

const TYPE_ICONS: Record<string, React.ElementType> = {
  blueprint: Layers,
  scenario: FileText,
  image: Server,
  base_image: HardDrive,
  content: BookOpen,
}

export default function CatalogItemDetail() {
  const { sourceId, itemId } = useParams<{ sourceId: string; itemId: string }>()
  const { user } = useAuthStore()
  const isAdmin = user?.roles?.includes('admin') ?? false

  const [item, setItem] = useState<CatalogItemDetailType | null>(null)
  const [loading, setLoading] = useState(true)
  const [installing, setInstalling] = useState(false)

  useEffect(() => {
    if (!sourceId || !itemId) return

    const fetchDetail = async () => {
      setLoading(true)
      try {
        const res = await catalogApi.getItemDetail(sourceId, decodeURIComponent(itemId))
        setItem(res.data)
      } catch (err: any) {
        toast.error(err.response?.data?.detail || 'Failed to load item details')
      } finally {
        setLoading(false)
      }
    }

    fetchDetail()
  }, [sourceId, itemId])

  const handleInstall = async () => {
    if (!item || !sourceId) return
    setInstalling(true)
    try {
      await catalogApi.installItem(item.id, {
        source_id: sourceId,
        build_images: true,
      })
      toast.success(`Installed "${item.name}" successfully`)
      // Refresh detail to update install status
      const res = await catalogApi.getItemDetail(sourceId, decodeURIComponent(itemId!))
      setItem(res.data)
    } catch (err: any) {
      toast.error(err.response?.data?.detail || `Failed to install "${item.name}"`)
    } finally {
      setInstalling(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    )
  }

  if (!item) {
    return (
      <div className="text-center py-12">
        <Package className="mx-auto h-12 w-12 text-gray-400" />
        <h3 className="mt-2 text-sm font-medium text-gray-900">Item Not Found</h3>
        <p className="mt-1 text-sm text-gray-500">
          The requested catalog item could not be found.
        </p>
        <div className="mt-4">
          <Link
            to="/catalog"
            className="inline-flex items-center text-sm text-primary-600 hover:text-primary-700"
          >
            <ArrowLeft className="h-4 w-4 mr-1" />
            Back to Catalog
          </Link>
        </div>
      </div>
    )
  }

  const TypeIcon = TYPE_ICONS[item.type] || Package

  return (
    <div>
      {/* Breadcrumb */}
      <nav className="mb-6">
        <Link
          to="/catalog"
          className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700"
        >
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back to Catalog
        </Link>
      </nav>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main Content */}
        <div className="lg:col-span-2">
          {/* Header */}
          <div className="bg-white shadow rounded-lg p-6">
            <div className="flex items-start justify-between">
              <div className="flex items-start gap-4">
                <div className={clsx(
                  'flex-shrink-0 rounded-lg p-3',
                  item.type === 'blueprint' ? 'bg-indigo-100' :
                  item.type === 'scenario' ? 'bg-emerald-100' :
                  item.type === 'image' ? 'bg-blue-100' :
                  item.type === 'content' ? 'bg-pink-100' : 'bg-gray-100'
                )}>
                  <TypeIcon className={clsx(
                    'h-8 w-8',
                    item.type === 'blueprint' ? 'text-indigo-600' :
                    item.type === 'scenario' ? 'text-emerald-600' :
                    item.type === 'image' ? 'text-blue-600' :
                    item.type === 'content' ? 'text-pink-600' : 'text-gray-600'
                  )} />
                </div>
                <div>
                  <h1 className="text-2xl font-bold text-gray-900">{item.name}</h1>
                  <div className="mt-1 flex items-center gap-3">
                    <span className={clsx(
                      'inline-flex items-center px-2.5 py-0.5 rounded text-xs font-medium capitalize',
                      TYPE_BADGE_COLORS[item.type]
                    )}>
                      {item.type}
                    </span>
                    <span className="text-sm text-gray-500">v{item.version}</span>
                  </div>
                  {item.description && (
                    <p className="mt-2 text-sm text-gray-600">{item.description}</p>
                  )}
                </div>
              </div>
            </div>

            {/* Tags */}
            {item.tags.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-2">
                {item.tags.map((tag) => (
                  <span
                    key={tag}
                    className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700"
                  >
                    <Tag className="h-3 w-3 mr-1" />
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* README Content */}
          {item.readme && (
            <div className="mt-6 bg-white shadow rounded-lg p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Documentation</h2>
              <div className="prose prose-sm max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {item.readme}
                </ReactMarkdown>
              </div>
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Install Card */}
          <div className="bg-white shadow rounded-lg p-6">
            <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-4">Actions</h3>

            {item.installed ? (
              item.update_available ? (
                <div className="space-y-3">
                  <div className="flex items-center text-amber-700 bg-amber-50 rounded-md p-3 text-sm">
                    <ArrowUpCircle className="h-5 w-5 mr-2 flex-shrink-0" />
                    An update is available
                  </div>
                  {isAdmin && (
                    <button
                      onClick={handleInstall}
                      disabled={installing}
                      className="w-full inline-flex items-center justify-center px-4 py-2 text-sm font-medium rounded-md text-white bg-amber-600 hover:bg-amber-700 disabled:opacity-50"
                    >
                      {installing ? (
                        <>
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          Updating...
                        </>
                      ) : (
                        <>
                          <ArrowUpCircle className="h-4 w-4 mr-2" />
                          Update to v{item.version}
                        </>
                      )}
                    </button>
                  )}
                </div>
              ) : (
                <div className="flex items-center text-green-700 bg-green-50 rounded-md p-3 text-sm">
                  <Check className="h-5 w-5 mr-2 flex-shrink-0" />
                  Installed {item.installed_version && `(v${item.installed_version})`}
                </div>
              )
            ) : isAdmin ? (
              <button
                onClick={handleInstall}
                disabled={installing}
                className="w-full inline-flex items-center justify-center px-4 py-2 text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700 disabled:opacity-50"
              >
                {installing ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Installing...
                  </>
                ) : (
                  <>
                    <Download className="h-4 w-4 mr-2" />
                    Install
                  </>
                )}
              </button>
            ) : (
              <p className="text-sm text-gray-500">
                Only administrators can install catalog items.
              </p>
            )}
          </div>

          {/* Metadata Card */}
          <div className="bg-white shadow rounded-lg p-6">
            <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-4">Details</h3>
            <dl className="space-y-3 text-sm">
              <div className="flex justify-between">
                <dt className="text-gray-500">Version</dt>
                <dd className="font-medium text-gray-900">{item.version}</dd>
              </div>
              {item.checksum && (
                <div className="flex justify-between">
                  <dt className="text-gray-500 flex items-center">
                    <Hash className="h-3 w-3 mr-1" />
                    Checksum
                  </dt>
                  <dd className="font-mono text-xs text-gray-600 truncate max-w-[120px]" title={item.checksum}>
                    {item.checksum}
                  </dd>
                </div>
              )}
              {item.arch && (
                <div className="flex justify-between">
                  <dt className="text-gray-500">Architecture</dt>
                  <dd className="font-medium text-gray-900">{item.arch}</dd>
                </div>
              )}
              {item.docker_tag && (
                <div className="flex justify-between">
                  <dt className="text-gray-500">Docker Tag</dt>
                  <dd className="font-mono text-xs text-gray-600 truncate max-w-[160px]" title={item.docker_tag}>
                    {item.docker_tag}
                  </dd>
                </div>
              )}
            </dl>
          </div>

          {/* Dependencies (blueprint-specific) */}
          {(item.requires_images.length > 0 || (item.requires_base_images && item.requires_base_images.length > 0)) && (
            <div className="bg-white shadow rounded-lg p-6">
              <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-4">Required Images</h3>
              <ul className="space-y-2">
                {item.requires_images.map((img) => (
                  <li key={img} className="flex items-center text-sm text-gray-700">
                    <Server className="h-4 w-4 mr-2 text-gray-400" />
                    {img}
                  </li>
                ))}
                {item.requires_base_images && item.requires_base_images.map((img) => (
                  <li key={img} className="flex items-center text-sm text-gray-700">
                    <Server className="h-4 w-4 mr-2 text-blue-400" />
                    {img} <span className="ml-1 text-xs text-gray-400">(base image)</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Content Indicators */}
          {(item.includes_msel || item.includes_content) && (
            <div className="bg-white shadow rounded-lg p-6">
              <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-4">Includes</h3>
              <ul className="space-y-2">
                {item.includes_msel && (
                  <li className="flex items-center text-sm text-gray-700">
                    <FileText className="h-4 w-4 mr-2 text-emerald-500" />
                    MSEL (Master Scenario Events List)
                  </li>
                )}
                {item.includes_content && (
                  <li className="flex items-center text-sm text-gray-700">
                    <BookOpen className="h-4 w-4 mr-2 text-pink-500" />
                    Student Walkthrough
                  </li>
                )}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
