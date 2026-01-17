// frontend/src/components/lab/VMSelector.tsx
import clsx from 'clsx'
import { Monitor } from 'lucide-react'
import { VM } from '../../types'

interface VMSelectorProps {
  vms: VM[]
  selectedVmId: string | null
  onSelectVM: (vmId: string) => void
}

export function VMSelector({ vms, selectedVmId, onSelectVM }: VMSelectorProps) {
  const runningVms = vms.filter(vm => vm.status === 'running')

  if (runningVms.length === 0) {
    return (
      <div className="flex items-center justify-center px-4 py-3 bg-gray-800 border-t border-gray-700">
        <span className="text-gray-400 text-sm">No running VMs</span>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-2 px-4 py-3 bg-gray-800 border-t border-gray-700 overflow-x-auto">
      <span className="text-gray-400 text-sm flex-shrink-0">VMs:</span>
      {runningVms.map((vm) => (
        <button
          key={vm.id}
          onClick={() => onSelectVM(vm.id)}
          className={clsx(
            'flex items-center gap-1.5 px-3 py-1.5 rounded text-sm whitespace-nowrap transition-colors',
            selectedVmId === vm.id
              ? 'bg-blue-600 text-white'
              : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
          )}
        >
          <Monitor className="w-4 h-4" />
          {vm.hostname}
          {selectedVmId === vm.id && (
            <span className="w-2 h-2 rounded-full bg-green-400" />
          )}
        </button>
      ))}
    </div>
  )
}
