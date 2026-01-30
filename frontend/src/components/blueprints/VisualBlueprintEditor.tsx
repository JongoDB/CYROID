// frontend/src/components/blueprints/VisualBlueprintEditor.tsx
import { useState, useCallback } from 'react';
import {
  Save,
  Loader2,
  Plus,
  Trash2,
  Network,
  Server,
  ChevronDown,
  ChevronUp,
  GripVertical,
} from 'lucide-react';
import clsx from 'clsx';
import { Modal, ModalBody, ModalFooter } from '../common/Modal';
import { blueprintsApi, BlueprintDetail, BlueprintConfig } from '../../services/api';
import { toast } from '../../stores/toastStore';

interface VisualBlueprintEditorProps {
  blueprint: BlueprintDetail;
  isOpen: boolean;
  onClose: () => void;
  onSaved?: () => void;
}

interface NetworkConfig {
  name: string;
  subnet: string;
  gateway: string;
  is_isolated: boolean;
}

interface NetworkInterfaceConfig {
  network_name: string;
  ip_address?: string;
  is_primary: boolean;
}

interface VMConfig {
  hostname: string;
  network_interfaces: NetworkInterfaceConfig[];
  base_image_id?: string;
  base_image_name?: string;
  base_image_tag?: string;
  golden_image_id?: string;
  snapshot_id?: string;
  template_name?: string;
  cpu: number;
  ram_mb: number;
  disk_gb: number;
  position_x?: number;
  position_y?: number;
  // Legacy fields for backward compatibility
  ip_address?: string;
  network_name?: string;
}

