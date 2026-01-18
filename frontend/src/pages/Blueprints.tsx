// frontend/src/pages/Blueprints.tsx
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { blueprintsApi, Blueprint, InstanceDeploy } from '../services/api';
import {
  LayoutTemplate,
  Loader2,
  Rocket,
  Trash2,
  Network,
  Server,
  Users,
  Upload,
} from 'lucide-react';
import { ConfirmDialog } from '../components/common/ConfirmDialog';
import { toast } from '../stores/toastStore';
import DeployInstanceModal from '../components/blueprints/DeployInstanceModal';
import { ImportBlueprintModal } from '../components/blueprints';

export default function Blueprints() {
  const [blueprints, setBlueprints] = useState<Blueprint[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleteConfirm, setDeleteConfirm] = useState<{
    blueprint: Blueprint | null;
    isLoading: boolean;
  }>({ blueprint: null, isLoading: false });
  const [deployModal, setDeployModal] = useState<Blueprint | null>(null);
  const [showImportModal, setShowImportModal] = useState(false);

  const fetchBlueprints = async () => {
    try {
      const response = await blueprintsApi.list();
      setBlueprints(response.data);
    } catch (err) {
      console.error('Failed to fetch blueprints:', err);
      toast.error('Failed to load blueprints');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBlueprints();
  }, []);

  const handleDelete = (blueprint: Blueprint) => {
    setDeleteConfirm({ blueprint, isLoading: false });
  };

  const confirmDelete = async () => {
    if (!deleteConfirm.blueprint) return;
    setDeleteConfirm((prev) => ({ ...prev, isLoading: true }));
    try {
      await blueprintsApi.delete(deleteConfirm.blueprint.id);
      setDeleteConfirm({ blueprint: null, isLoading: false });
      fetchBlueprints();
      toast.success('Blueprint deleted');
    } catch (err: any) {
      setDeleteConfirm({ blueprint: null, isLoading: false });
      toast.error(err.response?.data?.detail || 'Failed to delete blueprint');
    }
  };

  const handleDeploy = async (data: InstanceDeploy) => {
    if (!deployModal) return;
    try {
      const response = await blueprintsApi.deploy(deployModal.id, data);
      toast.success(`Instance "${response.data.name}" created`);
      setDeployModal(null);
      fetchBlueprints();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to deploy instance');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    );
  }

  return (
    <div>
      <div className="sm:flex sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Range Blueprints</h1>
          <p className="mt-2 text-sm text-gray-700">
            Reusable range configurations for deploying multiple isolated instances
          </p>
        </div>
        <div className="mt-4 sm:mt-0">
          <button
            onClick={() => setShowImportModal(true)}
            className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
          >
            <Upload className="h-4 w-4 mr-2" />
            Import Blueprint
          </button>
        </div>
      </div>

      {blueprints.length === 0 ? (
        <div className="mt-8 text-center">
          <LayoutTemplate className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900">No blueprints</h3>
          <p className="mt-1 text-sm text-gray-500">
            Create a range first, then save it as a blueprint from the range detail page.
          </p>
        </div>
      ) : (
        <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {blueprints.map((blueprint) => (
            <div
              key={blueprint.id}
              className="bg-white rounded-lg shadow overflow-hidden hover:shadow-md transition-shadow"
            >
              <div className="p-5">
                <div className="flex items-start justify-between">
                  <div className="flex items-center">
                    <div className="flex-shrink-0 bg-indigo-100 rounded-md p-2">
                      <LayoutTemplate className="h-6 w-6 text-indigo-600" />
                    </div>
                    <div className="ml-3">
                      <Link
                        to={`/blueprints/${blueprint.id}`}
                        className="text-sm font-medium text-gray-900 hover:text-indigo-600"
                      >
                        {blueprint.name}
                      </Link>
                      <p className="text-xs text-gray-500">v{blueprint.version}</p>
                    </div>
                  </div>
                </div>

                {blueprint.description && (
                  <p className="mt-3 text-sm text-gray-500 line-clamp-2">
                    {blueprint.description}
                  </p>
                )}

                <div className="mt-4 flex items-center text-xs text-gray-500 space-x-4">
                  <span className="flex items-center">
                    <Network className="h-3.5 w-3.5 mr-1" />
                    {blueprint.network_count} networks
                  </span>
                  <span className="flex items-center">
                    <Server className="h-3.5 w-3.5 mr-1" />
                    {blueprint.vm_count} VMs
                  </span>
                  <span className="flex items-center">
                    <Users className="h-3.5 w-3.5 mr-1" />
                    {blueprint.instance_count} instances
                  </span>
                </div>
              </div>

              <div className="bg-gray-50 px-5 py-3 flex justify-between items-center">
                <span className="text-xs text-gray-500">
                  Subnet: {blueprint.base_subnet_prefix}.x.x
                </span>
                <div className="flex space-x-2">
                  <button
                    onClick={() => setDeployModal(blueprint)}
                    className="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700"
                  >
                    <Rocket className="h-3.5 w-3.5 mr-1" />
                    Deploy
                  </button>
                  <button
                    onClick={() => handleDelete(blueprint)}
                    className="p-1.5 text-gray-400 hover:text-red-600"
                    title="Delete"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Delete Confirmation */}
      <ConfirmDialog
        isOpen={deleteConfirm.blueprint !== null}
        title="Delete Blueprint"
        message={`Are you sure you want to delete "${deleteConfirm.blueprint?.name}"? This cannot be undone.`}
        confirmLabel="Delete"
        variant="danger"
        onConfirm={confirmDelete}
        onCancel={() => setDeleteConfirm({ blueprint: null, isLoading: false })}
        isLoading={deleteConfirm.isLoading}
      />

      {/* Deploy Instance Modal */}
      {deployModal && (
        <DeployInstanceModal
          blueprint={deployModal}
          onClose={() => setDeployModal(null)}
          onDeploy={handleDeploy}
        />
      )}

      {/* Import Blueprint Modal */}
      {showImportModal && (
        <ImportBlueprintModal
          onClose={() => setShowImportModal(false)}
          onSuccess={() => {
            fetchBlueprints();
            toast.success('Blueprint imported successfully');
          }}
        />
      )}
    </div>
  );
}
