// frontend/src/components/wizard-v2/panels/NetworkPropertiesPanel.tsx
import { useState, useEffect, useMemo } from 'react';
import { X, Trash2, ChevronDown } from 'lucide-react';
import { useWizardStore } from '../../../stores/wizardStore';
import { imagesApi } from '../../../services/api';
import type { BaseImage } from '../../../types';

interface Props {
  selectedNetworkId: string | null;
  selectedVmId: string | null;
  onClose: () => void;
}

// Collapsible section component
function CollapsibleSection({
  title,
  defaultOpen = false,
  children
}: {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  return (
    <details className="group border border-gray-200 rounded-md bg-gray-50" open={defaultOpen}>
      <summary className="px-3 py-2 cursor-pointer text-xs font-medium text-gray-700 hover:bg-gray-100 flex items-center gap-1 list-none [&::-webkit-details-marker]:hidden">
        <ChevronDown className="w-3 h-3 transition-transform group-open:rotate-180" />
        {title}
      </summary>
      <div className="px-3 py-2 border-t border-gray-200 bg-white">
        {children}
      </div>
    </details>
  );
}

// Language options for Windows/Linux
const LANGUAGE_OPTIONS = [
  { value: 'en-US', label: 'English (US)' },
  { value: 'en-GB', label: 'English (UK)' },
  { value: 'de-DE', label: 'German' },
  { value: 'fr-FR', label: 'French' },
  { value: 'es-ES', label: 'Spanish' },
  { value: 'it-IT', label: 'Italian' },
  { value: 'pt-BR', label: 'Portuguese (Brazil)' },
  { value: 'ja-JP', label: 'Japanese' },
  { value: 'ko-KR', label: 'Korean' },
  { value: 'zh-CN', label: 'Chinese (Simplified)' },
];

export function NetworkPropertiesPanel({ selectedNetworkId, selectedVmId, onClose }: Props) {
  const { networks, updateNetwork, removeNetwork, updateVM, removeVM } = useWizardStore();
  const [baseImages, setBaseImages] = useState<BaseImage[]>([]);

  useEffect(() => {
    imagesApi.listBase().then(res => setBaseImages(res.data));
  }, []);

  const selectedNetwork = networks.segments.find(n => n.id === selectedNetworkId);
  const selectedVm = networks.vms.find(v => v.id === selectedVmId);

  // Get base image for selected VM
  const vmBaseImage = useMemo(() => {
    if (!selectedVm) return null;
    // Try to find by baseImageId first, then by templateName (for backward compatibility)
    return baseImages.find(img => img.id === selectedVm.baseImageId) ||
           baseImages.find(img => img.name === selectedVm.templateName);
  }, [selectedVm, baseImages]);

  // OS type detection
  const osInfo = useMemo(() => {
    if (!vmBaseImage) return { isWindows: false, isLinuxISO: false, isContainer: true };

    const isWindows = vmBaseImage.os_type === 'windows';
    const dockerTag = vmBaseImage.docker_image_tag?.toLowerCase() || '';
    const isLinuxISO = vmBaseImage.vm_type === 'linux_vm';
    const isKasmVNC = dockerTag.includes('kasmweb/');
    const isLinuxServer = dockerTag.includes('linuxserver/') || dockerTag.includes('lscr.io/linuxserver');
    const isContainer = vmBaseImage.image_type === 'container';
    const needsCredentials = isWindows || isLinuxISO || isKasmVNC || isLinuxServer;

    return { isWindows, isLinuxISO, isContainer, isKasmVNC, isLinuxServer, needsCredentials };
  }, [vmBaseImage]);

  if (!selectedNetwork && !selectedVm) {
    return null;
  }

  // Network properties panel
  if (selectedNetwork) {
    return (
      <div className="absolute bottom-0 left-0 right-0 bg-white border-t border-gray-200 p-4 shadow-lg max-h-[50%] overflow-y-auto">
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

  // VM properties panel
  if (selectedVm) {
    const defaultUsername = osInfo.isWindows ? 'Admin' : 'user';

    return (
      <div className="absolute bottom-0 left-0 right-0 bg-white border-t border-gray-200 p-4 shadow-lg max-h-[60%] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-gray-900">VM Properties</h3>
            <p className="text-xs text-gray-500">
              {vmBaseImage?.name || selectedVm.templateName}
              {vmBaseImage && ` (${vmBaseImage.os_type === 'windows' ? 'Windows' : 'Linux'}${osInfo.isLinuxISO ? ' VM' : osInfo.isContainer ? ' Container' : ''})`}
            </p>
          </div>
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

        {/* Basic Properties - Always visible */}
        <div className="grid grid-cols-5 gap-4 mb-4">
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
              placeholder={osInfo.isContainer ? 'Auto (DHCP)' : ''}
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

        {/* Collapsible Sections */}
        <div className="space-y-2">
          {/* Credentials - All OS types that need them */}
          {osInfo.needsCredentials && (
            <CollapsibleSection title="Credentials">
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Username</label>
                  <input
                    type="text"
                    value={selectedVm.username ?? defaultUsername}
                    onChange={(e) => updateVM(selectedVm.id, { username: e.target.value })}
                    className="w-full px-2 py-1 text-sm border border-gray-300 rounded"
                    placeholder={defaultUsername}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Password</label>
                  <input
                    type="password"
                    value={selectedVm.password ?? ''}
                    onChange={(e) => updateVM(selectedVm.id, { password: e.target.value })}
                    className="w-full px-2 py-1 text-sm border border-gray-300 rounded"
                    placeholder="Leave blank for default"
                  />
                </div>
                {!osInfo.isWindows && (
                  <div className="flex items-end">
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={selectedVm.sudoEnabled ?? true}
                        onChange={(e) => updateVM(selectedVm.id, { sudoEnabled: e.target.checked })}
                        className="rounded border-gray-300"
                      />
                      Enable sudo
                    </label>
                  </div>
                )}
              </div>
            </CollapsibleSection>
          )}

          {/* Network Settings - Windows & Linux ISO only */}
          {(osInfo.isWindows || osInfo.isLinuxISO) && (
            <CollapsibleSection title="Network Settings">
              <div className="grid grid-cols-3 gap-4">
                <div className="flex items-end">
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={selectedVm.useDhcp ?? true}
                      onChange={(e) => updateVM(selectedVm.id, { useDhcp: e.target.checked })}
                      className="rounded border-gray-300"
                    />
                    Use DHCP
                  </label>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Gateway</label>
                  <input
                    type="text"
                    value={selectedVm.gateway ?? ''}
                    onChange={(e) => updateVM(selectedVm.id, { gateway: e.target.value })}
                    className="w-full px-2 py-1 text-sm border border-gray-300 rounded"
                    disabled={selectedVm.useDhcp ?? true}
                    placeholder="Auto from network"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">DNS Servers</label>
                  <input
                    type="text"
                    value={selectedVm.dnsServers ?? ''}
                    onChange={(e) => updateVM(selectedVm.id, { dnsServers: e.target.value })}
                    className="w-full px-2 py-1 text-sm border border-gray-300 rounded"
                    disabled={selectedVm.useDhcp ?? true}
                    placeholder="8.8.8.8, 8.8.4.4"
                  />
                </div>
              </div>
            </CollapsibleSection>
          )}

          {/* Storage - Windows & Linux ISO only */}
          {(osInfo.isWindows || osInfo.isLinuxISO) && (
            <CollapsibleSection title="Additional Storage">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Disk 2 (GB)</label>
                  <input
                    type="number"
                    min={0}
                    value={selectedVm.disk2Gb ?? 0}
                    onChange={(e) => updateVM(selectedVm.id, { disk2Gb: parseInt(e.target.value) || 0 })}
                    className="w-full px-2 py-1 text-sm border border-gray-300 rounded"
                    placeholder="0 = disabled"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Disk 3 (GB)</label>
                  <input
                    type="number"
                    min={0}
                    value={selectedVm.disk3Gb ?? 0}
                    onChange={(e) => updateVM(selectedVm.id, { disk3Gb: parseInt(e.target.value) || 0 })}
                    className="w-full px-2 py-1 text-sm border border-gray-300 rounded"
                    placeholder="0 = disabled"
                  />
                </div>
              </div>
            </CollapsibleSection>
          )}

          {/* Advanced - Windows & Linux ISO */}
          {(osInfo.isWindows || osInfo.isLinuxISO) && (
            <CollapsibleSection title="Advanced Options">
              <div className="space-y-4">
                {/* Display Type */}
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">Display Type</label>
                    <select
                      value={selectedVm.displayType ?? 'desktop'}
                      onChange={(e) => updateVM(selectedVm.id, { displayType: e.target.value as 'desktop' | 'server' })}
                      className="w-full px-2 py-1 text-sm border border-gray-300 rounded"
                    >
                      <option value="desktop">Desktop</option>
                      <option value="server">Server (Headless)</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">Language</label>
                    <select
                      value={selectedVm.language ?? 'en-US'}
                      onChange={(e) => updateVM(selectedVm.id, { language: e.target.value })}
                      className="w-full px-2 py-1 text-sm border border-gray-300 rounded"
                    >
                      {LANGUAGE_OPTIONS.map(opt => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">Keyboard Layout</label>
                    <input
                      type="text"
                      value={selectedVm.keyboard ?? 'en-US'}
                      onChange={(e) => updateVM(selectedVm.id, { keyboard: e.target.value })}
                      className="w-full px-2 py-1 text-sm border border-gray-300 rounded"
                      placeholder="en-US"
                    />
                  </div>
                </div>

                {/* Shared Folders */}
                <div className="flex items-center gap-6">
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={selectedVm.enableSharedFolder ?? false}
                      onChange={(e) => updateVM(selectedVm.id, { enableSharedFolder: e.target.checked })}
                      className="rounded border-gray-300"
                    />
                    Enable VM Shared Folder
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={selectedVm.enableGlobalShared ?? false}
                      onChange={(e) => updateVM(selectedVm.id, { enableGlobalShared: e.target.checked })}
                      className="rounded border-gray-300"
                    />
                    Enable Global Shared Folder
                  </label>
                </div>
              </div>
            </CollapsibleSection>
          )}

          {/* Shared Folders for Containers (simpler) */}
          {osInfo.isContainer && !osInfo.needsCredentials && (
            <CollapsibleSection title="Shared Folders">
              <div className="flex items-center gap-6">
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={selectedVm.enableSharedFolder ?? false}
                    onChange={(e) => updateVM(selectedVm.id, { enableSharedFolder: e.target.checked })}
                    className="rounded border-gray-300"
                  />
                  Enable VM Shared Folder
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={selectedVm.enableGlobalShared ?? false}
                    onChange={(e) => updateVM(selectedVm.id, { enableGlobalShared: e.target.checked })}
                    className="rounded border-gray-300"
                  />
                  Enable Global Shared Folder
                </label>
              </div>
            </CollapsibleSection>
          )}
        </div>
      </div>
    );
  }

  return null;
}
