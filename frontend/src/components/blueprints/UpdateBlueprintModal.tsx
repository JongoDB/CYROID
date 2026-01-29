// frontend/src/components/blueprints/UpdateBlueprintModal.tsx
import { useState } from 'react';
import { blueprintsApi } from '../../services/api';
import { X, RefreshCw, Loader2 } from 'lucide-react';
import { toast } from '../../stores/toastStore';

interface Props {
  blueprintId: string;
  blueprintName: string;
  currentVersion: number;
  rangeId: string;
  onClose: () => void;
  onSuccess: () => void;
}

export default function UpdateBlueprintModal({
  blueprintId,
  blueprintName,
  currentVersion,
  rangeId,
  onClose,
  onSuccess,
}: Props) {
  const [submitting, setSubmitting] = useState(false);

  const handleUpdate = async () => {
    setSubmitting(true);
    try {
      await blueprintsApi.updateFromRange(blueprintId, rangeId);
      toast.success(`Blueprint updated to version ${currentVersion + 1}`);
      onSuccess();
      onClose();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to update blueprint');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4">
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75" onClick={onClose} />
        <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium text-gray-900">Update Blueprint</h3>
            <button onClick={onClose} disabled={submitting} className="text-gray-400 hover:text-gray-500 disabled:opacity-50" aria-label="Close">
              <X className="h-5 w-5" />
            </button>
          </div>

          <p className="text-sm text-gray-600 mb-4">
            Update <span className="font-medium">{blueprintName}</span> to version {currentVersion + 1}?
          </p>

          <p className="text-xs text-gray-500 mb-6">
            Existing instances will remain on their original versions until redeployed.
          </p>

          <div className="flex justify-end space-x-3">
            <button
              onClick={onClose}
              disabled={submitting}
              className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              onClick={handleUpdate}
              disabled={submitting}
              className="inline-flex items-center px-4 py-2 border border-transparent rounded-md text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50"
            >
              {submitting ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4 mr-2" />
              )}
              Update Blueprint
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
