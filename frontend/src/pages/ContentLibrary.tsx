// frontend/src/pages/ContentLibrary.tsx
import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Plus,
  Search,
  Filter,
  BookOpen,
  FileText,
  GraduationCap,
  Clipboard,
  Book,
  File,
  Edit,
  Trash2,
  Eye,
  EyeOff,
  MoreVertical,
  Download,
  Upload,
  X,
  FileCode,
  FileDown,
} from 'lucide-react'
import { contentApi, ContentListItem, ContentType, ContentImport } from '../services/api'
import { toast } from '../stores/toastStore'
import { formatDistanceToNow } from 'date-fns'
import html2pdf from 'html2pdf.js'

const CONTENT_TYPE_INFO: Record<ContentType, { icon: typeof BookOpen; label: string; color: string }> = {
  student_guide: { icon: GraduationCap, label: 'Student Guide', color: 'bg-blue-100 text-blue-800' },
  msel: { icon: Clipboard, label: 'MSEL', color: 'bg-purple-100 text-purple-800' },
  curriculum: { icon: Book, label: 'Curriculum', color: 'bg-green-100 text-green-800' },
  instructor_notes: { icon: FileText, label: 'Instructor Notes', color: 'bg-orange-100 text-orange-800' },
  reference_material: { icon: BookOpen, label: 'Reference', color: 'bg-gray-100 text-gray-800' },
  custom: { icon: File, label: 'Custom', color: 'bg-gray-100 text-gray-600' },
}

