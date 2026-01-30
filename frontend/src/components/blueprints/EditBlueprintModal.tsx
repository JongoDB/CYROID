// frontend/src/components/blueprints/EditBlueprintModal.tsx
import { useState, useCallback } from 'react';
import Editor from '@monaco-editor/react';
import { Save, AlertTriangle, Loader2 } from 'lucide-react';
import clsx from 'clsx';
import { Modal, ModalFooter } from '../common/Modal';
import { blueprintsApi, BlueprintDetail } from '../../services/api';
import { toast } from '../../stores/toastStore';

interface EditBlueprintModalProps {
  blueprint: BlueprintDetail;
  isOpen: boolean;
  onClose: () => void;
  onSaved?: () => void;
}

export function EditBlueprintModal({
  blueprint,
  isOpen,
  onClose,
  onSaved,
}: EditBlueprintModalProps) {
  const [configJson, setConfigJson] = useState(() =>
    JSON.stringify(blueprint.config, null, 2)
  );
  const [saving, setSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  // Validate JSON on change
  const handleEditorChange = useCallback(
    (value: string | undefined) => {
      const newContent = value || '';
      setConfigJson(newContent);

      // Check if content changed
      try {
        const parsed = JSON.parse(newContent);
        const original = JSON.stringify(blueprint.config, null, 2);
        setHasChanges(newContent !== original);
        setValidationError(null);

        // Basic validation of required fields
        if (!parsed.networks || !Array.isArray(parsed.networks)) {
          setValidationError('Config must have a "networks" array');
        } else if (!parsed.vms || !Array.isArray(parsed.vms)) {
          setValidationError('Config must have a "vms" array');
        }
      } catch (e: any) {
        setValidationError(`Invalid JSON: ${e.message}`);
        setHasChanges(true); // Allow user to see there's a problem
      }
    },
    [blueprint.config]
  );

  const handleClose = useCallback(() => {
    if (hasChanges) {
      const confirm = window.confirm('You have unsaved changes. Discard them?');
      if (!confirm) return;
    }
    onClose();
  }, [hasChanges, onClose]);

  const handleSave = useCallback(async () => {
    if (validationError) {
      toast.error('Please fix validation errors before saving');
      return;
    }

    setSaving(true);
    try {
      const config = JSON.parse(configJson);
      await blueprintsApi.update(blueprint.id, { config });
      toast.success(`Blueprint updated to version ${blueprint.version + 1}`);
      onSaved?.();
      onClose();
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'Failed to save blueprint';
      toast.error(detail);
    } finally {
      setSaving(false);
    }
  }, [configJson, validationError, blueprint.id, blueprint.version, onSaved, onClose]);

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={`Edit: ${blueprint.name}`}
      description={`Editing blueprint configuration (v${blueprint.version})`}
      size="full"
      closeOnBackdrop={!hasChanges}
      className="!max-w-4xl mx-4 h-[calc(100vh-4rem)] flex flex-col"
    >
      {/* Status bar */}
      <div className="flex items-center gap-3 px-4 py-2 bg-gray-100 border-b text-sm">
        {hasChanges && (
          <span className="px-2 py-0.5 text-xs font-medium bg-yellow-100 text-yellow-700 rounded">
            Unsaved
          </span>
        )}
        {validationError && (
          <span className="px-2 py-0.5 text-xs font-medium bg-red-100 text-red-700 rounded flex items-center gap-1">
            <AlertTriangle className="h-3 w-3" />
            Invalid
          </span>
        )}
        <span className="text-xs text-gray-500 ml-auto">
          JSON | Ctrl+S to save | Esc to close
        </span>
      </div>

      {/* Editor */}
      <div className="flex-1 relative min-h-0">
        <Editor
          height="100%"
          language="json"
          value={configJson}
          onChange={handleEditorChange}
          theme="vs-dark"
          options={{
            minimap: { enabled: false },
            fontSize: 14,
            lineNumbers: 'on',
            wordWrap: 'on',
            scrollBeyondLastLine: false,
            automaticLayout: true,
            tabSize: 2,
            insertSpaces: true,
            formatOnPaste: true,
          }}
        />
      </div>

      {/* Validation Warning */}
      {validationError && (
        <div className="px-4 py-2 bg-red-50 border-t border-red-100">
          <div className="flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 text-red-600 mt-0.5 flex-shrink-0" />
            <div className="text-sm text-red-800">{validationError}</div>
          </div>
        </div>
      )}

      {/* Footer */}
      <ModalFooter className="justify-between">
        <div className="text-xs text-gray-500">
          Saving will increment version to {blueprint.version + 1}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleClose}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !hasChanges || !!validationError}
            className={clsx(
              'inline-flex items-center px-4 py-2 text-sm font-medium rounded-md',
              saving || !hasChanges || validationError
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
        </div>
      </ModalFooter>
    </Modal>
  );
}
