// frontend/src/pages/ContentEditor.tsx
import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import Image from '@tiptap/extension-image'
import Link from '@tiptap/extension-link'
import { Table } from '@tiptap/extension-table'
import { TableRow } from '@tiptap/extension-table-row'
import { TableCell } from '@tiptap/extension-table-cell'
import { TableHeader } from '@tiptap/extension-table-header'
import CodeBlockLowlight from '@tiptap/extension-code-block-lowlight'
import { common, createLowlight } from 'lowlight'
import DOMPurify from 'dompurify'
import {
  Save,
  ArrowLeft,
  Eye,
  EyeOff,
  Bold,
  Italic,
  Strikethrough,
  Code,
  List,
  ListOrdered,
  Quote,
  Minus,
  Heading1,
  Heading2,
  Heading3,
  Link as LinkIcon,
  Image as ImageIcon,
  Table as TableIcon,
  Undo,
  Redo,
  Upload,
  X,
  Copy,
  Tag,
} from 'lucide-react'
import { contentApi, Content, ContentCreate, ContentUpdate, ContentType, ContentAsset } from '../services/api'

const lowlight = createLowlight(common)

const CONTENT_TYPES: { value: ContentType; label: string }[] = [
  { value: 'student_guide', label: 'Student Guide' },
  { value: 'msel', label: 'MSEL' },
  { value: 'curriculum', label: 'Curriculum' },
  { value: 'instructor_notes', label: 'Instructor Notes' },
  { value: 'reference_material', label: 'Reference Material' },
  { value: 'custom', label: 'Custom' },
]

// Sanitize HTML to prevent XSS - allows safe HTML tags from TipTap
function sanitizeHtml(html: string): string {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: [
      'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'br', 'hr',
      'strong', 'b', 'em', 'i', 'u', 's', 'strike', 'code', 'pre',
      'ul', 'ol', 'li', 'blockquote',
      'a', 'img',
      'table', 'thead', 'tbody', 'tr', 'th', 'td',
      'div', 'span',
    ],
    ALLOWED_ATTR: ['href', 'src', 'alt', 'title', 'class', 'target', 'rel', 'colspan', 'rowspan'],
  })
}

interface EditorToolbarProps {
  editor: ReturnType<typeof useEditor>
}

