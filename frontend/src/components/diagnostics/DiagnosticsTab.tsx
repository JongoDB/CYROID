// frontend/src/components/diagnostics/DiagnosticsTab.tsx
import { useState } from 'react'
import type { Range, Network, VM } from '../../types'
import { ComponentHealth } from './ComponentHealth'
import { ErrorTimeline } from './ErrorTimeline'
import { LogViewer } from './LogViewer'

interface DiagnosticsTabProps {
  range: Range
  networks: Network[]
  vms: VM[]
}

export function DiagnosticsTab({ range, networks, vms }: DiagnosticsTabProps) {
  const [selectedVm, setSelectedVm] = useState<VM | null>(null)

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

  return (
    <div className="space-y-4">
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
