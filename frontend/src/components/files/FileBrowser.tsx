// frontend/src/components/files/FileBrowser.tsx
import { useState, useEffect } from 'react';
import {
  Folder,
  File,
  FileCode,
  FileText,
  FileJson,
  ChevronLeft,
  Plus,
  Trash2,
  Edit3,
  Loader2,
  Lock,
  RefreshCw,
} from 'lucide-react';
import clsx from 'clsx';
import { filesApi, FileInfo } from '../../services/api';
import { toast } from '../../stores/toastStore';
import { ConfirmDialog } from '../common/ConfirmDialog';
import { FileEditorModal } from './FileEditorModal';
import { CreateFileModal } from './CreateFileModal';

interface FileBrowserProps {
  basePath: string;
  title?: string;
  onFileSelect?: (path: string) => void;
}

// Get icon for file type
function getFileIcon(file: FileInfo) {
  if (file.is_dir) return Folder;

  const name = file.name.toLowerCase();
  const ext = '.' + name.split('.').pop();

  if (name === 'dockerfile' || name.startsWith('dockerfile.')) {
    return FileCode;
  }

  const iconMap: Record<string, typeof File> = {
    '.yaml': FileCode,
    '.yml': FileCode,
    '.json': FileJson,
    '.md': FileText,
    '.markdown': FileText,
    '.sh': FileCode,
    '.bash': FileCode,
    '.py': FileCode,
    '.js': FileCode,
    '.ts': FileCode,
    '.txt': FileText,
  };

  return iconMap[ext] || File;
}

