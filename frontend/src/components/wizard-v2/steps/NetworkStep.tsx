// frontend/src/components/wizard-v2/steps/NetworkStep.tsx
import { useCallback, useMemo, useState, useEffect } from 'react';
import {
  ReactFlow,
  Controls,
  Background,
  BackgroundVariant,
  applyNodeChanges,
  applyEdgeChanges,
  addEdge,
  Node,
  Edge,
  OnNodesChange,
  OnEdgesChange,
  OnConnect,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Network, Server } from 'lucide-react';
import { useWizardStore, NetworkSegment } from '../../../stores/wizardStore';
import { WizardNetworkNode } from '../nodes/WizardNetworkNode';
import { WizardVMNode } from '../nodes/WizardVMNode';
import { NetworkPropertiesPanel } from '../panels/NetworkPropertiesPanel';
import { SERVICE_CATALOG } from '../data/servicePresets';

export function NetworkStep() {
  const { environment, services, networks, addNetwork, addVM, updateVM, addConnection } = useWizardStore();
  const [selectedNetworkId, setSelectedNetworkId] = useState<string | null>(null);
  const [selectedVmId, setSelectedVmId] = useState<string | null>(null);

  // Initialize networks from environment preset if empty
  useEffect(() => {
    if (networks.segments.length === 0 && environment.type !== 'custom') {
      const presetNetworks = getPresetNetworks(environment.type);
      presetNetworks.forEach((net, i) => {
        addNetwork({
          ...net,
          id: `network-${Date.now()}-${i}`,
          position: { x: 100 + i * 400, y: 100 },
        });
      });
    }
  }, [environment.type]);

  // Initialize VMs from selected services if empty
  useEffect(() => {
    if (networks.vms.length === 0 && services.selected.length > 0 && networks.segments.length > 0) {
      services.selected.forEach((serviceId, i) => {
        const service = SERVICE_CATALOG.find(s => s.id === serviceId);
        if (service) {
          const targetNetwork = networks.segments.find(n =>
            n.name.toLowerCase().includes(service.defaultNetwork.toLowerCase())
          ) || networks.segments[0];

          if (targetNetwork) {
            const baseIp = targetNetwork.subnet.replace('.0/24', '');
            addVM({
              id: `vm-${Date.now()}-${i}`,
              hostname: service.name.toLowerCase().replace(/\s+/g, '-'),
              templateId: '',
              templateName: service.templateName,
              networkId: targetNetwork.id,
              ip: `${baseIp}.${10 + i}`,
              cpu: service.cpu || 2,
              ramMb: service.ramMb || 2048,
              diskGb: service.diskGb || 20,
              position: { x: targetNetwork.position.x + 50, y: targetNetwork.position.y + 150 + i * 80 },
            });
          }
        }
      });
    }
  }, [services.selected, networks.segments.length]);

  // Convert to React Flow nodes
  const nodes: Node[] = useMemo(() => {
    const networkNodes: Node[] = networks.segments.map((segment) => ({
      id: segment.id,
      type: 'wizardNetwork',
      position: segment.position,
      data: {
        segment,
        onSelect: (id: string) => {
          setSelectedNetworkId(id);
          setSelectedVmId(null);
        },
        isSelected: selectedNetworkId === segment.id,
      },
    }));

    const vmNodes: Node[] = networks.vms.map((vm) => ({
      id: vm.id,
      type: 'wizardVm',
      position: vm.position,
      data: {
        vm,
        onSelect: (id: string) => {
          setSelectedVmId(id);
          setSelectedNetworkId(null);
        },
        isSelected: selectedVmId === vm.id,
      },
    }));

    return [...networkNodes, ...vmNodes];
  }, [networks.segments, networks.vms, selectedNetworkId, selectedVmId]);

  // Convert to React Flow edges
  const edges: Edge[] = useMemo(() => {
    // VM to Network edges
    const vmEdges = networks.vms
      .filter(vm => vm.networkId)
      .map((vm) => ({
        id: `edge-vm-${vm.id}`,
        source: vm.networkId,
        target: vm.id,
        type: 'smoothstep',
        animated: true,
        style: { stroke: '#6b7280' },
      }));

    // Network to Network edges
    const netEdges = networks.connections.map((conn) => ({
      id: conn.id,
      source: conn.sourceId,
      target: conn.targetId,
      type: 'smoothstep',
      style: { stroke: '#3b82f6', strokeWidth: 2 },
    }));

    return [...vmEdges, ...netEdges];
  }, [networks.vms, networks.connections]);

  const nodeTypes = useMemo(() => ({
    wizardNetwork: WizardNetworkNode as any,
    wizardVm: WizardVMNode as any,
  }), []);

  const [flowNodes, setFlowNodes] = useState<Node[]>(nodes);
  const [flowEdges, setFlowEdges] = useState<Edge[]>(edges);

  // Sync with store changes
  useEffect(() => {
    setFlowNodes(nodes);
  }, [nodes]);

  useEffect(() => {
    setFlowEdges(edges);
  }, [edges]);

  const onNodesChange: OnNodesChange = useCallback((changes) => {
    setFlowNodes((nds) => applyNodeChanges(changes, nds));

    // Update positions in store
    changes.forEach((change) => {
      if (change.type === 'position' && change.position && !change.dragging) {
        const node = networks.segments.find(n => n.id === change.id);
        if (node) {
          // Network position update would go here
        } else {
          const vm = networks.vms.find(v => v.id === change.id);
          if (vm) {
            updateVM(change.id, { position: change.position });
          }
        }
      }
    });
  }, [networks.segments, networks.vms, updateVM]);

  const onEdgesChange: OnEdgesChange = useCallback((changes) => {
    setFlowEdges((eds) => applyEdgeChanges(changes, eds));
  }, []);

  const onConnect: OnConnect = useCallback((connection) => {
    if (connection.source && connection.target) {
      // Check if it's a network-to-network connection
      const sourceNetwork = networks.segments.find(n => n.id === connection.source);
      const targetNetwork = networks.segments.find(n => n.id === connection.target);

      if (sourceNetwork && targetNetwork) {
        addConnection({
          id: `conn-${Date.now()}`,
          sourceId: connection.source,
          targetId: connection.target,
        });
      } else {
        // VM to network connection - update VM's networkId
        const vm = networks.vms.find(v => v.id === connection.target);
        if (vm && sourceNetwork) {
          updateVM(vm.id, { networkId: connection.source });
        }
      }
    }
    setFlowEdges((eds) => addEdge(connection, eds));
  }, [networks.segments, networks.vms, addConnection, updateVM]);

  const handleAddNetwork = () => {
    const id = `network-${Date.now()}`;
    const num = networks.segments.length + 1;
    addNetwork({
      id,
      name: `Network ${num}`,
      subnet: `10.${num}.0.0/24`,
      gateway: `10.${num}.0.1`,
      dhcp: false,
      isolated: false,
      position: { x: 100 + (num - 1) * 400, y: 100 },
    });
  };

  const handleAddVM = () => {
    if (networks.segments.length === 0) return;

    const targetNetwork = networks.segments[0];
    const id = `vm-${Date.now()}`;
    const num = networks.vms.length + 1;
    const baseIp = targetNetwork.subnet.replace('.0/24', '');

    addVM({
      id,
      hostname: `vm-${num}`,
      templateId: '',
      templateName: 'Ubuntu Server',
      networkId: targetNetwork.id,
      ip: `${baseIp}.${10 + num}`,
      cpu: 2,
      ramMb: 2048,
      diskGb: 20,
      position: { x: targetNetwork.position.x + 50, y: targetNetwork.position.y + 150 + (num - 1) * 80 },
    });
  };

  return (
    <div className="h-[calc(100vh-280px)] flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Network Topology</h2>
          <p className="text-gray-600">Design your network layout. Drag nodes to reposition, click to configure.</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleAddNetwork}
            className="inline-flex items-center px-3 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
          >
            <Network className="w-4 h-4 mr-2" />
            Add Network
          </button>
          <button
            onClick={handleAddVM}
            disabled={networks.segments.length === 0}
            className="inline-flex items-center px-3 py-2 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
          >
            <Server className="w-4 h-4 mr-2" />
            Add VM
          </button>
        </div>
      </div>

      <div className="flex-1 border border-gray-200 rounded-lg overflow-hidden relative">
        <ReactFlow
          nodes={flowNodes}
          edges={flowEdges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          nodeTypes={nodeTypes}
          fitView
          snapToGrid
          snapGrid={[20, 20]}
          onClick={() => {
            setSelectedNetworkId(null);
            setSelectedVmId(null);
          }}
        >
          <Controls />
          <Background variant={BackgroundVariant.Dots} gap={20} size={1} />
        </ReactFlow>

        <NetworkPropertiesPanel
          selectedNetworkId={selectedNetworkId}
          selectedVmId={selectedVmId}
          onClose={() => {
            setSelectedNetworkId(null);
            setSelectedVmId(null);
          }}
        />
      </div>
    </div>
  );
}

