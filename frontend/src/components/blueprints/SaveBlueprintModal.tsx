// frontend/src/components/blueprints/SaveBlueprintModal.tsx
import { useState } from 'react';
import { blueprintsApi, BlueprintCreate } from '../../services/api';
import { X, LayoutTemplate, Loader2 } from 'lucide-react';
import { toast } from '../../stores/toastStore';

interface Props {
  rangeId: string;
  rangeName: string;
  suggestedPrefix: string;
  onClose: () => void;
  onSuccess: () => void;
}

export default function SaveBlueprintModal({
  rangeId,
  rangeName,
  suggestedPrefix,
  onClose,
  onSuccess,
}: Props) {
  const [name, setName] = useState(rangeName);
  const [description, setDescription] = useState('');
  const [baseSubnetPrefix, setBaseSubnetPrefix] = useState(suggestedPrefix);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);

    try {
      const data: BlueprintCreate = {
        range_id: rangeId,
        name,
        description: description || undefined,
        base_subnet_prefix: baseSubnetPrefix,
      };
      await blueprintsApi.create(data);
      toast.success('Blueprint created successfully');
      onSuccess();
      onClose();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to create blueprint');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4">
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75" onClick={onClose} />

        <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full">
          <div className="flex items-center justify-between p-4 border-b">
            <h3 className="text-lg font-medium text-gray-900">Save as Blueprint</h3>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-500">
              <X className="h-5 w-5" />
            </button>
          </div>

          <form onSubmit={handleSubmit} className="p-4 space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Blueprint Name
              </label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                placeholder="e.g., Red Team Training Lab"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">
                Description
              </label>
              <textarea
                rows={2}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                placeholder="Optional description..."
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">
                Base Subnet Prefix
              </label>
              <input
                type="text"
                required
                pattern="\d{1,3}\.\d{1,3}"
                value={baseSubnetPrefix}
                onChange={(e) => setBaseSubnetPrefix(e.target.value)}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                placeholder="e.g., 10.100"
              />
              <p className="mt-1 text-xs text-gray-500">
                Each instance will get an incremented second octet (10.100 → 10.101 → 10.102)
              </p>
            </div>

            <div className="flex justify-end space-x-3 pt-4">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting || !name || !baseSubnetPrefix}
                className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50"
              >
                {submitting ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <LayoutTemplate className="h-4 w-4 mr-2" />
                )}
                Save Blueprint
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
