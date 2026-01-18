// frontend/src/components/wizard-v2/nodes/WizardNetworkNode.tsx
import { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import { Network, Shield } from 'lucide-react';
import clsx from 'clsx';
import { NetworkSegment } from '../../../stores/wizardStore';

export interface WizardNetworkNodeData {
  segment: NetworkSegment;
  onSelect: (id: string) => void;
  isSelected: boolean;
}

interface WizardNetworkNodeProps {
  data: WizardNetworkNodeData;
}

export const WizardNetworkNode = memo(({ data }: WizardNetworkNodeProps) => {
  const { segment, onSelect, isSelected } = data;

  return (
    <div
      onClick={() => onSelect(segment.id)}
      className={clsx(
        'px-4 py-3 rounded-xl border-2 shadow-md min-w-[280px] cursor-pointer transition-all',
        isSelected && 'ring-2 ring-primary-400',
        segment.isolated
          ? 'border-blue-400 bg-blue-50'
          : 'border-green-400 bg-green-50'
      )}
    >
      <Handle type="target" position={Position.Top} className="w-3 h-3 !bg-gray-400" />

      <div className="flex items-center gap-2 mb-2">
        <Network className="w-5 h-5 text-gray-600" />
        <div className="flex-1">
          <div className="text-sm font-semibold text-gray-900">{segment.name}</div>
          <div className="text-xs text-gray-500">{segment.subnet}</div>
        </div>
        <span
          className={clsx(
            'flex items-center gap-1 px-2 py-0.5 text-[10px] font-medium rounded',
            segment.isolated ? 'bg-blue-100 text-blue-700' : 'bg-green-100 text-green-700'
          )}
        >
          <Shield className="w-3 h-3" />
          {segment.isolated ? 'Isolated' : 'Open'}
        </span>
      </div>

      <div className="text-[10px] text-gray-400">
        Gateway: {segment.gateway}
        {segment.dhcp && ' | DHCP'}
      </div>

      <Handle type="source" position={Position.Bottom} className="w-3 h-3 !bg-gray-400" />
    </div>
  );
});

WizardNetworkNode.displayName = 'WizardNetworkNode';
