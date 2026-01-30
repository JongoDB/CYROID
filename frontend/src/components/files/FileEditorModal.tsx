// frontend/src/components/files/FileEditorModal.tsx
import { useState, useEffect, useRef, useCallback } from 'react';
import Editor from '@monaco-editor/react';
import { Save, AlertTriangle, Loader2, Lock } from 'lucide-react';
import clsx from 'clsx';
import { Modal, ModalFooter } from '../common/Modal';
import { filesApi } from '../../services/api';
import { toast } from '../../stores/toastStore';

interface FileEditorModalProps {
  isOpen: boolean;
  filePath: string;
  onClose: () => void;
  onSaved?: () => void;
  readOnly?: boolean;
}

// Map file extensions to Monaco languages
function getLanguageFromPath(path: string): string {
  const name = path.split('/').pop()?.toLowerCase() || '';
  const ext = '.' + name.split('.').pop();

  if (name === 'dockerfile' || name.startsWith('dockerfile.')) {
    return 'dockerfile';
  }

  const langMap: Record<string, string> = {
    '.yaml': 'yaml',
    '.yml': 'yaml',
    '.json': 'json',
    '.md': 'markdown',
    '.markdown': 'markdown',
    '.sh': 'shell',
    '.bash': 'shell',
    '.py': 'python',
    '.js': 'javascript',
    '.ts': 'typescript',
    '.html': 'html',
    '.css': 'css',
    '.xml': 'xml',
    '.sql': 'sql',
    '.toml': 'toml',
    '.ini': 'ini',
    '.conf': 'ini',
    '.cfg': 'ini',
    '.env': 'shell',
    '.txt': 'plaintext',
  };

  return langMap[ext] || 'plaintext';
}

