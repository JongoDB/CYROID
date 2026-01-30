import { useState } from 'react'
import { Camera, Loader2, AlertCircle } from 'lucide-react'
import { Modal, ModalBody, ModalFooter } from '../common/Modal'
import { snapshotsApi } from '../../services/api'
import { toast } from '../../stores/toastStore'

interface Props {
  vmId: string
  hostname: string
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
}

export function CreateSnapshotModal({ vmId, hostname, isOpen, onClose, onSuccess }: Props) {
  // Auto-generate default name with hostname and date
  const defaultName = `${hostname}-${new Date().toISOString().split('T')[0]}`

  const [name, setName] = useState(defaultName)
  const [description, setDescription] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleCreate = async () => {
    if (!name.trim()) {
      setError('Snapshot name is required')
      return
    }

    setLoading(true)
    setError(null)

    try {
      await snapshotsApi.create({
        vm_id: vmId,
        name: name.trim(),
        description: description.trim() || undefined,
      })

      toast.success(`Snapshot "${name}" created successfully`)
      onSuccess()
      onClose()
    } catch (err: any) {
      const message = err.response?.data?.detail || 'Failed to create snapshot'
      setError(message)
      toast.error(message)
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !loading) {
      handleCreate()
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Create Snapshot"
      description={`Create a snapshot of ${hostname} that can be restored later`}
      size="md"
    >
      <ModalBody className="space-y-4">
        <p className="text-sm text-gray-600">
          Create a snapshot of <span className="font-medium text-gray-900">{hostname}</span> that can be restored later.
        </p>

        {/* Error message */}
        {error && (
          <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Name input */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Snapshot Name <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="e.g., kali-configured-2026-01-17"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            disabled={loading}
            autoFocus
          />
          <p className="mt-1 text-xs text-gray-500">
            Use a descriptive name to identify this snapshot later.
          </p>
        </div>

        {/* Description input */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Description <span className="text-gray-400">(optional)</span>
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="e.g., Kali with all tools installed and configured for AD testing"
            rows={3}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 resize-none"
            disabled={loading}
          />
        </div>

        {/* Info box */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-3">
          <p className="text-sm text-blue-800">
            Snapshots capture the current state of the VM including all installed software and configurations.
            View and restore snapshots from the Image Cache page.
          </p>
        </div>
      </ModalBody>

      <ModalFooter>
        <button
          onClick={onClose}
          disabled={loading}
          className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
        >
          Cancel
        </button>
        <button
          onClick={handleCreate}
          disabled={loading || !name.trim()}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Creating...
            </>
          ) : (
            <>
              <Camera className="w-4 h-4" />
              Create Snapshot
            </>
          )}
        </button>
      </ModalFooter>
    </Modal>
  )
}
