// frontend/src/components/scenarios/VMMappingModal.tsx
import { useState } from 'react'
import type { Scenario, VM } from '../../types'
import { X, Loader2, Server, ChevronDown } from 'lucide-react'

interface VMMappingModalProps {
  scenario: Scenario
  vms: VM[]
  onApply: (roleMapping: Record<string, string>) => Promise<void>
  onBack: () => void
  onClose: () => void
}

// Convert role slug to display name
function formatRoleName(role: string): string {
  return role
    .split('-')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

export default function VMMappingModal({
  scenario,
  vms,
  onApply,
  onBack,
  onClose,
}: VMMappingModalProps) {
  const [roleMapping, setRoleMapping] = useState<Record<string, string>>({})
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleVMSelect = (role: string, vmId: string) => {
    setRoleMapping((prev) => ({ ...prev, [role]: vmId }))
  }

  const allRolesMapped = scenario.required_roles.every((role) => roleMapping[role])

  const handleApply = async () => {
    if (!allRolesMapped) return

    setSubmitting(true)
    setError(null)
    try {
      await onApply(roleMapping)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to apply scenario')
      setSubmitting(false)
    }
  }

  // Check if a VM is already assigned to another role
  const getVMAssignment = (vmId: string): string | null => {
    for (const [role, id] of Object.entries(roleMapping)) {
      if (id === vmId) return role
    }
    return null
  }

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4">
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75" onClick={onClose} />

        <div className="relative bg-white rounded-lg shadow-xl max-w-lg w-full">
          <div className="flex items-center justify-between p-4 border-b">
            <h3 className="text-lg font-medium text-gray-900">
              Configure: {scenario.name}
            </h3>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-500">
              <X className="h-5 w-5" />
            </button>
          </div>

          <div className="p-4">
            <p className="text-sm text-gray-600 mb-4">
              This scenario requires {scenario.required_roles.length} target system
              {scenario.required_roles.length !== 1 ? 's' : ''}.
              Map each role to a VM in your range:
            </p>

            {error && (
              <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-md text-sm">
                {error}
              </div>
            )}

            <div className="space-y-3">
              {scenario.required_roles.map((role) => (
                <div key={role} className="flex items-center justify-between">
                  <label className="text-sm font-medium text-gray-700 w-1/3">
                    {formatRoleName(role)}
                  </label>
                  <div className="relative w-2/3">
                    <select
                      value={roleMapping[role] || ''}
                      onChange={(e) => handleVMSelect(role, e.target.value)}
                      className="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm appearance-none pr-8"
                    >
                      <option value="">Select a VM...</option>
                      {vms.map((vm) => {
                        const assignedTo = getVMAssignment(vm.id)
                        const isAssignedElsewhere = assignedTo && assignedTo !== role
                        return (
                          <option
                            key={vm.id}
                            value={vm.id}
                            disabled={isAssignedElsewhere}
                          >
                            {vm.hostname}
                            {isAssignedElsewhere && ` (→ ${formatRoleName(assignedTo)})`}
                          </option>
                        )
                      })}
                    </select>
                    <ChevronDown className="absolute right-2 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
                  </div>
                </div>
              ))}
            </div>

            {vms.length === 0 && (
              <div className="mt-4 p-3 bg-yellow-50 text-yellow-700 rounded-md text-sm">
                <Server className="inline h-4 w-4 mr-1" />
                No VMs in this range. Add VMs before applying a scenario.
              </div>
            )}
          </div>

          <div className="flex justify-between p-4 border-t bg-gray-50">
            <button
              type="button"
              onClick={onBack}
              className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
            >
              Back
            </button>
            <div className="flex space-x-3">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleApply}
                disabled={!allRolesMapped || submitting}
                className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 disabled:opacity-50"
              >
                {submitting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                Apply Scenario
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