export function FileEditorModal({
  isOpen,
  filePath,
  onClose,
  onSaved,
  readOnly = false,
}: FileEditorModalProps) {
  const [content, setContent] = useState('');
  const [originalContent, setOriginalContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lockToken, setLockToken] = useState<string | null>(null);
  const [lockedBy, setLockedBy] = useState<string | null>(null);
  const [hasChanges, setHasChanges] = useState(false);
  const [validationWarnings, setValidationWarnings] = useState<string[]>([]);
  const heartbeatRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const language = getLanguageFromPath(filePath);
  const fileName = filePath.split('/').pop() || filePath;

  // Load file content
  useEffect(() => {
    if (!isOpen || !filePath) return;

    const loadFile = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await filesApi.readFile(filePath);
        setContent(response.data.content);
        setOriginalContent(response.data.content);
        setLockToken(response.data.lock_token || null);
        setLockedBy(response.data.locked_by || null);
        setHasChanges(false);
      } catch (err: any) {
        const detail = err.response?.data?.detail || 'Failed to load file';
        setError(detail);
        toast.error(detail);
      } finally {
        setLoading(false);
      }
    };

    loadFile();
  }, [isOpen, filePath]);

  // Heartbeat to keep lock alive
  useEffect(() => {
    if (!lockToken || !filePath || readOnly) return;

    heartbeatRef.current = setInterval(async () => {
      try {
        await filesApi.heartbeatLock(filePath, lockToken);
      } catch (err) {
        console.warn('Failed to refresh lock:', err);
      }
    }, 60000); // Every 60 seconds

    return () => {
      if (heartbeatRef.current) {
        clearInterval(heartbeatRef.current);
      }
    };
  }, [lockToken, filePath, readOnly]);

  // Release lock on close
  const handleClose = useCallback(async () => {
    if (hasChanges) {
      const confirm = window.confirm('You have unsaved changes. Discard them?');
      if (!confirm) return;
    }

    // Release lock
    if (lockToken && filePath) {
      try {
        await filesApi.releaseLock(filePath);
      } catch (err) {
        console.warn('Failed to release lock:', err);
      }
    }

    if (heartbeatRef.current) {
      clearInterval(heartbeatRef.current);
    }

    onClose();
  }, [hasChanges, lockToken, filePath, onClose]);

  // Validate content based on file type
  const validateContent = useCallback((text: string): string[] => {
    const warnings: string[] = [];
    const ext = '.' + fileName.split('.').pop()?.toLowerCase();

    if (ext === '.yaml' || ext === '.yml') {
      try {
        // Basic YAML validation - check for common issues
        const lines = text.split('\n');
        lines.forEach((line, i) => {
          // Check for tabs (YAML doesn't like tabs)
          if (line.includes('\t')) {
            warnings.push(`Line ${i + 1}: Tab character found - YAML prefers spaces`);
          }
        });
      } catch (e: any) {
        warnings.push(`YAML error: ${e.message}`);
      }
    }

    if (ext === '.json') {
      try {
        JSON.parse(text);
      } catch (e: any) {
        warnings.push(`JSON error: ${e.message}`);
      }
    }

    if (ext === '.sh' || ext === '.bash') {
      if (!text.startsWith('#!')) {
        warnings.push('Warning: No shebang line (e.g., #!/bin/bash)');
      }
    }

    return warnings;
  }, [fileName]);

  // Handle content change
  const handleEditorChange = useCallback((value: string | undefined) => {
    const newContent = value || '';
    setContent(newContent);
    setHasChanges(newContent !== originalContent);
    setValidationWarnings(validateContent(newContent));
  }, [originalContent, validateContent]);

  // Save file
  const handleSave = useCallback(async (closeAfter = false) => {
    if (readOnly || lockedBy) {
      toast.error('Cannot save: file is read-only or locked by another user');
      return;
    }

    setSaving(true);
    try {
      await filesApi.updateFile(filePath, content, lockToken || undefined);
      setOriginalContent(content);
      setHasChanges(false);
      toast.success('File saved');
      onSaved?.();

      if (closeAfter) {
        // Release lock and close
        if (lockToken) {
          try {
            await filesApi.releaseLock(filePath);
          } catch (err) {
            console.warn('Failed to release lock:', err);
          }
        }
        onClose();
      }
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'Failed to save file';
      toast.error(detail);
    } finally {
      setSaving(false);
    }
  }, [filePath, content, lockToken, readOnly, lockedBy, onSaved, onClose]);

  // Keyboard shortcut for save (Ctrl/Cmd + S)
  // Note: Escape is handled by the Modal component
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) return;

      // Ctrl/Cmd + S to save
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        if (!readOnly && !lockedBy) {
          handleSave(false);
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, handleSave, readOnly, lockedBy]);

  const isReadOnly = readOnly || !!lockedBy;

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={fileName}
      description={`Edit file: ${filePath}`}
      size="full"
      closeOnBackdrop={!hasChanges}
      className="!max-w-none mx-4 md:mx-8 lg:mx-12 h-[calc(100vh-2rem)] md:h-[calc(100vh-4rem)] lg:h-[calc(100vh-6rem)] flex flex-col"
    >
      {/* Status bar */}
      <div className="flex items-center gap-3 px-4 py-2 bg-gray-100 border-b text-sm">
        {hasChanges && (
          <span className="px-2 py-0.5 text-xs font-medium bg-yellow-100 text-yellow-700 rounded">
            Unsaved
          </span>
        )}
        {isReadOnly && (
          <span className="px-2 py-0.5 text-xs font-medium bg-gray-200 text-gray-600 rounded flex items-center gap-1">
            <Lock className="h-3 w-3" />
            {lockedBy ? `Locked by ${lockedBy}` : 'Read-only'}
          </span>
        )}
        <span className="text-xs text-gray-500 hidden sm:block ml-auto">
          {language} | Ctrl+S to save | Esc to close
        </span>
      </div>

      {/* Editor */}
      <div className="flex-1 relative min-h-0">
        {loading ? (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-50">
            <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
          </div>
        ) : error ? (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-50">
            <div className="text-center">
              <AlertTriangle className="h-12 w-12 text-red-500 mx-auto mb-3" />
              <p className="text-gray-900 font-medium">{error}</p>
            </div>
          </div>
        ) : (
          <Editor
            height="100%"
            language={language}
            value={content}
            onChange={handleEditorChange}
            theme="vs-dark"
            options={{
              readOnly: isReadOnly,
              minimap: { enabled: true },
              fontSize: 14,
              lineNumbers: 'on',
              wordWrap: 'on',
              scrollBeyondLastLine: false,
              automaticLayout: true,
              tabSize: 2,
              insertSpaces: true,
            }}
          />
        )}
      </div>

      {/* Validation Warnings */}
      {validationWarnings.length > 0 && (
        <div className="px-4 py-2 bg-yellow-50 border-t border-yellow-100">
          <div className="flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 text-yellow-600 mt-0.5 flex-shrink-0" />
            <div className="text-sm text-yellow-800">
              {validationWarnings.length === 1 ? (
                validationWarnings[0]
              ) : (
                <ul className="list-disc list-inside">
                  {validationWarnings.slice(0, 3).map((w, i) => (
                    <li key={i}>{w}</li>
                  ))}
                  {validationWarnings.length > 3 && (
                    <li>...and {validationWarnings.length - 3} more</li>
                  )}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <ModalFooter className="justify-between">
        <div className="text-xs text-gray-500">
          {filePath}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleClose}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
          >
            Cancel
          </button>
          {!isReadOnly && (
            <>
              <button
                onClick={() => handleSave(false)}
                disabled={saving || !hasChanges}
                className={clsx(
                  'inline-flex items-center px-4 py-2 text-sm font-medium rounded-md',
                  saving || !hasChanges
                    ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                    : 'bg-primary-600 text-white hover:bg-primary-700'
                )}
              >
                {saving ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Save className="h-4 w-4 mr-2" />
                )}
                Save
              </button>
              <button
                onClick={() => handleSave(true)}
                disabled={saving || !hasChanges}
                className={clsx(
                  'inline-flex items-center px-4 py-2 text-sm font-medium rounded-md',
                  saving || !hasChanges
                    ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                    : 'bg-green-600 text-white hover:bg-green-700'
                )}
              >
                Save & Close
              </button>
            </>
          )}
        </div>
      </ModalFooter>
    </Modal>
  );
}
