// frontend/src/components/blueprints/UpdateBlueprintModal.tsx
import { useState } from 'react';
import { blueprintsApi } from '../../services/api';
import { RefreshCw, Loader2 } from 'lucide-react';
import { toast } from '../../stores/toastStore';
import { Modal, ModalBody, ModalFooter } from '../common/Modal';

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
    <Modal
      isOpen={true}
      onClose={onClose}
      title="Update Blueprint"
      description={`Update ${blueprintName} to a new version`}
      size="sm"
      closeOnBackdrop={!submitting}
      closeOnEscape={!submitting}
    >
      <ModalBody>
        <p className="text-sm text-gray-600 mb-4">
          Update <span className="font-medium">{blueprintName}</span> to version {currentVersion + 1}?
        </p>
        <p className="text-xs text-gray-500">
          Existing instances will remain on their original versions until redeployed.
        </p>
      </ModalBody>

      <ModalFooter>
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
      </ModalFooter>
    </Modal>
  );
}
