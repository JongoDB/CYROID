// frontend/src/components/blueprints/DeployInstanceModal.tsx
import { useState } from 'react';
import { Blueprint, InstanceDeploy } from '../../services/api';
import { X, Rocket, Loader2 } from 'lucide-react';

interface Props {
  blueprint: Blueprint;
  onClose: () => void;
  onDeploy: (data: InstanceDeploy) => Promise<void>;
}

export default function DeployInstanceModal({ blueprint, onClose, onDeploy }: Props) {
  const [name, setName] = useState('');
  const [autoDeploy, setAutoDeploy] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await onDeploy({ name, auto_deploy: autoDeploy });
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
            <div>
              <h3 className="text-lg font-medium text-gray-900">Deploy Instance</h3>
              <p className="text-sm text-gray-500">
                {blueprint.name} v{blueprint.version}
              </p>
            </div>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-500">
              <X className="h-5 w-5" />
            </button>
          </div>

          <form onSubmit={handleSubmit} className="p-4 space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Instance Name
              </label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                placeholder="e.g., Texas Morning Class"
              />
            </div>

            <div className="flex items-center">
              <input
                type="checkbox"
                id="autoDeploy"
                checked={autoDeploy}
                onChange={(e) => setAutoDeploy(e.target.checked)}
                className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
              />
              <label htmlFor="autoDeploy" className="ml-2 block text-sm text-gray-700">
                Auto-deploy after creation
              </label>
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
                disabled={submitting || !name}
                className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50"
              >
                {submitting ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Rocket className="h-4 w-4 mr-2" />
                )}
                Deploy Instance
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
