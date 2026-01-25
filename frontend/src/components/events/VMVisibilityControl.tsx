import { useState, useEffect, useCallback } from 'react'
import { Monitor, Eye, EyeOff, Users, RefreshCw } from 'lucide-react'
import { trainingEventsApi, VMVisibilityResponse, TrainingEventDetail } from '../../services/api'
import { toast } from '../../stores/toastStore'

interface VMVisibilityControlProps {
  event: TrainingEventDetail
  canManage: boolean
  onUpdate?: () => void
}

export function VMVisibilityControl({ event, canManage, onUpdate }: VMVisibilityControlProps) {
  const [selectedUserId, setSelectedUserId] = useState<string>('')
  const [visibility, setVisibility] = useState<VMVisibilityResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)

  // Filter to only show student participants with deployed ranges
  const studentsWithRanges = event.participants?.filter(
    (p) => p.role === 'student' && p.range_id
  ) || []

  // Load visibility when user selected
  const loadVisibility = useCallback(async (userId: string) => {
    if (!userId) {
      setVisibility(null)
      return
    }

    setLoading(true)
    try {
      const response = await trainingEventsApi.getParticipantVMVisibility(event.id, userId)
      setVisibility(response.data)
    } catch (error) {
      console.error('Failed to load VM visibility:', error)
      toast.error('Failed to load VM visibility settings')
    } finally {
      setLoading(false)
    }
  }, [event.id])

  useEffect(() => {
    if (selectedUserId) {
      loadVisibility(selectedUserId)
    }
  }, [selectedUserId, loadVisibility])

  // Toggle VM visibility
  const handleToggleVM = async (vmId: string) => {
    if (!visibility || !canManage) return

    const currentlyHidden = visibility.hidden_vm_ids.includes(vmId)
    const newHiddenIds = currentlyHidden
      ? visibility.hidden_vm_ids.filter((id) => id !== vmId)
      : [...visibility.hidden_vm_ids, vmId]

    // Optimistic update
    setVisibility({
      ...visibility,
      hidden_vm_ids: newHiddenIds,
      vms: visibility.vms.map((vm) =>
        vm.id === vmId ? { ...vm, is_hidden: !currentlyHidden } : vm
      ),
    })

    setSaving(true)
    try {
      await trainingEventsApi.updateParticipantVMVisibility(event.id, selectedUserId, newHiddenIds)
      toast.success(currentlyHidden ? 'VM now visible' : 'VM hidden')
      onUpdate?.()
    } catch (error) {
      console.error('Failed to update VM visibility:', error)
      toast.error('Failed to update VM visibility')
      // Revert on error
      loadVisibility(selectedUserId)
    } finally {
      setSaving(false)
    }
  }

  // Quick actions
  const handleShowAll = async () => {
    if (!visibility || !canManage) return

    setSaving(true)
    try {
      await trainingEventsApi.updateParticipantVMVisibility(event.id, selectedUserId, [])
      setVisibility({ ...visibility, hidden_vm_ids: [], vms: visibility.vms.map((vm) => ({ ...vm, is_hidden: false })) })
      toast.success('All VMs now visible')
      onUpdate?.()
    } catch (error) {
      console.error('Failed to show all VMs:', error)
      toast.error('Failed to update VM visibility')
    } finally {
      setSaving(false)
    }
  }

  const handleHideAll = async () => {
    if (!visibility || !canManage) return

    const allVmIds = visibility.vms.map((vm) => vm.id)
    setSaving(true)
    try {
      await trainingEventsApi.updateParticipantVMVisibility(event.id, selectedUserId, allVmIds)
      setVisibility({ ...visibility, hidden_vm_ids: allVmIds, vms: visibility.vms.map((vm) => ({ ...vm, is_hidden: true })) })
      toast.success('All VMs now hidden')
      onUpdate?.()
    } catch (error) {
      console.error('Failed to hide all VMs:', error)
      toast.error('Failed to update VM visibility')
    } finally {
      setSaving(false)
    }
  }

  // Don't show if no students with ranges
  if (studentsWithRanges.length === 0) {
    return null
  }

  return (
    <div className="bg-white shadow rounded-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-gray-900 flex items-center gap-2">
          <Monitor className="h-4 w-4" />
          VM Console Visibility
        </h3>
        {visibility && (
          <button
            onClick={() => loadVisibility(selectedUserId)}
            disabled={loading}
            className="text-gray-400 hover:text-gray-600"
            title="Refresh"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        )}
      </div>

      <p className="text-xs text-gray-500 mb-4">
        Control which VMs each student can see and access via console
      </p>

      {/* Participant selector */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-1">
          <Users className="inline h-4 w-4 mr-1" />
          Select Student
        </label>
        <select
          value={selectedUserId}
          onChange={(e) => setSelectedUserId(e.target.value)}
          className="w-full border border-gray-300 rounded-md py-2 px-3 text-sm focus:ring-primary-500 focus:border-primary-500"
        >
          <option value="">Select a student...</option>
          {studentsWithRanges.map((p) => (
            <option key={p.user_id} value={p.user_id}>
              {p.username || p.user_id} ({p.range_name || 'Range'})
            </option>
          ))}
        </select>
      </div>

      {/* Loading state */}
      {loading && (
        <div className="text-center py-8 text-gray-500">
          <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2" />
          <p className="text-sm">Loading VMs...</p>
        </div>
      )}

      {/* VM list */}
      {visibility && !loading && (
        <>
          {visibility.vms.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <Monitor className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">No VMs in this student's range</p>
            </div>
          ) : (
            <div className="border border-gray-200 rounded-md max-h-64 overflow-y-auto">
              {visibility.vms.map((vm) => {
                const isHidden = visibility.hidden_vm_ids.includes(vm.id)
                return (
                  <label
                    key={vm.id}
                    className={`flex items-center px-3 py-2 hover:bg-gray-50 cursor-pointer border-b border-gray-100 last:border-b-0 ${
                      !canManage ? 'opacity-75 cursor-not-allowed' : ''
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={!isHidden}
                      onChange={() => handleToggleVM(vm.id)}
                      disabled={!canManage || saving}
                      className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                    />
                    <span className="ml-3 flex-1">
                      <span className={`text-sm ${isHidden ? 'text-gray-400' : 'text-gray-900'}`}>
                        {vm.hostname}
                      </span>
                      <span className={`ml-2 text-xs ${
                        vm.status === 'running' ? 'text-green-600' :
                        vm.status === 'stopped' ? 'text-gray-500' :
                        'text-yellow-600'
                      }`}>
                        ({vm.status})
                      </span>
                    </span>
                    {isHidden ? (
                      <EyeOff className="h-4 w-4 text-gray-400" />
                    ) : (
                      <Eye className="h-4 w-4 text-green-500" />
                    )}
                  </label>
                )
              })}
            </div>
          )}

          {/* Quick actions */}
          {visibility.vms.length > 0 && canManage && (
            <div className="mt-4 flex gap-2">
              <button
                onClick={handleShowAll}
                disabled={saving || visibility.hidden_vm_ids.length === 0}
                className="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-md text-gray-700 bg-gray-100 hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Eye className="h-3 w-3 mr-1" />
                Show All
              </button>
              <button
                onClick={handleHideAll}
                disabled={saving || visibility.hidden_vm_ids.length === visibility.vms.length}
                className="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-md text-gray-700 bg-gray-100 hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <EyeOff className="h-3 w-3 mr-1" />
                Hide All
              </button>
            </div>
          )}

          {/* Visibility summary */}
          <div className="mt-4 text-xs text-gray-500">
            {visibility.hidden_vm_ids.length === 0 ? (
              <span className="text-green-600">All {visibility.vms.length} VMs visible</span>
            ) : visibility.hidden_vm_ids.length === visibility.vms.length ? (
              <span className="text-red-600">All VMs hidden</span>
            ) : (
              <span>
                {visibility.vms.length - visibility.hidden_vm_ids.length} of {visibility.vms.length} VMs visible
              </span>
            )}
          </div>
        </>
      )}
    </div>
  )
}
