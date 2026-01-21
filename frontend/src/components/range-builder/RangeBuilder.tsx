// frontend/src/components/range-builder/RangeBuilder.tsx
import { useCallback, useState, useMemo } from 'react'
import {
  ReactFlow,
  Controls,
  Background,
  applyNodeChanges,
  applyEdgeChanges,
  addEdge,
  Node,
  Edge,
  OnNodesChange,
  OnEdgesChange,
  OnConnect,
  BackgroundVariant,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { VMNode } from './nodes/VMNode'
import { NetworkNode } from './nodes/NetworkNode'
import { ComponentPanel } from './ComponentPanel'
import type { VM, Network, BaseImage } from '../../types'

interface RangeBuilderProps {
  rangeId: string
  networks: Network[]
  vms: VM[]
  baseImages: BaseImage[]
  onAddNetwork: (data: Partial<Network>) => Promise<void>
  onAddVM: (data: Partial<VM>) => Promise<void>
  onUpdateVM: (id: string, position: { x: number; y: number }) => Promise<void>
  onDeleteVM: (id: string) => Promise<void>
  onDeleteNetwork: (id: string) => Promise<void>
}

export function RangeBuilder({
  rangeId,
  networks,
  vms,
  baseImages,
  onAddNetwork,
  onAddVM,
  onUpdateVM,
  onDeleteVM: _onDeleteVM,
  onDeleteNetwork: _onDeleteNetwork,
}: RangeBuilderProps) {
  // Note: _onDeleteVM and _onDeleteNetwork are available for future use
  // Convert networks and VMs to React Flow nodes
  const initialNodes: Node[] = useMemo(() => {
    const networkNodes: Node[] = networks.map((network, index) => ({
      id: 'network-' + network.id,
      type: 'network',
      position: { x: 100 + index * 350, y: 50 },
      data: { network },
    }))

    const vmNodes: Node[] = vms.map((vm) => ({
      id: 'vm-' + vm.id,
      type: 'vm',
      position: { x: vm.position_x || 100, y: vm.position_y || 200 },
      data: {
        vm,
        baseImage: baseImages.find(img => img.id === vm.base_image_id),
        network: networks.find(n => n.id === vm.network_id),
      },
      parentId: 'network-' + vm.network_id,
      extent: 'parent' as const,
    }))

    return [...networkNodes, ...vmNodes]
  }, [networks, vms, baseImages])

  // Create edges connecting VMs to networks
  const initialEdges: Edge[] = useMemo(() => {
    return vms.map((vm) => ({
      id: 'edge-' + vm.id,
      source: 'network-' + vm.network_id,
      target: 'vm-' + vm.id,
      type: 'smoothstep',
      animated: vm.status === 'running',
      style: {
        stroke: vm.status === 'running' ? '#22c55e' : '#6b7280',
      },
    }))
  }, [vms])

  const [nodes, setNodes] = useState<Node[]>(initialNodes)
  const [edges, setEdges] = useState<Edge[]>(initialEdges)

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const nodeTypes = useMemo(() => ({
    vm: VMNode as any,
    network: NetworkNode as any,
  }), [])

  const onNodesChange: OnNodesChange = useCallback(
    (changes) => {
      setNodes((nds) => applyNodeChanges(changes, nds))

      // Handle position changes for VMs
      changes.forEach((change) => {
        if (change.type === 'position' && change.dragging === false && change.position) {
          const nodeId = change.id
          if (nodeId.startsWith('vm-')) {
            const vmId = nodeId.replace('vm-', '')
            onUpdateVM(vmId, change.position)
          }
        }
      })
    },
    [onUpdateVM]
  )

  const onEdgesChange: OnEdgesChange = useCallback(
    (changes) => setEdges((eds) => applyEdgeChanges(changes, eds)),
    []
  )

  const onConnect: OnConnect = useCallback(
    (connection) => setEdges((eds) => addEdge(connection, eds)),
    []
  )

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault()

      const type = event.dataTransfer.getData('application/reactflow/type')
      const baseImageId = event.dataTransfer.getData('application/reactflow/baseImageId')

      if (!type) return

      const position = {
        x: event.clientX - 250,
        y: event.clientY - 100,
      }

      if (type === 'network') {
        const newNetworkNum = networks.length + 1
        onAddNetwork({
          name: 'Network ' + newNetworkNum,
          subnet: '10.0.' + newNetworkNum + '.0/24',
          gateway: '10.0.' + newNetworkNum + '.1',
        })
      } else if (type === 'vm' && baseImageId) {
        const baseImage = baseImages.find(img => img.id === baseImageId)
        if (baseImage && networks.length > 0) {
          const network = networks[0]
          const existingIps = vms
            .filter(v => v.network_id === network.id)
            .map(v => parseInt(v.ip_address.split('.').pop() || '0'))
          const nextIp = Math.max(10, ...existingIps) + 1
          const subnetBase = network.subnet.replace('.0/24', '')

          onAddVM({
            range_id: rangeId,
            network_id: network.id,
            base_image_id: baseImageId,
            hostname: baseImage.name.toLowerCase().replace(/\s+/g, '-') + '-' + (vms.length + 1),
            ip_address: subnetBase + '.' + nextIp,
            cpu: baseImage.default_cpu,
            ram_mb: baseImage.default_ram_mb,
            disk_gb: baseImage.default_disk_gb,
            position_x: position.x,
            position_y: position.y,
          })
        }
      }
    },
    [networks, vms, baseImages, rangeId, onAddNetwork, onAddVM]
  )

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  return (
    <div className="flex h-[600px] border border-gray-200 rounded-lg overflow-hidden">
      <ComponentPanel baseImages={baseImages} />
      <div className="flex-1">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onDrop={onDrop}
          onDragOver={onDragOver}
          nodeTypes={nodeTypes}
          fitView
          snapToGrid
          snapGrid={[15, 15]}
        >
          <Controls />
          <Background variant={BackgroundVariant.Dots} gap={20} size={1} />
        </ReactFlow>
      </div>
    </div>
  )
}
