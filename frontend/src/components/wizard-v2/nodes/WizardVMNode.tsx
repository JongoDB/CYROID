// frontend/src/components/wizard-v2/nodes/WizardVMNode.tsx
import { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import { Server, Cpu, MemoryStick } from 'lucide-react';
import clsx from 'clsx';
import { VMPlacement } from '../../../stores/wizardStore';

export interface WizardVMNodeData {
  vm: VMPlacement;
  onSelect: (id: string) => void;
  isSelected: boolean;
}

interface WizardVMNodeProps {
  data: WizardVMNodeData;
}

export const WizardVMNode = memo(({ data }: WizardVMNodeProps) => {
  const { vm, onSelect, isSelected } = data;

  return (
    <div
      onClick={(e) => {
        e.stopPropagation();
        onSelect(vm.id);
      }}
      className={clsx(
        'px-3 py-2 rounded-lg border-2 shadow-sm min-w-[160px] cursor-pointer transition-all bg-white',
        isSelected ? 'border-primary-500 ring-2 ring-primary-200' : 'border-gray-300 hover:border-gray-400'
      )}
    >
      <Handle type="target" position={Position.Top} className="w-2 h-2 !bg-gray-400" />

      <div className="flex items-center gap-2 mb-1">
        <Server className="w-4 h-4 text-gray-500" />
        <span className="text-sm font-medium text-gray-900 truncate">{vm.hostname}</span>
      </div>

      <div className="text-xs text-gray-500 mb-1">{vm.templateName}</div>

      <div className="flex items-center gap-2 text-[10px] text-gray-400">
        <span className="flex items-center gap-0.5">
          <Cpu className="w-3 h-3" />
          {vm.cpu}
        </span>
        <span className="flex items-center gap-0.5">
          <MemoryStick className="w-3 h-3" />
          {vm.ramMb}MB
        </span>
        {vm.ip && <span>IP: {vm.ip}</span>}
      </div>

      <Handle type="source" position={Position.Bottom} className="w-2 h-2 !bg-gray-400" />
    </div>
  );
});

WizardVMNode.displayName = 'WizardVMNode';