function getPresetNetworks(envType: string): Omit<NetworkSegment, 'id' | 'position'>[] {
  switch (envType) {
    case 'enterprise':
      return [
        { name: 'DMZ', subnet: '10.1.0.0/24', gateway: '10.1.0.1', dhcp: false, isolated: false },
        { name: 'Corporate', subnet: '10.2.0.0/24', gateway: '10.2.0.1', dhcp: true, isolated: false },
        { name: 'Management', subnet: '10.3.0.0/24', gateway: '10.3.0.1', dhcp: false, isolated: true },
      ];
    case 'industrial':
      return [
        { name: 'IT Network', subnet: '10.1.0.0/24', gateway: '10.1.0.1', dhcp: true, isolated: false },
        { name: 'OT Network', subnet: '10.2.0.0/24', gateway: '10.2.0.1', dhcp: false, isolated: true },
        { name: 'DMZ', subnet: '10.3.0.0/24', gateway: '10.3.0.1', dhcp: false, isolated: false },
      ];
    case 'cloud':
      return [
        { name: 'Public', subnet: '10.1.0.0/24', gateway: '10.1.0.1', dhcp: false, isolated: false },
        { name: 'Private', subnet: '10.2.0.0/24', gateway: '10.2.0.1', dhcp: true, isolated: true },
        { name: 'Database', subnet: '10.3.0.0/24', gateway: '10.3.0.1', dhcp: false, isolated: true },
      ];
    default:
      return [];
  }
}