function EditorToolbar({ editor }: EditorToolbarProps) {
  if (!editor) return null

  const setLink = useCallback(() => {
    const previousUrl = editor.getAttributes('link').href
    const url = window.prompt('URL', previousUrl)
    if (url === null) return
    if (url === '') {
      editor.chain().focus().extendMarkRange('link').unsetLink().run()
      return
    }
    editor.chain().focus().extendMarkRange('link').setLink({ href: url }).run()
  }, [editor])

  const addImage = useCallback(() => {
    const url = window.prompt('Image URL')
    if (url) {
      editor.chain().focus().setImage({ src: url }).run()
    }
  }, [editor])

  const addTable = useCallback(() => {
    editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()
  }, [editor])

  const buttonClass = (isActive: boolean) =>
    `p-2 rounded hover:bg-gray-100 ${isActive ? 'bg-gray-200 text-primary-600' : 'text-gray-600'}`

  return (
    <div className="flex flex-wrap items-center gap-1 p-2 border-b border-gray-200 bg-gray-50">
      {/* Undo/Redo */}
      <button onClick={() => editor.chain().focus().undo().run()} className={buttonClass(false)} title="Undo">
        <Undo className="h-4 w-4" />
      </button>
      <button onClick={() => editor.chain().focus().redo().run()} className={buttonClass(false)} title="Redo">
        <Redo className="h-4 w-4" />
      </button>
      <div className="w-px h-6 bg-gray-300 mx-1" />

      {/* Headings */}
      <button
        onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
        className={buttonClass(editor.isActive('heading', { level: 1 }))}
        title="Heading 1"
      >
        <Heading1 className="h-4 w-4" />
      </button>
      <button
        onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
        className={buttonClass(editor.isActive('heading', { level: 2 }))}
        title="Heading 2"
      >
        <Heading2 className="h-4 w-4" />
      </button>
      <button
        onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
        className={buttonClass(editor.isActive('heading', { level: 3 }))}
        title="Heading 3"
      >
        <Heading3 className="h-4 w-4" />
      </button>
      <div className="w-px h-6 bg-gray-300 mx-1" />

      {/* Text formatting */}
      <button
        onClick={() => editor.chain().focus().toggleBold().run()}
        className={buttonClass(editor.isActive('bold'))}
        title="Bold"
      >
        <Bold className="h-4 w-4" />
      </button>
      <button
        onClick={() => editor.chain().focus().toggleItalic().run()}
        className={buttonClass(editor.isActive('italic'))}
        title="Italic"
      >
        <Italic className="h-4 w-4" />
      </button>
      <button
        onClick={() => editor.chain().focus().toggleStrike().run()}
        className={buttonClass(editor.isActive('strike'))}
        title="Strikethrough"
      >
        <Strikethrough className="h-4 w-4" />
      </button>
      <button
        onClick={() => editor.chain().focus().toggleCode().run()}
        className={buttonClass(editor.isActive('code'))}
        title="Inline Code"
      >
        <Code className="h-4 w-4" />
      </button>
      <div className="w-px h-6 bg-gray-300 mx-1" />

      {/* Lists */}
      <button
        onClick={() => editor.chain().focus().toggleBulletList().run()}
        className={buttonClass(editor.isActive('bulletList'))}
        title="Bullet List"
      >
        <List className="h-4 w-4" />
      </button>
      <button
        onClick={() => editor.chain().focus().toggleOrderedList().run()}
        className={buttonClass(editor.isActive('orderedList'))}
        title="Ordered List"
      >
        <ListOrdered className="h-4 w-4" />
      </button>
      <div className="w-px h-6 bg-gray-300 mx-1" />

      {/* Blocks */}
      <button
        onClick={() => editor.chain().focus().toggleBlockquote().run()}
        className={buttonClass(editor.isActive('blockquote'))}
        title="Blockquote"
      >
        <Quote className="h-4 w-4" />
      </button>
      <button
        onClick={() => editor.chain().focus().toggleCodeBlock().run()}
        className={buttonClass(editor.isActive('codeBlock'))}
        title="Code Block"
      >
        <Code className="h-4 w-4" />
      </button>
      <button
        onClick={() => editor.chain().focus().setHorizontalRule().run()}
        className={buttonClass(false)}
        title="Horizontal Rule"
      >
        <Minus className="h-4 w-4" />
      </button>
      <div className="w-px h-6 bg-gray-300 mx-1" />

      {/* Media & Tables */}
      <button onClick={setLink} className={buttonClass(editor.isActive('link'))} title="Link">
        <LinkIcon className="h-4 w-4" />
      </button>
      <button onClick={addImage} className={buttonClass(false)} title="Image">
        <ImageIcon className="h-4 w-4" />
      </button>
      <button onClick={addTable} className={buttonClass(false)} title="Table">
        <TableIcon className="h-4 w-4" />
      </button>
    </div>
  )
}

