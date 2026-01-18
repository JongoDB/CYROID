// frontend/src/components/wizard-v2/panels/NetworkPropertiesPanel.tsx
import { X, Trash2 } from 'lucide-react';
import { useWizardStore } from '../../../stores/wizardStore';

interface Props {
  selectedNetworkId: string | null;
  selectedVmId: string | null;
  onClose: () => void;
}

export function NetworkPropertiesPanel({ selectedNetworkId, selectedVmId, onClose }: Props) {
  const { networks, updateNetwork, removeNetwork, updateVM, removeVM } = useWizardStore();

  const selectedNetwork = networks.segments.find(n => n.id === selectedNetworkId);
  const selectedVm = networks.vms.find(v => v.id === selectedVmId);

  if (!selectedNetwork && !selectedVm) {
    return null;
  }

  if (selectedNetwork) {
    return (
      <div className="absolute bottom-0 left-0 right-0 bg-white border-t border-gray-200 p-4 shadow-lg">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-gray-900">Network Properties</h3>
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                removeNetwork(selectedNetwork.id);
                onClose();
              }}
              className="text-red-500 hover:text-red-600"
            >
              <Trash2 className="w-4 h-4" />
            </button>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-500">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="grid grid-cols-4 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Name</label>
            <input
              type="text"
              value={selectedNetwork.name}
              onChange={(e) => updateNetwork(selectedNetwork.id, { name: e.target.value })}
              className="w-full px-2 py-1 text-sm border border-gray-300 rounded"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Subnet</label>
            <input
              type="text"
              value={selectedNetwork.subnet}
              onChange={(e) => updateNetwork(selectedNetwork.id, { subnet: e.target.value })}
              className="w-full px-2 py-1 text-sm border border-gray-300 rounded"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Gateway</label>
            <input
              type="text"
              value={selectedNetwork.gateway}
              onChange={(e) => updateNetwork(selectedNetwork.id, { gateway: e.target.value })}
              className="w-full px-2 py-1 text-sm border border-gray-300 rounded"
            />
          </div>
          <div className="flex items-end gap-4">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={selectedNetwork.dhcp}
                onChange={(e) => updateNetwork(selectedNetwork.id, { dhcp: e.target.checked })}
                className="rounded border-gray-300"
              />
              DHCP
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={selectedNetwork.isolated}
                onChange={(e) => updateNetwork(selectedNetwork.id, { isolated: e.target.checked })}
                className="rounded border-gray-300"
              />
              Isolated
            </label>
          </div>
        </div>
      </div>
    );
  }

  if (selectedVm) {
    return (
      <div className="absolute bottom-0 left-0 right-0 bg-white border-t border-gray-200 p-4 shadow-lg">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-gray-900">VM Properties</h3>
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                removeVM(selectedVm.id);
                onClose();
              }}
              className="text-red-500 hover:text-red-600"
            >
              <Trash2 className="w-4 h-4" />
            </button>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-500">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="grid grid-cols-5 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Hostname</label>
            <input
              type="text"
              value={selectedVm.hostname}
              onChange={(e) => updateVM(selectedVm.id, { hostname: e.target.value })}
              className="w-full px-2 py-1 text-sm border border-gray-300 rounded"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">IP Address</label>
            <input
              type="text"
              value={selectedVm.ip}
              onChange={(e) => updateVM(selectedVm.id, { ip: e.target.value })}
              className="w-full px-2 py-1 text-sm border border-gray-300 rounded"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">CPU</label>
            <input
              type="number"
              min={1}
              max={16}
              value={selectedVm.cpu}
              onChange={(e) => updateVM(selectedVm.id, { cpu: parseInt(e.target.value) || 1 })}
              className="w-full px-2 py-1 text-sm border border-gray-300 rounded"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">RAM (MB)</label>
            <input
              type="number"
              min={512}
              step={512}
              value={selectedVm.ramMb}
              onChange={(e) => updateVM(selectedVm.id, { ramMb: parseInt(e.target.value) || 1024 })}
              className="w-full px-2 py-1 text-sm border border-gray-300 rounded"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Disk (GB)</label>
            <input
              type="number"
              min={10}
              value={selectedVm.diskGb}
              onChange={(e) => updateVM(selectedVm.id, { diskGb: parseInt(e.target.value) || 20 })}
              className="w-full px-2 py-1 text-sm border border-gray-300 rounded"
            />
          </div>
        </div>
      </div>
    );
  }

  return null;
}
