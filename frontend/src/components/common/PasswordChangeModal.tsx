// frontend/src/components/common/PasswordChangeModal.tsx
import { useState, FormEvent } from 'react'
import { useAuthStore } from '../../stores/authStore'

interface PasswordChangeModalProps {
  isOpen: boolean
  onClose: () => void
  isForced?: boolean // If true, user cannot dismiss the modal
}

export default function PasswordChangeModal({ isOpen, onClose, isForced = false }: PasswordChangeModalProps) {
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [localError, setLocalError] = useState<string | null>(null)
  const { changePassword, isLoading, error, clearError } = useAuthStore()

  if (!isOpen) return null

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setLocalError(null)

    // Validate passwords match
    if (newPassword !== confirmPassword) {
      setLocalError('New passwords do not match')
      return
    }

    // Validate password length
    if (newPassword.length < 8) {
      setLocalError('New password must be at least 8 characters')
      return
    }

    try {
      await changePassword({ current_password: currentPassword, new_password: newPassword })
      // Reset form
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      onClose()
    } catch {
      // Error handled by store
    }
  }

  const displayError = localError || error

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-screen items-center justify-center px-4 py-12">
        {/* Backdrop */}
        <div
          className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity"
          onClick={isForced ? undefined : onClose}
        />

        {/* Modal */}
        <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full p-6">
          <div className="mb-6">
            <h3 className="text-lg font-semibold text-gray-900">
              {isForced ? 'Password Reset Required' : 'Change Password'}
            </h3>
            {isForced && (
              <p className="mt-2 text-sm text-amber-600">
                An administrator has required you to change your password before continuing.
              </p>
            )}
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {displayError && (
              <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded relative">
                {displayError}
                <button
                  type="button"
                  className="absolute top-0 right-0 p-4"
                  onClick={() => {
                    setLocalError(null)
                    clearError()
                  }}
                >
                  &times;
                </button>
              </div>
            )}

            <div>
              <label htmlFor="current-password" className="block text-sm font-medium text-gray-700">
                Current Password
              </label>
              <input
                id="current-password"
                type="password"
                required
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
              />
            </div>

            <div>
              <label htmlFor="new-password" className="block text-sm font-medium text-gray-700">
                New Password
              </label>
              <input
                id="new-password"
                type="password"
                required
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
              />
            </div>

            <div>
              <label htmlFor="confirm-password" className="block text-sm font-medium text-gray-700">
                Confirm New Password
              </label>
              <input
                id="confirm-password"
                type="password"
                required
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
              />
            </div>

            <div className="flex justify-end space-x-3 pt-4">
              {!isForced && (
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
                >
                  Cancel
                </button>
              )}
              <button
                type="submit"
                disabled={isLoading}
                className="px-4 py-2 text-sm font-medium text-white bg-primary-600 border border-transparent rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoading ? 'Changing...' : 'Change Password'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