export default function ContentEditor() {
  const { id } = useParams()
  const navigate = useNavigate()
  const isNew = id === 'new'

  const [loading, setLoading] = useState(!isNew)
  const [saving, setSaving] = useState(false)
  const [content, setContent] = useState<Content | null>(null)

  // Form state
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [contentType, setContentType] = useState<ContentType>('custom')
  const [tags, setTags] = useState<string[]>([])
  const [tagInput, setTagInput] = useState('')
  const [organization, setOrganization] = useState('')
  const [isPublished, setIsPublished] = useState(false)

  // Assets
  const [assets, setAssets] = useState<ContentAsset[]>([])
  const [uploading, setUploading] = useState(false)

  // Preview mode
  const [showPreview, setShowPreview] = useState(false)

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        codeBlock: false,
      }),
      Placeholder.configure({
        placeholder: 'Start writing your content...',
      }),
      Image,
      Link.configure({
        openOnClick: false,
      }),
      Table.configure({
        resizable: true,
      }),
      TableRow,
      TableCell,
      TableHeader,
      CodeBlockLowlight.configure({
        lowlight,
      }),
    ],
    content: '',
    editorProps: {
      attributes: {
        class: 'prose prose-sm sm:prose max-w-none focus:outline-none min-h-[400px] p-4',
      },
    },
  })

  useEffect(() => {
    if (!isNew && id) {
      loadContent(id)
    }
  }, [id, isNew])

  async function loadContent(contentId: string) {
    setLoading(true)
    try {
      const response = await contentApi.get(contentId)
      const data = response.data
      setContent(data)
      setTitle(data.title)
      setDescription(data.description || '')
      setContentType(data.content_type)
      setTags(data.tags)
      setOrganization(data.organization || '')
      setIsPublished(data.is_published)
      setAssets(data.assets)

      // Set editor content from markdown (convert to HTML for TipTap)
      if (editor && data.body_html) {
        editor.commands.setContent(sanitizeHtml(data.body_html))
      } else if (editor && data.body_markdown) {
        // If no HTML, try to use markdown (basic conversion)
        editor.commands.setContent(`<p>${data.body_markdown.replace(/\n/g, '</p><p>')}</p>`)
      }
    } catch (err) {
      console.error('Failed to load content:', err)
      navigate('/content')
    } finally {
      setLoading(false)
    }
  }

  // Convert TipTap HTML to simple markdown (basic conversion)
  function htmlToMarkdown(html: string): string {
    // This is a simplified conversion - in production you'd want a proper library
    let md = html
      .replace(/<h1[^>]*>(.*?)<\/h1>/gi, '# $1\n\n')
      .replace(/<h2[^>]*>(.*?)<\/h2>/gi, '## $1\n\n')
      .replace(/<h3[^>]*>(.*?)<\/h3>/gi, '### $1\n\n')
      .replace(/<strong[^>]*>(.*?)<\/strong>/gi, '**$1**')
      .replace(/<b[^>]*>(.*?)<\/b>/gi, '**$1**')
      .replace(/<em[^>]*>(.*?)<\/em>/gi, '*$1*')
      .replace(/<i[^>]*>(.*?)<\/i>/gi, '*$1*')
      .replace(/<code[^>]*>(.*?)<\/code>/gi, '`$1`')
      .replace(/<a[^>]*href="([^"]*)"[^>]*>(.*?)<\/a>/gi, '[$2]($1)')
      .replace(/<img[^>]*src="([^"]*)"[^>]*>/gi, '![]($1)')
      .replace(/<li[^>]*>(.*?)<\/li>/gi, '- $1\n')
      .replace(/<blockquote[^>]*>(.*?)<\/blockquote>/gi, '> $1\n\n')
      .replace(/<hr\s*\/?>/gi, '\n---\n')
      .replace(/<br\s*\/?>/gi, '\n')
      .replace(/<p[^>]*>(.*?)<\/p>/gi, '$1\n\n')
      .replace(/<[^>]+>/g, '')
      .replace(/&nbsp;/g, ' ')
      .replace(/&lt;/g, '<')
      .replace(/&gt;/g, '>')
      .replace(/&amp;/g, '&')
      .replace(/\n{3,}/g, '\n\n')
      .trim()
    return md
  }

  async function handleSave() {
    if (!title.trim()) {
      alert('Title is required')
      return
    }

    setSaving(true)
    try {
      const html = editor?.getHTML() || ''
      const markdown = htmlToMarkdown(html)

      if (isNew) {
        const data: ContentCreate = {
          title,
          description: description || undefined,
          content_type: contentType,
          body_markdown: markdown,
          tags,
          organization: organization || undefined,
        }
        const response = await contentApi.create(data)
        navigate(`/content/${response.data.id}`)
      } else if (id) {
        const data: ContentUpdate = {
          title,
          description: description || undefined,
          content_type: contentType,
          body_markdown: markdown,
          tags,
          organization: organization || undefined,
          is_published: isPublished,
        }
        await contentApi.update(id, data)
        await loadContent(id)
      }
    } catch (err) {
      console.error('Failed to save:', err)
      alert('Failed to save content')
    } finally {
      setSaving(false)
    }
  }

  function handleAddTag() {
    const tag = tagInput.trim()
    if (tag && !tags.includes(tag)) {
      setTags([...tags, tag])
      setTagInput('')
    }
  }

  function handleRemoveTag(tagToRemove: string) {
    setTags(tags.filter((t) => t !== tagToRemove))
  }

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file || !id || isNew) return

    setUploading(true)
    try {
      const response = await contentApi.uploadAsset(id, file)
      setAssets([...assets, response.data])
    } catch (err) {
      console.error('Failed to upload:', err)
      alert('Failed to upload file')
    } finally {
      setUploading(false)
    }
  }

  async function handleDeleteAsset(assetId: string) {
    if (!id || !confirm('Delete this asset?')) return
    try {
      await contentApi.deleteAsset(id, assetId)
      setAssets(assets.filter((a) => a.id !== assetId))
    } catch (err) {
      console.error('Failed to delete asset:', err)
    }
  }

  async function handleTogglePublish() {
    if (!id || isNew) return
    try {
      if (isPublished) {
        await contentApi.unpublish(id)
        setIsPublished(false)
      } else {
        await contentApi.publish(id)
        setIsPublished(true)
      }
    } catch (err) {
      console.error('Failed to toggle publish:', err)
    }
  }

  // Get sanitized HTML for preview
  const previewHtml = sanitizeHtml(editor?.getHTML() || '')

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <button
            onClick={() => navigate('/content')}
            className="p-2 rounded-md hover:bg-gray-100"
          >
            <ArrowLeft className="h-5 w-5 text-gray-600" />
          </button>
          <h1 className="text-2xl font-semibold text-gray-900">
            {isNew ? 'Create Content' : 'Edit Content'}
          </h1>
        </div>
        <div className="flex items-center space-x-3">
          {!isNew && (
            <button
              onClick={handleTogglePublish}
              className={`inline-flex items-center px-3 py-2 border rounded-md text-sm font-medium ${
                isPublished
                  ? 'border-yellow-300 bg-yellow-50 text-yellow-700 hover:bg-yellow-100'
                  : 'border-green-300 bg-green-50 text-green-700 hover:bg-green-100'
              }`}
            >
              {isPublished ? (
                <>
                  <EyeOff className="h-4 w-4 mr-2" />
                  Unpublish
                </>
              ) : (
                <>
                  <Eye className="h-4 w-4 mr-2" />
                  Publish
                </>
              )}
            </button>
          )}
          <button
            onClick={() => setShowPreview(!showPreview)}
            className={`inline-flex items-center px-3 py-2 border rounded-md text-sm font-medium ${
              showPreview
                ? 'border-primary-500 bg-primary-50 text-primary-700'
                : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50'
            }`}
          >
            <Eye className="h-4 w-4 mr-2" />
            Preview
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700 disabled:opacity-50"
          >
            <Save className="h-4 w-4 mr-2" />
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Editor */}
        <div className="lg:col-span-2 space-y-4">
          {/* Title */}
          <div className="bg-white shadow rounded-lg p-4">
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Content Title"
              className="w-full text-2xl font-semibold border-none focus:ring-0 p-0 placeholder-gray-400"
            />
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Short description (optional)"
              className="w-full mt-2 text-sm text-gray-500 border-none focus:ring-0 p-0 placeholder-gray-400"
            />
          </div>

          {/* Editor */}
          <div className="bg-white shadow rounded-lg overflow-hidden">
            {showPreview ? (
              <div className="p-6">
                <div
                  className="prose prose-sm sm:prose max-w-none"
                  dangerouslySetInnerHTML={{ __html: previewHtml }}
                />
              </div>
            ) : (
              <>
                <EditorToolbar editor={editor} />
                <EditorContent editor={editor} />
              </>
            )}
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          {/* Metadata */}
          <div className="bg-white shadow rounded-lg p-4">
            <h3 className="text-sm font-medium text-gray-900 mb-4">Settings</h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Content Type
                </label>
                <select
                  value={contentType}
                  onChange={(e) => setContentType(e.target.value as ContentType)}
                  className="w-full border border-gray-300 rounded-md py-2 px-3 text-sm"
                >
                  {CONTENT_TYPES.map((type) => (
                    <option key={type.value} value={type.value}>
                      {type.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Organization
                </label>
                <input
                  type="text"
                  value={organization}
                  onChange={(e) => setOrganization(e.target.value)}
                  placeholder="e.g., USMC, CYBERCOM"
                  className="w-full border border-gray-300 rounded-md py-2 px-3 text-sm"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Tags
                </label>
                <div className="flex gap-2 mb-2 flex-wrap">
                  {tags.map((tag) => (
                    <span
                      key={tag}
                      className="inline-flex items-center px-2 py-1 rounded text-xs bg-gray-100 text-gray-700"
                    >
                      {tag}
                      <button
                        onClick={() => handleRemoveTag(tag)}
                        className="ml-1 hover:text-red-500"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </span>
                  ))}
                </div>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={tagInput}
                    onChange={(e) => setTagInput(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), handleAddTag())}
                    placeholder="Add tag..."
                    className="flex-1 border border-gray-300 rounded-md py-1 px-2 text-sm"
                  />
                  <button
                    onClick={handleAddTag}
                    className="px-3 py-1 border border-gray-300 rounded-md text-sm hover:bg-gray-50"
                  >
                    <Tag className="h-4 w-4" />
                  </button>
                </div>
              </div>

              {content && (
                <div className="pt-4 border-t border-gray-200 text-xs text-gray-500">
                  <div>Version: {content.version}</div>
                  <div>Created: {new Date(content.created_at).toLocaleDateString()}</div>
                  <div>Updated: {new Date(content.updated_at).toLocaleDateString()}</div>
                </div>
              )}
            </div>
          </div>

          {/* Assets */}
          {!isNew && (
            <div className="bg-white shadow rounded-lg p-4">
              <h3 className="text-sm font-medium text-gray-900 mb-4">Assets</h3>

              <label className="block w-full mb-4">
                <span className="sr-only">Upload file</span>
                <div className="flex items-center justify-center w-full h-20 border-2 border-dashed border-gray-300 rounded-lg hover:border-primary-400 cursor-pointer transition-colors">
                  <div className="text-center">
                    <Upload className="mx-auto h-6 w-6 text-gray-400" />
                    <span className="mt-1 block text-xs text-gray-500">
                      {uploading ? 'Uploading...' : 'Upload image'}
                    </span>
                  </div>
                </div>
                <input
                  type="file"
                  accept="image/*"
                  onChange={handleFileUpload}
                  disabled={uploading}
                  className="hidden"
                />
              </label>

              {assets.length > 0 && (
                <div className="space-y-2">
                  {assets.map((asset) => (
                    <div
                      key={asset.id}
                      className="flex items-center justify-between p-2 bg-gray-50 rounded text-xs"
                    >
                      <div className="flex items-center truncate">
                        <ImageIcon className="h-4 w-4 text-gray-400 mr-2 flex-shrink-0" />
                        <span className="truncate">{asset.filename}</span>
                      </div>
                      <div className="flex items-center space-x-1 ml-2">
                        <button
                          onClick={() => {
                            navigator.clipboard.writeText(asset.file_path)
                          }}
                          className="p-1 hover:bg-gray-200 rounded"
                          title="Copy path"
                        >
                          <Copy className="h-3 w-3" />
                        </button>
                        <button
                          onClick={() => handleDeleteAsset(asset.id)}
                          className="p-1 hover:bg-red-100 text-red-500 rounded"
                          title="Delete"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
