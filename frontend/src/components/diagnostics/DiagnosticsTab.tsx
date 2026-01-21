// frontend/src/components/diagnostics/DiagnosticsTab.tsx
import { useState } from 'react'
import { Terminal } from 'lucide-react'
import type { Range, Network, VM } from '../../types'
import { ComponentHealth } from './ComponentHealth'
import { ErrorTimeline } from './ErrorTimeline'
import { LogViewer } from './LogViewer'
import { RangeConsole } from '../console/RangeConsole'

interface DiagnosticsTabProps {
  range: Range
  networks: Network[]
  vms: VM[]
}

export function DiagnosticsTab({ range, networks, vms }: DiagnosticsTabProps) {
  const [selectedVm, setSelectedVm] = useState<VM | null>(null)
  const [showRangeConsole, setShowRangeConsole] = useState(false)

  const handleSelectVm = (vm: VM) => {
    // Toggle selection if clicking the same VM
    if (selectedVm?.id === vm.id) {
      setSelectedVm(null)
    } else {
      setSelectedVm(vm)
    }
  }

  const handleViewLogs = (vm: VM) => {
    setSelectedVm(vm)
  }

  const token = localStorage.getItem('token') || ''

  return (
    <div className="space-y-4">
      {/* Range Console toggle button */}
      <div className="flex justify-end">
        <button
          onClick={() => setShowRangeConsole(!showRangeConsole)}
          className={`inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
            showRangeConsole
              ? 'bg-cyan-600 text-white hover:bg-cyan-700'
              : 'bg-gray-700 text-gray-200 hover:bg-gray-600'
          }`}
        >
          <Terminal className="w-4 h-4" />
          {showRangeConsole ? 'Hide Range Console' : 'Open Range Console'}
        </button>
      </div>

      {/* Range Console - DinD shell access */}
      {showRangeConsole && (
        <div className="h-[500px]">
          <RangeConsole
            rangeId={range.id}
            rangeName={range.name}
            token={token}
            onClose={() => setShowRangeConsole(false)}
          />
        </div>
      )}

      {/* Two-column layout for health and timeline */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ComponentHealth
          range={range}
          networks={networks}
          vms={vms}
          onSelectVm={handleSelectVm}
          selectedVmId={selectedVm?.id ?? null}
        />
        <ErrorTimeline
          rangeId={range.id}
          vms={vms}
          onViewLogs={handleViewLogs}
        />
      </div>

      {/* Log viewer - shown when VM is selected */}
      {selectedVm && (
        <LogViewer
          vmId={selectedVm.id}
          vmHostname={selectedVm.hostname}
          onClose={() => setSelectedVm(null)}
        />
      )}
    </div>
  )
}
