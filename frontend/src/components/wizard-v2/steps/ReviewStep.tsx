// frontend/src/components/wizard-v2/steps/ReviewStep.tsx
import { useState, useMemo } from 'react';
import {
  ReactFlow,
  Controls,
  Background,
  BackgroundVariant,
  Node,
  Edge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { ChevronDown, ChevronRight, Network, Server, Users, ShieldAlert } from 'lucide-react';
import { useWizardStore } from '../../../stores/wizardStore';
import { WizardNetworkNode } from '../nodes/WizardNetworkNode';
import { WizardVMNode } from '../nodes/WizardVMNode';
import { VULN_PRESETS } from '../data/vulnPresets';

interface CollapsibleSectionProps {
  title: string;
  icon: typeof Network;
  count: number;
  children: React.ReactNode;
  defaultOpen?: boolean;
}

function CollapsibleSection({ title, icon: Icon, count, children, defaultOpen = false }: CollapsibleSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Icon className="w-4 h-4 text-gray-500" />
          <span className="font-medium text-gray-900">{title}</span>
          <span className="text-sm text-gray-500">({count})</span>
        </div>
        {isOpen ? (
          <ChevronDown className="w-4 h-4 text-gray-400" />
        ) : (
          <ChevronRight className="w-4 h-4 text-gray-400" />
        )}
      </button>
      {isOpen && <div className="p-4 border-t">{children}</div>}
    </div>
  );
}

