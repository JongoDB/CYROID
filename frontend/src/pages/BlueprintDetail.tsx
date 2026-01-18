// frontend/src/pages/BlueprintDetail.tsx
import { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import {
  blueprintsApi,
  instancesApi,
  BlueprintDetail as BlueprintDetailType,
  Instance,
  InstanceDeploy,
} from '../services/api';
import {
  LayoutTemplate,
  Loader2,
  ArrowLeft,
  Rocket,
  Network,
  Server,
  Play,
  Square,
  RefreshCw,
  Copy,
  Trash2,
  ExternalLink,
} from 'lucide-react';
import clsx from 'clsx';
import { toast } from '../stores/toastStore';
import { ConfirmDialog } from '../components/common/ConfirmDialog';
import { DeployInstanceModal } from '../components/blueprints';

const statusColors: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-800',
  deploying: 'bg-yellow-100 text-yellow-800',
  running: 'bg-green-100 text-green-800',
  stopped: 'bg-gray-100 text-gray-800',
  error: 'bg-red-100 text-red-800',
};

export default function BlueprintDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [blueprint, setBlueprint] = useState<BlueprintDetailType | null>(null);
  const [instances, setInstances] = useState<Instance[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'overview' | 'instances'>('overview');
  const [showDeployModal, setShowDeployModal] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<{
    instance: Instance | null;
    isLoading: boolean;
  }>({ instance: null, isLoading: false });

  const fetchData = async () => {
    if (!id) return;
    try {
      const [bpRes, instRes] = await Promise.all([
        blueprintsApi.get(id),
        blueprintsApi.listInstances(id),
      ]);
      setBlueprint(bpRes.data);
      setInstances(instRes.data);
    } catch (err) {
      console.error('Failed to fetch blueprint:', err);
      toast.error('Failed to load blueprint');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [id]);

  const handleDeploy = async (data: InstanceDeploy) => {
    if (!id) return;
    try {
      await blueprintsApi.deploy(id, data);
      toast.success('Instance deployed');
      setShowDeployModal(false);
      fetchData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to deploy');
    }
  };

  const handleClone = async (instance: Instance) => {
    try {
      await instancesApi.clone(instance.id);
      toast.success('Instance cloned');
      fetchData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to clone');
    }
  };

  const handleDelete = async () => {
    if (!deleteConfirm.instance) return;
    setDeleteConfirm((prev) => ({ ...prev, isLoading: true }));
    try {
      await instancesApi.delete(deleteConfirm.instance.id);
      toast.success('Instance deleted');
      setDeleteConfirm({ instance: null, isLoading: false });
      fetchData();
    } catch (err: any) {
      setDeleteConfirm({ instance: null, isLoading: false });
      toast.error(err.response?.data?.detail || 'Failed to delete');
    }
  };

  if (loading || !blueprint) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <Link
          to="/blueprints"
          className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700 mb-4"
        >
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back to Blueprints
        </Link>
        <div className="flex items-center justify-between">
          <div className="flex items-center">
            <div className="bg-indigo-100 rounded-md p-3">
              <LayoutTemplate className="h-8 w-8 text-indigo-600" />
            </div>
            <div className="ml-4">
              <h1 className="text-2xl font-bold text-gray-900">{blueprint.name}</h1>
              <p className="text-sm text-gray-500">
                Version {blueprint.version} · Created by {blueprint.created_by_username}
              </p>
            </div>
          </div>
          <button
            onClick={() => setShowDeployModal(true)}
            className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700"
          >
            <Rocket className="h-4 w-4 mr-2" />
            Deploy Instance
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('overview')}
            className={clsx(
              'py-4 px-1 border-b-2 font-medium text-sm',
              activeTab === 'overview'
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            )}
          >
            Overview
          </button>
          <button
            onClick={() => setActiveTab('instances')}
            className={clsx(
              'py-4 px-1 border-b-2 font-medium text-sm',
              activeTab === 'instances'
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            )}
          >
            Instances ({instances.length})
          </button>
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' ? (
        <div className="bg-white shadow rounded-lg p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Configuration</h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Networks */}
            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-2 flex items-center">
                <Network className="h-4 w-4 mr-2" />
                Networks ({blueprint.config.networks.length})
              </h4>
              <ul className="space-y-2">
                {blueprint.config.networks.map((net, i) => (
                  <li key={i} className="bg-gray-50 rounded p-2 text-sm">
                    <span className="font-medium">{net.name}</span>
                    <span className="text-gray-500 ml-2">{net.subnet}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* VMs */}
            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-2 flex items-center">
                <Server className="h-4 w-4 mr-2" />
                VMs ({blueprint.config.vms.length})
              </h4>
              <ul className="space-y-2">
                {blueprint.config.vms.map((vm, i) => (
                  <li key={i} className="bg-gray-50 rounded p-2 text-sm">
                    <span className="font-medium">{vm.hostname}</span>
                    <span className="text-gray-500 ml-2">{vm.ip_address}</span>
                    <span className="text-gray-400 ml-2">({vm.template_name})</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-white shadow rounded-lg overflow-hidden">
          {instances.length === 0 ? (
            <div className="p-8 text-center">
              <Rocket className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-2 text-sm font-medium text-gray-900">No instances</h3>
              <p className="mt-1 text-sm text-gray-500">
                Deploy your first instance from this blueprint.
              </p>
              <button
                onClick={() => setShowDeployModal(true)}
                className="mt-4 inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700"
              >
                <Rocket className="h-4 w-4 mr-2" />
                Deploy Instance
              </button>
            </div>
          ) : (
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Instance
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Subnet
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Instructor
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {instances.map((instance) => (
                  <tr key={instance.id}>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">
                        {instance.name}
                      </div>
                      <div className="text-xs text-gray-500">
                        v{instance.blueprint_version}
                        {instance.blueprint_version < blueprint.version && (
                          <span className="ml-1 text-amber-500">(outdated)</span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {blueprint.base_subnet_prefix.split('.')[0]}.
                      {parseInt(blueprint.base_subnet_prefix.split('.')[1]) +
                        instance.subnet_offset}
                      .x.x
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={clsx(
                          'px-2 py-1 text-xs font-medium rounded-full',
                          statusColors[instance.range_status || 'draft']
                        )}
                      >
                        {instance.range_status || 'unknown'}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {instance.instructor_username}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium space-x-2">
                      <Link
                        to={`/ranges/${instance.range_id}`}
                        className="text-indigo-600 hover:text-indigo-900"
                        title="Open Range"
                      >
                        <ExternalLink className="h-4 w-4 inline" />
                      </Link>
                      <button
                        onClick={() => handleClone(instance)}
                        className="text-gray-400 hover:text-gray-600"
                        title="Clone"
                      >
                        <Copy className="h-4 w-4 inline" />
                      </button>
                      <button
                        onClick={() =>
                          setDeleteConfirm({ instance, isLoading: false })
                        }
                        className="text-gray-400 hover:text-red-600"
                        title="Delete"
                      >
                        <Trash2 className="h-4 w-4 inline" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Deploy Modal */}
      {showDeployModal && (
        <DeployInstanceModal
          blueprint={blueprint}
          onClose={() => setShowDeployModal(false)}
          onDeploy={handleDeploy}
        />
      )}

      {/* Delete Confirmation */}
      <ConfirmDialog
        isOpen={deleteConfirm.instance !== null}
        title="Delete Instance"
        message={`Are you sure you want to delete "${deleteConfirm.instance?.name}"? This will delete the range and all its VMs. This cannot be undone.`}
        confirmLabel="Delete"
        variant="danger"
        onConfirm={handleDelete}
        onCancel={() => setDeleteConfirm({ instance: null, isLoading: false })}
        isLoading={deleteConfirm.isLoading}
      />
    </div>
  );
}