// Format file size
function formatSize(bytes?: number): string {
  if (!bytes) return '-';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// Format date
function formatDate(dateStr?: string): string {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  const now = new Date();
  const diff = now.getTime() - date.getTime();

  if (diff < 60000) return 'Just now';
  if (diff < 3600000) return `${Math.floor(diff / 60000)} min ago`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} hours ago`;
  if (diff < 604800000) return `${Math.floor(diff / 86400000)} days ago`;

  return date.toLocaleDateString();
}

export function FileBrowser({ basePath, title, onFileSelect }: FileBrowserProps) {
  const [currentPath, setCurrentPath] = useState(basePath);
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [parentPath, setParentPath] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal states
  const [editorFile, setEditorFile] = useState<string | null>(null);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<{ open: boolean; file: FileInfo | null }>({
    open: false,
    file: null,
  });

  const loadFiles = async (path: string) => {
    setLoading(true);
    setError(null);
    try {
      const response = await filesApi.listFiles(path);
      setFiles(response.data.files);
      setParentPath(response.data.parent || null);
      setCurrentPath(path);
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'Failed to load files';
      setError(detail);
      toast.error(detail);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadFiles(basePath);
  }, [basePath]);

  const handleNavigate = (path: string) => {
    loadFiles(path);
  };

  const handleFileClick = (file: FileInfo) => {
    if (file.is_dir) {
      handleNavigate(file.path);
    } else if (file.is_text) {
      setEditorFile(file.path);
      onFileSelect?.(file.path);
    } else {
      toast.info('Binary files cannot be edited. Use download instead.');
    }
  };

  const handleDelete = async (file: FileInfo) => {
    try {
      await filesApi.deleteFile(file.path);
      toast.success(`Deleted ${file.name}`);
      loadFiles(currentPath);
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'Failed to delete';
      toast.error(detail);
    }
    setDeleteConfirm({ open: false, file: null });
  };

  const handleCreateFile = () => {
    setCreateModalOpen(true);
  };

  const handleFileCreated = () => {
    setCreateModalOpen(false);
    loadFiles(currentPath);
  };

  const breadcrumbs = currentPath.split('/').filter(Boolean);

  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 bg-gray-50 border-b flex items-center justify-between">
        <div className="flex items-center gap-2">
          {title && <h3 className="font-medium text-gray-900">{title}</h3>}

          {/* Breadcrumbs */}
          <div className="flex items-center text-sm text-gray-500">
            {breadcrumbs.map((segment, i) => (
              <span key={i} className="flex items-center">
                {i > 0 && <span className="mx-1">/</span>}
                <button
                  onClick={() => handleNavigate(breadcrumbs.slice(0, i + 1).join('/'))}
                  className="hover:text-primary-600 hover:underline"
                >
                  {segment}
                </button>
              </span>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => loadFiles(currentPath)}
            className="p-1.5 text-gray-400 hover:text-gray-600 rounded"
            title="Refresh"
          >
            <RefreshCw className={clsx('h-4 w-4', loading && 'animate-spin')} />
          </button>
          <button
            onClick={handleCreateFile}
            className="inline-flex items-center px-3 py-1.5 text-sm font-medium text-white bg-primary-600 rounded hover:bg-primary-700"
          >
            <Plus className="h-4 w-4 mr-1" />
            New File
          </button>
        </div>
      </div>

      {/* File List */}
      <div className="divide-y divide-gray-100">
        {/* Parent directory */}
        {parentPath && currentPath !== basePath && (
          <button
            onClick={() => handleNavigate(parentPath)}
            className="w-full flex items-center px-4 py-2 hover:bg-gray-50 text-left"
          >
            <ChevronLeft className="h-4 w-4 text-gray-400 mr-2" />
            <span className="text-sm text-gray-600">..</span>
          </button>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
          </div>
        ) : error ? (
          <div className="text-center py-12">
            <p className="text-red-500">{error}</p>
          </div>
        ) : files.length === 0 ? (
          <div className="text-center py-12">
            <Folder className="h-12 w-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500">No files in this directory</p>
            <button
              onClick={handleCreateFile}
              className="mt-2 text-sm text-primary-600 hover:text-primary-700"
            >
              Create a new file
            </button>
          </div>
        ) : (
          files.map((file) => {
            const Icon = getFileIcon(file);
            return (
              <div
                key={file.path}
                className="flex items-center px-4 py-2 hover:bg-gray-50 group"
              >
                <button
                  onClick={() => handleFileClick(file)}
                  className="flex items-center flex-1 min-w-0 text-left"
                >
                  <Icon
                    className={clsx(
                      'h-5 w-5 mr-3 flex-shrink-0',
                      file.is_dir ? 'text-yellow-500' : 'text-gray-400'
                    )}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-900 truncate">
                        {file.name}
                      </span>
                      {file.locked_by && (
                        <span title={`Locked by ${file.locked_by}`}><Lock className="h-3 w-3 text-yellow-500" /></span>
                      )}
                    </div>
                  </div>
                </button>

                <div className="flex items-center gap-4 text-xs text-gray-500">
                  <span className="w-20 text-right hidden sm:block">
                    {formatSize(file.size)}
                  </span>
                  <span className="w-24 text-right hidden md:block">
                    {formatDate(file.modified)}
                  </span>

                  {/* Actions */}
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    {file.is_text && !file.is_dir && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setEditorFile(file.path);
                        }}
                        className="p-1 text-gray-400 hover:text-primary-600 rounded"
                        title="Edit"
                      >
                        <Edit3 className="h-4 w-4" />
                      </button>
                    )}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setDeleteConfirm({ open: true, file });
                      }}
                      className="p-1 text-gray-400 hover:text-red-600 rounded"
                      title="Delete"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Modals */}
      <FileEditorModal
        isOpen={!!editorFile}
        filePath={editorFile || ''}
        onClose={() => setEditorFile(null)}
        onSaved={() => loadFiles(currentPath)}
      />

      <CreateFileModal
        isOpen={createModalOpen}
        basePath={currentPath}
        onClose={() => setCreateModalOpen(false)}
        onCreated={handleFileCreated}
      />

      <ConfirmDialog
        isOpen={deleteConfirm.open}
        onCancel={() => setDeleteConfirm({ open: false, file: null })}
        onConfirm={() => deleteConfirm.file && handleDelete(deleteConfirm.file)}
        title={`Delete ${deleteConfirm.file?.is_dir ? 'Directory' : 'File'}`}
        message={`Are you sure you want to delete "${deleteConfirm.file?.name}"?${
          deleteConfirm.file?.is_dir ? ' This will delete all contents.' : ''
        }`}
        confirmLabel="Delete"
        variant="danger"
      />
    </div>
  );
}