export default function ContentLibrary() {
  const navigate = useNavigate()
  const [content, setContent] = useState<ContentListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState<ContentType | ''>('')
  const [publishedFilter, setPublishedFilter] = useState<'all' | 'published' | 'draft'>('all')
  const [showFilters, setShowFilters] = useState(false)
  const [activeMenu, setActiveMenu] = useState<string | null>(null)
  const [showImportModal, setShowImportModal] = useState(false)
  const [importData, setImportData] = useState<string>('')
  const [importLoading, setImportLoading] = useState(false)
  const [importError, setImportError] = useState<string | null>(null)

  useEffect(() => {
    loadContent()
  }, [typeFilter, publishedFilter])

  async function loadContent() {
    setLoading(true)
    setError(null)
    try {
      const params: Record<string, unknown> = {}
      if (typeFilter) params.content_type = typeFilter
      if (publishedFilter === 'published') params.published_only = true
      const response = await contentApi.list(params as { content_type?: ContentType; published_only?: boolean })
      setContent(response.data)
    } catch (err) {
      setError('Failed to load content')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const filteredContent = content.filter((item) => {
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      return (
        item.title.toLowerCase().includes(query) ||
        item.description?.toLowerCase().includes(query) ||
        item.tags.some((tag) => tag.toLowerCase().includes(query))
      )
    }
    if (publishedFilter === 'draft' && item.is_published) return false
    return true
  })

  async function handleDelete(id: string) {
    if (!confirm('Are you sure you want to delete this content?')) return
    try {
      await contentApi.delete(id)
      setContent(content.filter((c) => c.id !== id))
    } catch (err) {
      console.error('Failed to delete:', err)
    }
    setActiveMenu(null)
  }

  async function handleTogglePublish(item: ContentListItem) {
    try {
      if (item.is_published) {
        await contentApi.unpublish(item.id)
      } else {
        await contentApi.publish(item.id)
      }
      loadContent()
    } catch (err) {
      console.error('Failed to toggle publish:', err)
    }
    setActiveMenu(null)
  }

  async function handleExportHtml(id: string, title: string) {
    try {
      const response = await contentApi.exportContent(id, 'html')
      const blob = response.data as Blob
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      // Use title for filename, sanitized
      const safeTitle = title.replace(/[^a-z0-9]/gi, '_').substring(0, 50)
      a.download = `${safeTitle}.html`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      toast.success('Content exported as HTML')
    } catch (err) {
      console.error('Failed to export:', err)
      toast.error('Failed to export content')
    }
    setActiveMenu(null)
  }

  async function handleExportPdf(id: string, title: string) {
    try {
      // Fetch HTML content from backend (trusted source)
      const response = await contentApi.exportContent(id, 'html')
      const blob = response.data as Blob
      const htmlContent = await blob.text()

      // Create temporary container for PDF generation (never added to DOM)
      const container = document.createElement('div')
      // Safe: HTML is from our own backend API, not user input
      container.innerHTML = htmlContent

      // Extract just the body content if it's a full HTML document
      const bodyMatch = htmlContent.match(/<body[^>]*>([\s\S]*)<\/body>/i)
      if (bodyMatch) {
        container.innerHTML = bodyMatch[1]
      }

      // Apply inline styles for PDF rendering
      container.style.fontFamily = 'system-ui, sans-serif'
      container.style.lineHeight = '1.6'
      container.style.padding = '20px'

      const safeTitle = title.replace(/[^a-z0-9]/gi, '_').substring(0, 50)

      // Generate PDF using html2pdf
      await html2pdf()
        .set({
          margin: [10, 10, 10, 10],
          filename: `${safeTitle}.pdf`,
          image: { type: 'jpeg', quality: 0.98 },
          html2canvas: { scale: 2, useCORS: true, logging: false },
          jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' },
        })
        .from(container)
        .save()

      toast.success('Content exported as PDF')
    } catch (err) {
      console.error('Failed to export PDF:', err)
      toast.error('Failed to export content as PDF')
    }
    setActiveMenu(null)
  }

  async function handleImport() {
    if (!importData.trim()) {
      setImportError('Please paste JSON content to import')
      return
    }

    setImportLoading(true)
    setImportError(null)

    try {
      const parsed = JSON.parse(importData) as ContentImport
      // Validate required fields
      if (!parsed.title || !parsed.content_type || !parsed.body_markdown) {
        throw new Error('Missing required fields: title, content_type, body_markdown')
      }
      await contentApi.importContent(parsed)
      toast.success('Content imported successfully')
      setShowImportModal(false)
      setImportData('')
      loadContent()
    } catch (err: any) {
      const message = err.response?.data?.detail || err.message || 'Failed to import content'
      setImportError(message)
    } finally {
      setImportLoading(false)
    }
  }

  function handleImportFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return

    const reader = new FileReader()
    reader.onload = (event) => {
      const text = event.target?.result as string
      setImportData(text)
      setImportError(null)
    }
    reader.onerror = () => {
      setImportError('Failed to read file')
    }
    reader.readAsText(file)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Content Library</h1>
          <p className="text-sm text-gray-500 mt-1">
            Manage training materials, guides, and documentation
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={() => setShowImportModal(true)}
            className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
          >
            <Upload className="h-4 w-4 mr-2" />
            Import
          </button>
          <Link
            to="/content/new"
            className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700"
          >
            <Plus className="h-4 w-4 mr-2" />
            New Content
          </Link>
        </div>
      </div>

      {/* Search and Filters */}
      <div className="bg-white shadow rounded-lg p-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
            <input
              type="text"
              placeholder="Search by title, description, or tags..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500"
            />
          </div>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`inline-flex items-center px-3 py-2 border rounded-md text-sm font-medium ${
              showFilters || typeFilter || publishedFilter !== 'all'
                ? 'border-primary-500 text-primary-700 bg-primary-50'
                : 'border-gray-300 text-gray-700 bg-white'
            }`}
          >
            <Filter className="h-4 w-4 mr-2" />
            Filters
          </button>
        </div>

        {showFilters && (
          <div className="mt-4 pt-4 border-t border-gray-200 grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Content Type</label>
              <select
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value as ContentType | '')}
                className="w-full border border-gray-300 rounded-md py-2 px-3 focus:ring-primary-500 focus:border-primary-500"
              >
                <option value="">All Types</option>
                {Object.entries(CONTENT_TYPE_INFO).map(([value, info]) => (
                  <option key={value} value={value}>
                    {info.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
              <select
                value={publishedFilter}
                onChange={(e) => setPublishedFilter(e.target.value as 'all' | 'published' | 'draft')}
                className="w-full border border-gray-300 rounded-md py-2 px-3 focus:ring-primary-500 focus:border-primary-500"
              >
                <option value="all">All</option>
                <option value="published">Published</option>
                <option value="draft">Draft</option>
              </select>
            </div>
          </div>
        )}
      </div>

      {/* Content Grid */}
      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
        </div>
      ) : error ? (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">{error}</div>
      ) : filteredContent.length === 0 ? (
        <div className="bg-white shadow rounded-lg p-12 text-center">
          <BookOpen className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-lg font-medium text-gray-900">No content found</h3>
          <p className="mt-1 text-sm text-gray-500">
            {searchQuery || typeFilter
              ? 'Try adjusting your filters'
              : 'Get started by creating your first piece of content'}
          </p>
          {!searchQuery && !typeFilter && (
            <Link
              to="/content/new"
              className="mt-4 inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700"
            >
              <Plus className="h-4 w-4 mr-2" />
              Create Content
            </Link>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredContent.map((item) => {
            const typeInfo = CONTENT_TYPE_INFO[item.content_type]
            const TypeIcon = typeInfo.icon
            return (
              <div
                key={item.id}
                className="bg-white shadow rounded-lg hover:shadow-md transition-shadow"
              >
                <div className="p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center space-x-2">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${typeInfo.color}`}>
                        <TypeIcon className="h-3 w-3 mr-1" />
                        {typeInfo.label}
                      </span>
                      {!item.is_published && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-yellow-100 text-yellow-800">
                          Draft
                        </span>
                      )}
                    </div>
                    <div className="relative">
                      <button
                        onClick={() => setActiveMenu(activeMenu === item.id ? null : item.id)}
                        className="p-1 rounded-full hover:bg-gray-100"
                      >
                        <MoreVertical className="h-5 w-5 text-gray-400" />
                      </button>
                      {activeMenu === item.id && (
                        <div className="absolute right-0 mt-2 w-48 bg-white rounded-md shadow-lg ring-1 ring-black ring-opacity-5 z-50">
                          <div className="py-1">
                            <button
                              onClick={() => { navigate(`/content/${item.id}`); setActiveMenu(null); }}
                              className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                            >
                              <Edit className="h-4 w-4 mr-3" />
                              Edit
                            </button>
                            <button
                              onClick={() => handleTogglePublish(item)}
                              className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                            >
                              {item.is_published ? (
                                <>
                                  <EyeOff className="h-4 w-4 mr-3" />
                                  Unpublish
                                </>
                              ) : (
                                <>
                                  <Eye className="h-4 w-4 mr-3" />
                                  Publish
                                </>
                              )}
                            </button>
                            <div className="border-t border-gray-100">
                              <button
                                onClick={() => handleExportHtml(item.id, item.title)}
                                className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                              >
                                <Download className="h-4 w-4 mr-3" />
                                Export as HTML
                              </button>
                              <button
                                onClick={() => handleExportPdf(item.id, item.title)}
                                className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                              >
                                <FileDown className="h-4 w-4 mr-3" />
                                Export as PDF
                              </button>
                            </div>
                            <div className="border-t border-gray-100">
                              <button
                                onClick={() => handleDelete(item.id)}
                                className="flex items-center w-full px-4 py-2 text-sm text-red-700 hover:bg-red-50"
                              >
                                <Trash2 className="h-4 w-4 mr-3" />
                                Delete
                              </button>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                  <Link to={`/content/${item.id}`} className="block mt-3">
                    <h3 className="text-lg font-medium text-gray-900 hover:text-primary-600">
                      {item.title}
                    </h3>
                  </Link>
                  {item.description && (
                    <p className="mt-1 text-sm text-gray-500 line-clamp-2">{item.description}</p>
                  )}
                  {item.tags.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1">
                      {item.tags.slice(0, 3).map((tag) => (
                        <span
                          key={tag}
                          className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-600"
                        >
                          {tag}
                        </span>
                      ))}
                      {item.tags.length > 3 && (
                        <span className="text-xs text-gray-500">+{item.tags.length - 3}</span>
                      )}
                    </div>
                  )}
                </div>
                <div className="px-4 py-3 bg-gray-50 text-xs text-gray-500 flex items-center justify-between">
                  <span>v{item.version}</span>
                  <span>Updated {formatDistanceToNow(new Date(item.updated_at), { addSuffix: true })}</span>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Import Modal */}
      {showImportModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-hidden">
            <div className="flex items-center justify-between p-4 border-b">
              <h2 className="text-lg font-medium">Import Content</h2>
              <button
                onClick={() => {
                  setShowImportModal(false)
                  setImportData('')
                  setImportError(null)
                }}
                className="p-1 hover:bg-gray-100 rounded"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="p-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Upload JSON file or paste content
                </label>
                <input
                  type="file"
                  accept=".json"
                  onChange={handleImportFile}
                  className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  JSON Content
                </label>
                <textarea
                  value={importData}
                  onChange={(e) => {
                    setImportData(e.target.value)
                    setImportError(null)
                  }}
                  placeholder='{"title": "My Content", "content_type": "student_guide", "body_markdown": "# Content here..."}'
                  rows={12}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md font-mono text-sm focus:ring-primary-500 focus:border-primary-500"
                />
              </div>

              {importError && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-700">
                  {importError}
                </div>
              )}

              <div className="bg-gray-50 -mx-4 -mb-4 px-4 py-3 border-t">
                <div className="flex items-center justify-between">
                  <div className="flex items-center text-sm text-gray-500">
                    <FileCode className="h-4 w-4 mr-1" />
                    Required: title, content_type, body_markdown
                  </div>
                  <div className="flex space-x-3">
                    <button
                      onClick={() => {
                        setShowImportModal(false)
                        setImportData('')
                        setImportError(null)
                      }}
                      className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleImport}
                      disabled={importLoading || !importData.trim()}
                      className="px-4 py-2 bg-primary-600 text-white rounded-md text-sm font-medium hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {importLoading ? 'Importing...' : 'Import'}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
