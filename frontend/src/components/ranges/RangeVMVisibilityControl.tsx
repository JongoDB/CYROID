import { useState, useEffect, useCallback } from 'react'
import { Monitor, Eye, EyeOff, RefreshCw, Save } from 'lucide-react'
import { rangesApi, RangeVMVisibilityResponse } from '../../services/api'
import { toast } from '../../stores/toastStore'

interface RangeVMVisibilityControlProps {
  rangeId: string
  canManage: boolean
  onUpdate?: () => void
}

export function RangeVMVisibilityControl({
  rangeId,
  canManage,
  onUpdate,
}: RangeVMVisibilityControlProps) {
  const [visibility, setVisibility] = useState<RangeVMVisibilityResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)

  // Track pending changes separately from server state
  const [pendingHiddenIds, setPendingHiddenIds] = useState<string[]>([])
  const [originalHiddenIds, setOriginalHiddenIds] = useState<string[]>([])

  // Check if there are unsaved changes
  const hasChanges = JSON.stringify([...pendingHiddenIds].sort()) !== JSON.stringify([...originalHiddenIds].sort())

  // Load visibility
  const loadVisibility = useCallback(async () => {
    setLoading(true)
    try {
      const response = await rangesApi.getVMVisibility(rangeId)
      setVisibility(response.data)
      setPendingHiddenIds(response.data.hidden_vm_ids || [])
      setOriginalHiddenIds(response.data.hidden_vm_ids || [])
    } catch (error) {
      console.error('Failed to load VM visibility:', error)
      toast.error('Failed to load VM visibility settings')
    } finally {
      setLoading(false)
    }
  }, [rangeId])

  useEffect(() => {
    loadVisibility()
  }, [loadVisibility])

  // Toggle VM visibility (local only, doesn't save)
  const handleToggleVM = (vmId: string) => {
    if (!canManage) return

    const currentlyHidden = pendingHiddenIds.includes(vmId)
    if (currentlyHidden) {
      setPendingHiddenIds(pendingHiddenIds.filter((id) => id !== vmId))
    } else {
      setPendingHiddenIds([...pendingHiddenIds, vmId])
    }
  }

  // Save pending changes
  const handleSave = async () => {
    if (!visibility || !canManage || !hasChanges) return

    setSaving(true)
    try {
      await rangesApi.updateVMVisibility(rangeId, pendingHiddenIds)
      setOriginalHiddenIds(pendingHiddenIds)
      setVisibility({
        ...visibility,
        hidden_vm_ids: pendingHiddenIds,
        vms: visibility.vms.map((vm) => ({
          ...vm,
          is_hidden: pendingHiddenIds.includes(vm.id),
        })),
      })
      toast.success('VM visibility updated')
      onUpdate?.()
    } catch (error) {
      console.error('Failed to update VM visibility:', error)
      toast.error('Failed to update VM visibility')
    } finally {
      setSaving(false)
    }
  }

  // Discard changes
  const handleDiscard = () => {
    setPendingHiddenIds(originalHiddenIds)
  }

  // Quick actions (local only)
  const handleShowAll = () => {
    if (!visibility || !canManage) return
    setPendingHiddenIds([])
  }

  const handleHideAll = () => {
    if (!visibility || !canManage) return
    setPendingHiddenIds(visibility.vms.map((vm) => vm.id))
  }

  // Don't show if no VMs
  if (visibility && visibility.vms.length === 0) {
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
            onClick={loadVisibility}
            disabled={loading || hasChanges}
            className="text-gray-400 hover:text-gray-600 disabled:opacity-50"
            title={hasChanges ? 'Save or discard changes first' : 'Refresh'}
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        )}
      </div>

      <p className="text-xs text-gray-500 mb-4">
        Control which VMs the assigned user can see and access via console
      </p>

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
          <div className="border border-gray-200 rounded-md max-h-64 overflow-y-auto">
            {visibility.vms.map((vm) => {
              const isHidden = pendingHiddenIds.includes(vm.id)
              const wasOriginallyHidden = originalHiddenIds.includes(vm.id)
              const isChanged = isHidden !== wasOriginallyHidden
              return (
                <label
                  key={vm.id}
                  className={`flex items-center px-3 py-2 border-b border-gray-100 last:border-b-0 cursor-pointer ${
                    isChanged ? 'bg-yellow-50' : 'hover:bg-gray-50'
                  } ${!canManage ? 'opacity-75 cursor-not-allowed' : ''}`}
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
                    {isChanged && (
                      <span className="ml-2 text-xs text-yellow-600 font-medium">
                        (unsaved)
                      </span>
                    )}
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

          {/* Action buttons */}
          {canManage && (
            <div className="mt-4 flex flex-wrap gap-2">
              {/* Save/Discard buttons */}
              {hasChanges && (
                <>
                  <button
                    onClick={handleSave}
                    disabled={saving}
                    className="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Save className="h-3 w-3 mr-1" />
                    {saving ? 'Saving...' : 'Save Changes'}
                  </button>
                  <button
                    onClick={handleDiscard}
                    disabled={saving}
                    className="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-md text-gray-700 bg-gray-100 hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Discard
                  </button>
                </>
              )}

              {/* Quick actions */}
              <button
                onClick={handleShowAll}
                disabled={saving || pendingHiddenIds.length === 0}
                className="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-md text-gray-700 bg-gray-100 hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Eye className="h-3 w-3 mr-1" />
                Select All
              </button>
              <button
                onClick={handleHideAll}
                disabled={saving || pendingHiddenIds.length === visibility.vms.length}
                className="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-md text-gray-700 bg-gray-100 hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <EyeOff className="h-3 w-3 mr-1" />
                Deselect All
              </button>
            </div>
          )}

          {/* Visibility summary */}
          <div className="mt-4 text-xs text-gray-500">
            {pendingHiddenIds.length === 0 ? (
              <span className="text-green-600">All {visibility.vms.length} VMs visible</span>
            ) : pendingHiddenIds.length === visibility.vms.length ? (
              <span className="text-red-600">All VMs hidden</span>
            ) : (
              <span>
                {visibility.vms.length - pendingHiddenIds.length} of {visibility.vms.length} VMs visible
              </span>
            )}
            {hasChanges && <span className="ml-2 text-yellow-600">(unsaved changes)</span>}
          </div>
        </>
      )}
    </div>
  )
}