export function VisualBlueprintEditor({
  blueprint,
  isOpen,
  onClose,
  onSaved,
}: VisualBlueprintEditorProps) {
  // Deep clone the config to avoid mutating the original
  const [networks, setNetworks] = useState<NetworkConfig[]>(() =>
    JSON.parse(JSON.stringify(blueprint.config.networks))
  );
  const [vms, setVMs] = useState<VMConfig[]>(() => {
    // Normalize VMs to always use network_interfaces
    return blueprint.config.vms.map((vm) => {
      const normalized: VMConfig = {
        ...vm,
        cpu: vm.cpu || 1,
        ram_mb: vm.ram_mb || 1024,
        disk_gb: vm.disk_gb || 20,
        network_interfaces: vm.network_interfaces || [],
      };
      // Convert legacy single-NIC to network_interfaces if needed
      if (
        normalized.network_interfaces.length === 0 &&
        vm.network_name &&
        vm.ip_address
      ) {
        normalized.network_interfaces = [
          {
            network_name: vm.network_name,
            ip_address: vm.ip_address,
            is_primary: true,
          },
        ];
      }
      return normalized;
    });
  });

  const [saving, setSaving] = useState(false);
  const [expandedVMs, setExpandedVMs] = useState<Set<number>>(new Set([0]));

  const hasChanges = useCallback(() => {
    const originalConfig = JSON.stringify({
      networks: blueprint.config.networks,
      vms: blueprint.config.vms,
    });
    const currentConfig = JSON.stringify({ networks, vms });
    return originalConfig !== currentConfig;
  }, [blueprint.config, networks, vms]);

  const handleClose = useCallback(() => {
    if (hasChanges()) {
      const confirm = window.confirm('You have unsaved changes. Discard them?');
      if (!confirm) return;
    }
    onClose();
  }, [hasChanges, onClose]);

  const handleSave = useCallback(async () => {
    // Validate
    if (networks.length === 0) {
      toast.error('At least one network is required');
      return;
    }
    if (vms.length === 0) {
      toast.error('At least one VM is required');
      return;
    }

    // Check for duplicate network names
    const networkNames = networks.map((n) => n.name);
    if (new Set(networkNames).size !== networkNames.length) {
      toast.error('Network names must be unique');
      return;
    }

    // Check for duplicate hostnames
    const hostnames = vms.map((v) => v.hostname);
    if (new Set(hostnames).size !== hostnames.length) {
      toast.error('VM hostnames must be unique');
      return;
    }

    // Check VMs have at least one network interface and no duplicate networks
    for (const vm of vms) {
      if (vm.network_interfaces.length === 0) {
        toast.error(`VM "${vm.hostname}" must have at least one network interface`);
        return;
      }
      // Check for duplicate network assignments on the same VM
      const vmNetworks = vm.network_interfaces.map((ni) => ni.network_name);
      if (new Set(vmNetworks).size !== vmNetworks.length) {
        toast.error(`VM "${vm.hostname}" has duplicate network connections. Each network can only be connected once per VM.`);
        return;
      }
    }

    setSaving(true);
    try {
      const config: BlueprintConfig = {
        networks,
        vms: vms.map((vm) => {
          // Destructure to exclude legacy fields, keep everything else
          const { ip_address, network_name, ...rest } = vm;
          return rest;
        }),
        router: blueprint.config.router,
        msel: blueprint.config.msel,
      };

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
  }, [networks, vms, blueprint, onSaved, onClose]);

  const toggleVMExpanded = (index: number) => {
    setExpandedVMs((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  // Network handlers
  const addNetwork = () => {
    const newName = `network-${networks.length + 1}`;
    setNetworks([
      ...networks,
      {
        name: newName,
        subnet: '10.0.0.0/24',
        gateway: '10.0.0.1',
        is_isolated: false,
      },
    ]);
  };

  const updateNetwork = (index: number, updates: Partial<NetworkConfig>) => {
    setNetworks((prev) =>
      prev.map((n, i) => (i === index ? { ...n, ...updates } : n))
    );
  };

  const removeNetwork = (index: number) => {
    const networkName = networks[index].name;
    // Check if any VM uses this network
    const vmUsingNetwork = vms.find((vm) =>
      vm.network_interfaces.some((ni) => ni.network_name === networkName)
    );
    if (vmUsingNetwork) {
      toast.error(
        `Cannot delete network "${networkName}" - it's used by VM "${vmUsingNetwork.hostname}"`
      );
      return;
    }
    setNetworks((prev) => prev.filter((_, i) => i !== index));
  };

  // VM handlers
  const addVM = () => {
    const newHostname = `vm-${vms.length + 1}`;
    setVMs([
      ...vms,
      {
        hostname: newHostname,
        network_interfaces:
          networks.length > 0
            ? [{ network_name: networks[0].name, ip_address: '', is_primary: true }]
            : [],
        cpu: 1,
        ram_mb: 1024,
        disk_gb: 20,
        base_image_tag: 'ubuntu:22.04',
      },
    ]);
    setExpandedVMs((prev) => new Set([...prev, vms.length]));
  };

  const updateVM = (index: number, updates: Partial<VMConfig>) => {
    setVMs((prev) => prev.map((v, i) => (i === index ? { ...v, ...updates } : v)));
  };

  const removeVM = (index: number) => {
    setVMs((prev) => prev.filter((_, i) => i !== index));
    setExpandedVMs((prev) => {
      const next = new Set<number>();
      prev.forEach((i) => {
        if (i < index) next.add(i);
        else if (i > index) next.add(i - 1);
      });
      return next;
    });
  };

  // Network interface handlers
  const addInterface = (vmIndex: number) => {
    if (networks.length === 0) {
      toast.error('Create a network first');
      return;
    }

    const vm = vms[vmIndex];
    const usedNetworks = new Set(vm.network_interfaces.map((ni) => ni.network_name));
    const availableNetwork = networks.find((n) => !usedNetworks.has(n.name));

    if (!availableNetwork) {
      toast.error('All networks are already connected to this VM. Add a new network first.');
      return;
    }

    setVMs((prev) =>
      prev.map((v, i) => {
        if (i !== vmIndex) return v;
        return {
          ...v,
          network_interfaces: [
            ...v.network_interfaces,
            {
              network_name: availableNetwork.name,
              ip_address: '',
              is_primary: v.network_interfaces.length === 0,
            },
          ],
        };
      })
    );
  };

  const updateInterface = (
    vmIndex: number,
    ifaceIndex: number,
    updates: Partial<NetworkInterfaceConfig>
  ) => {
    setVMs((prev) =>
      prev.map((vm, i) => {
        if (i !== vmIndex) return vm;
        const newInterfaces = vm.network_interfaces.map((iface, j) => {
          if (j !== ifaceIndex) {
            // If setting this one as primary, unset others
            if (updates.is_primary) {
              return { ...iface, is_primary: false };
            }
            return iface;
          }
          return { ...iface, ...updates };
        });
        return { ...vm, network_interfaces: newInterfaces };
      })
    );
  };

  const removeInterface = (vmIndex: number, ifaceIndex: number) => {
    setVMs((prev) =>
      prev.map((vm, i) => {
        if (i !== vmIndex) return vm;
        const newInterfaces = vm.network_interfaces.filter((_, j) => j !== ifaceIndex);
        // Ensure at least one is primary
        if (newInterfaces.length > 0 && !newInterfaces.some((ni) => ni.is_primary)) {
          newInterfaces[0].is_primary = true;
        }
        return { ...vm, network_interfaces: newInterfaces };
      })
    );
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={`Edit: ${blueprint.name}`}
      description={`Visual editor (v${blueprint.version})`}
      size="full"
      closeOnBackdrop={!hasChanges()}
      className="!max-w-5xl mx-4 h-[calc(100vh-4rem)] flex flex-col"
    >
      <ModalBody className="flex-1 overflow-y-auto space-y-6">
        {/* Networks Section */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-lg font-medium text-gray-900 flex items-center">
              <Network className="h-5 w-5 mr-2 text-indigo-600" />
              Networks ({networks.length})
            </h3>
            <button
              onClick={addNetwork}
              className="inline-flex items-center px-3 py-1.5 text-sm font-medium text-indigo-600 bg-indigo-50 rounded-md hover:bg-indigo-100"
            >
              <Plus className="h-4 w-4 mr-1" />
              Add Network
            </button>
          </div>

          <div className="space-y-2">
            {networks.map((network, index) => (
              <div
                key={index}
                className="bg-gray-50 rounded-lg p-4 border border-gray-200"
              >
                <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">
                      Name
                    </label>
                    <input
                      type="text"
                      value={network.name}
                      onChange={(e) => updateNetwork(index, { name: e.target.value })}
                      className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">
                      Subnet (CIDR)
                    </label>
                    <input
                      type="text"
                      value={network.subnet}
                      onChange={(e) => updateNetwork(index, { subnet: e.target.value })}
                      placeholder="10.0.0.0/24"
                      className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">
                      Gateway
                    </label>
                    <input
                      type="text"
                      value={network.gateway}
                      onChange={(e) => updateNetwork(index, { gateway: e.target.value })}
                      placeholder="10.0.0.1"
                      className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
                    />
                  </div>
                  <div className="flex items-end justify-between">
                    <label className="flex items-center">
                      <input
                        type="checkbox"
                        checked={network.is_isolated}
                        onChange={(e) =>
                          updateNetwork(index, { is_isolated: e.target.checked })
                        }
                        className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                      />
                      <span className="ml-2 text-sm text-gray-600">Isolated</span>
                    </label>
                    <button
                      onClick={() => removeNetwork(index)}
                      className="p-1.5 text-gray-400 hover:text-red-600"
                      title="Remove network"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
            {networks.length === 0 && (
              <p className="text-sm text-gray-500 text-center py-4">
                No networks defined. Click "Add Network" to create one.
              </p>
            )}
          </div>
        </div>

        {/* VMs Section */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-lg font-medium text-gray-900 flex items-center">
              <Server className="h-5 w-5 mr-2 text-green-600" />
              Virtual Machines ({vms.length})
            </h3>
            <button
              onClick={addVM}
              className="inline-flex items-center px-3 py-1.5 text-sm font-medium text-green-600 bg-green-50 rounded-md hover:bg-green-100"
            >
              <Plus className="h-4 w-4 mr-1" />
              Add VM
            </button>
          </div>

          <div className="space-y-3">
            {vms.map((vm, vmIndex) => (
              <div
                key={vmIndex}
                className="bg-white rounded-lg border border-gray-200 overflow-hidden"
              >
                {/* VM Header - always visible */}
                <div
                  className="flex items-center justify-between px-4 py-3 bg-gray-50 cursor-pointer hover:bg-gray-100"
                  onClick={() => toggleVMExpanded(vmIndex)}
                >
                  <div className="flex items-center">
                    <GripVertical className="h-4 w-4 text-gray-400 mr-2" />
                    <Server className="h-4 w-4 text-gray-500 mr-2" />
                    <span className="font-medium text-gray-900">{vm.hostname}</span>
                    <span className="ml-3 text-xs text-gray-500">
                      {vm.base_image_tag || vm.template_name || 'No image'}
                    </span>
                    <span className="ml-3 text-xs text-gray-400">
                      {vm.network_interfaces.length} NIC
                      {vm.network_interfaces.length !== 1 ? 's' : ''}
                    </span>
                  </div>
                  <div className="flex items-center">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        removeVM(vmIndex);
                      }}
                      className="p-1 text-gray-400 hover:text-red-600 mr-2"
                      title="Remove VM"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                    {expandedVMs.has(vmIndex) ? (
                      <ChevronUp className="h-5 w-5 text-gray-400" />
                    ) : (
                      <ChevronDown className="h-5 w-5 text-gray-400" />
                    )}
                  </div>
                </div>

                {/* VM Details - collapsible */}
                {expandedVMs.has(vmIndex) && (
                  <div className="p-4 space-y-4">
                    {/* Basic Info */}
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                      <div>
                        <label className="block text-xs font-medium text-gray-500 mb-1">
                          Hostname
                        </label>
                        <input
                          type="text"
                          value={vm.hostname}
                          onChange={(e) =>
                            updateVM(vmIndex, { hostname: e.target.value })
                          }
                          className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-gray-500 mb-1">
                          Image Tag
                        </label>
                        <input
                          type="text"
                          value={vm.base_image_tag || ''}
                          onChange={(e) =>
                            updateVM(vmIndex, { base_image_tag: e.target.value })
                          }
                          placeholder="ubuntu:22.04"
                          className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
                        />
                      </div>
                      <div className="grid grid-cols-3 gap-2">
                        <div>
                          <label className="block text-xs font-medium text-gray-500 mb-1">
                            CPU
                          </label>
                          <input
                            type="number"
                            min="1"
                            value={vm.cpu}
                            onChange={(e) =>
                              updateVM(vmIndex, { cpu: parseInt(e.target.value) || 1 })
                            }
                            className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-gray-500 mb-1">
                            RAM (MB)
                          </label>
                          <input
                            type="number"
                            min="256"
                            step="256"
                            value={vm.ram_mb}
                            onChange={(e) =>
                              updateVM(vmIndex, {
                                ram_mb: parseInt(e.target.value) || 1024,
                              })
                            }
                            className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-gray-500 mb-1">
                            Disk (GB)
                          </label>
                          <input
                            type="number"
                            min="1"
                            value={vm.disk_gb}
                            onChange={(e) =>
                              updateVM(vmIndex, {
                                disk_gb: parseInt(e.target.value) || 20,
                              })
                            }
                            className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
                          />
                        </div>
                      </div>
                    </div>

                    {/* Network Interfaces */}
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <label className="text-sm font-medium text-gray-700">
                          Network Interfaces
                        </label>
                        <button
                          onClick={() => addInterface(vmIndex)}
                          className="inline-flex items-center px-2 py-1 text-xs font-medium text-indigo-600 bg-indigo-50 rounded hover:bg-indigo-100"
                        >
                          <Plus className="h-3 w-3 mr-1" />
                          Add NIC
                        </button>
                      </div>

                      <div className="space-y-2">
                        {vm.network_interfaces.map((iface, ifaceIndex) => (
                          <div
                            key={ifaceIndex}
                            className="flex items-center gap-3 bg-gray-50 rounded-md p-2"
                          >
                            <div className="flex-1 grid grid-cols-1 md:grid-cols-3 gap-2">
                              <div>
                                <select
                                  value={iface.network_name}
                                  onChange={(e) =>
                                    updateInterface(vmIndex, ifaceIndex, {
                                      network_name: e.target.value,
                                    })
                                  }
                                  className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
                                >
                                  <option value="">Select network...</option>
                                  {networks.map((net) => {
                                    // Check if this network is already used by another interface on this VM
                                    const isUsedByOther = vm.network_interfaces.some(
                                      (ni, idx) => idx !== ifaceIndex && ni.network_name === net.name
                                    );
                                    return (
                                      <option
                                        key={net.name}
                                        value={net.name}
                                        disabled={isUsedByOther}
                                      >
                                        {net.name} ({net.subnet}){isUsedByOther ? ' - already used' : ''}
                                      </option>
                                    );
                                  })}
                                </select>
                              </div>
                              <div>
                                <input
                                  type="text"
                                  value={iface.ip_address}
                                  onChange={(e) =>
                                    updateInterface(vmIndex, ifaceIndex, {
                                      ip_address: e.target.value,
                                    })
                                  }
                                  placeholder="IP (auto if empty)"
                                  className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
                                />
                              </div>
                              <div className="flex items-center justify-between">
                                <label className="flex items-center">
                                  <input
                                    type="radio"
                                    name={`primary-${vmIndex}`}
                                    checked={iface.is_primary}
                                    onChange={() =>
                                      updateInterface(vmIndex, ifaceIndex, {
                                        is_primary: true,
                                      })
                                    }
                                    className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300"
                                  />
                                  <span className="ml-2 text-xs text-gray-600">
                                    Primary
                                  </span>
                                </label>
                                <button
                                  onClick={() => removeInterface(vmIndex, ifaceIndex)}
                                  disabled={vm.network_interfaces.length <= 1}
                                  className="p-1 text-gray-400 hover:text-red-600 disabled:opacity-30 disabled:cursor-not-allowed"
                                  title="Remove interface"
                                >
                                  <Trash2 className="h-4 w-4" />
                                </button>
                              </div>
                            </div>
                          </div>
                        ))}
                        {vm.network_interfaces.length === 0 && (
                          <p className="text-xs text-red-500 py-2">
                            At least one network interface is required
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
            {vms.length === 0 && (
              <p className="text-sm text-gray-500 text-center py-4">
                No VMs defined. Click "Add VM" to create one.
              </p>
            )}
          </div>
        </div>
      </ModalBody>

      <ModalFooter className="justify-between">
        <div className="text-xs text-gray-500">
          {hasChanges() ? (
            <span className="text-yellow-600 font-medium">Unsaved changes</span>
          ) : (
            <span>No changes</span>
          )}
          {' · '}
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
            disabled={saving || !hasChanges()}
            className={clsx(
              'inline-flex items-center px-4 py-2 text-sm font-medium rounded-md',
              saving || !hasChanges()
                ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                : 'bg-indigo-600 text-white hover:bg-indigo-700'
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