export function ReviewStep() {
  const { environment, services, networks, users, vulnerabilities, rangeName, saveAsBlueprint, setRangeName, setSaveAsBlueprint } = useWizardStore();

  // Calculate totals
  const totalVms = networks.vms.length;
  const totalNetworks = networks.segments.length;
  const totalUsers = users.groups.reduce((sum, g) => sum + g.count, 0);
  const vulnPreset = VULN_PRESETS[vulnerabilities.preset];

  // Read-only React Flow nodes
  const nodes: Node[] = useMemo(() => {
    const networkNodes: Node[] = networks.segments.map((segment) => ({
      id: segment.id,
      type: 'wizardNetwork',
      position: segment.position,
      data: { segment, onSelect: () => {}, isSelected: false },
      draggable: false,
      selectable: false,
    }));

    const vmNodes: Node[] = networks.vms.map((vm) => ({
      id: vm.id,
      type: 'wizardVm',
      position: vm.position,
      data: { vm, onSelect: () => {}, isSelected: false },
      draggable: false,
      selectable: false,
    }));

    return [...networkNodes, ...vmNodes];
  }, [networks.segments, networks.vms]);

  const edges: Edge[] = useMemo(() => {
    return networks.vms
      .filter(vm => vm.networkId)
      .map((vm) => ({
        id: `edge-${vm.id}`,
        source: vm.networkId,
        target: vm.id,
        type: 'smoothstep',
        style: { stroke: '#6b7280' },
      }));
  }, [networks.vms]);

  const nodeTypes = useMemo(() => ({
    wizardNetwork: WizardNetworkNode,
    wizardVm: WizardVMNode,
  }), []);

  return (
    <div className="max-w-5xl mx-auto">
      <h2 className="text-2xl font-bold text-gray-900 mb-2">Review & Deploy</h2>
      <p className="text-gray-600 mb-6">
        Review your configuration before creating the range.
      </p>

      {/* Topology preview */}
      <div className="h-[300px] border border-gray-200 rounded-lg overflow-hidden mb-6">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          panOnDrag={false}
          zoomOnScroll={false}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
        >
          <Controls showInteractive={false} />
          <Background variant={BackgroundVariant.Dots} gap={20} size={1} />
        </ReactFlow>
      </div>

      {/* Configuration summary */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        {/* Environment summary */}
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="text-sm font-medium text-gray-500 mb-1">Environment</div>
          <div className="text-lg font-semibold text-gray-900 capitalize">{environment.type}</div>
          <div className="text-sm text-gray-500">{services.selected.length} services selected</div>
        </div>

        {/* Resource summary */}
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="text-sm font-medium text-gray-500 mb-1">Resources</div>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div>
              <div className="text-lg font-semibold text-gray-900">{totalNetworks}</div>
              <div className="text-xs text-gray-500">Networks</div>
            </div>
            <div>
              <div className="text-lg font-semibold text-gray-900">{totalVms}</div>
              <div className="text-xs text-gray-500">VMs</div>
            </div>
            <div>
              <div className="text-lg font-semibold text-gray-900">{totalUsers}</div>
              <div className="text-xs text-gray-500">Users</div>
            </div>
          </div>
        </div>
      </div>

      {/* Collapsible details */}
      <div className="space-y-3 mb-6">
        <CollapsibleSection title="Networks" icon={Network} count={totalNetworks}>
          <table className="w-full text-sm">
            <thead className="text-left text-gray-500">
              <tr>
                <th className="pb-2">Name</th>
                <th className="pb-2">Subnet</th>
                <th className="pb-2">Gateway</th>
                <th className="pb-2">Options</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {networks.segments.map((net) => (
                <tr key={net.id}>
                  <td className="py-2 font-medium text-gray-900">{net.name}</td>
                  <td className="py-2 text-gray-600">{net.subnet}</td>
                  <td className="py-2 text-gray-600">{net.gateway}</td>
                  <td className="py-2">
                    {net.dhcp && <span className="px-1.5 py-0.5 text-xs bg-blue-100 text-blue-700 rounded mr-1">DHCP</span>}
                    {net.isolated && <span className="px-1.5 py-0.5 text-xs bg-orange-100 text-orange-700 rounded">Isolated</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CollapsibleSection>

        <CollapsibleSection title="Virtual Machines" icon={Server} count={totalVms}>
          <table className="w-full text-sm">
            <thead className="text-left text-gray-500">
              <tr>
                <th className="pb-2">Hostname</th>
                <th className="pb-2">Template</th>
                <th className="pb-2">Network</th>
                <th className="pb-2">IP</th>
                <th className="pb-2">Resources</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {networks.vms.map((vm) => {
                const network = networks.segments.find(n => n.id === vm.networkId);
                return (
                  <tr key={vm.id}>
                    <td className="py-2 font-medium text-gray-900">{vm.hostname}</td>
                    <td className="py-2 text-gray-600">{vm.templateName}</td>
                    <td className="py-2 text-gray-600">{network?.name || '-'}</td>
                    <td className="py-2 text-gray-600 font-mono text-xs">{vm.ip}</td>
                    <td className="py-2 text-gray-500 text-xs">{vm.cpu} CPU, {vm.ramMb}MB, {vm.diskGb}GB</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </CollapsibleSection>

        <CollapsibleSection title="Users" icon={Users} count={totalUsers}>
          {totalUsers === 0 ? (
            <p className="text-gray-500 text-sm">No users configured</p>
          ) : (
            <div className="grid grid-cols-4 gap-4">
              {users.groups.filter(g => g.count > 0).map((group) => (
                <div key={group.id} className="text-center p-3 bg-gray-50 rounded-lg">
                  <div className="text-2xl font-bold text-gray-900">{group.count}</div>
                  <div className="text-sm text-gray-600">{group.name}</div>
                </div>
              ))}
            </div>
          )}
        </CollapsibleSection>

        <CollapsibleSection title="Vulnerabilities" icon={ShieldAlert} count={vulnPreset.vulnIds.length}>
          <div className="flex items-center gap-4">
            <div>
              <span className="font-medium text-gray-900">{vulnPreset.name}</span>
              <p className="text-sm text-gray-500">{vulnPreset.description}</p>
            </div>
          </div>
          {vulnerabilities.narrative && (
            <div className="mt-3 p-3 bg-gray-50 rounded-lg">
              <div className="text-xs font-medium text-gray-500 mb-1">Attack Narrative</div>
              <p className="text-sm text-gray-700">{vulnerabilities.narrative}</p>
            </div>
          )}
        </CollapsibleSection>
      </div>

      {/* Range name and options */}
      <div className="bg-primary-50 rounded-lg p-4 border border-primary-200">
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-2">Range Name</label>
          <input
            type="text"
            value={rangeName}
            onChange={(e) => setRangeName(e.target.value)}
            placeholder="Enter a name for your range..."
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-primary-500 focus:border-primary-500"
          />
        </div>

        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={saveAsBlueprint}
            onChange={(e) => setSaveAsBlueprint(e.target.checked)}
            className="w-5 h-5 rounded border-gray-300 text-primary-600"
          />
          <div>
            <span className="font-medium text-gray-900">Save as Blueprint</span>
            <p className="text-sm text-gray-500">Create a reusable template from this configuration</p>
          </div>
        </label>
      </div>
    </div>
  );
}
