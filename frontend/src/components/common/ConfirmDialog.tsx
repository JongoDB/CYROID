// frontend/src/components/common/ConfirmDialog.tsx
import { AlertTriangle, Trash2, X } from 'lucide-react'
import clsx from 'clsx'

export interface ConfirmDialogProps {
  isOpen: boolean
  title: string
  message: string
  confirmLabel?: string
  cancelLabel?: string
  variant?: 'danger' | 'warning' | 'info'
  onConfirm: () => void
  onCancel: () => void
  isLoading?: boolean
}

export function ConfirmDialog({
  isOpen,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'danger',
  onConfirm,
  onCancel,
  isLoading = false
}: ConfirmDialogProps) {
  if (!isOpen) return null

  const iconColors = {
    danger: 'bg-red-100 text-red-600',
    warning: 'bg-yellow-100 text-yellow-600',
    info: 'bg-blue-100 text-blue-600'
  }

  const buttonColors = {
    danger: 'bg-red-600 hover:bg-red-700 focus:ring-red-500',
    warning: 'bg-yellow-600 hover:bg-yellow-700 focus:ring-yellow-500',
    info: 'bg-blue-600 hover:bg-blue-700 focus:ring-blue-500'
  }

  const Icon = variant === 'danger' ? Trash2 : AlertTriangle

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-screen items-center justify-center px-4 py-12">
        {/* Backdrop */}
        <div
          className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity"
          onClick={onCancel}
        />

        {/* Modal */}
        <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full">
          {/* Close button */}
          <button
            onClick={onCancel}
            className="absolute top-4 right-4 text-gray-400 hover:text-gray-500"
          >
            <X className="h-5 w-5" />
          </button>

          <div className="p-6">
            {/* Icon and content */}
            <div className="flex items-start gap-4">
              <div className={clsx(
                "flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center",
                iconColors[variant]
              )}>
                <Icon className="h-5 w-5" />
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-gray-900">
                  {title}
                </h3>
                <p className="mt-2 text-sm text-gray-500">
                  {message}
                </p>
              </div>
            </div>

            {/* Actions */}
            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                onClick={onCancel}
                disabled={isLoading}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500 disabled:opacity-50"
              >
                {cancelLabel}
              </button>
              <button
                type="button"
                onClick={onConfirm}
                disabled={isLoading}
                className={clsx(
                  "px-4 py-2 text-sm font-medium text-white border border-transparent rounded-md focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50",
                  buttonColors[variant]
                )}
              >
                {isLoading ? 'Please wait...' : confirmLabel}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// Hook for easier usage with async operations
import { useState, useCallback } from 'react'

interface UseConfirmDialogOptions {
  title: string
  message: string
  confirmLabel?: string
  variant?: 'danger' | 'warning' | 'info'
}

interface ConfirmState {
  isOpen: boolean
  options: UseConfirmDialogOptions
  onConfirm: (() => void) | null
}

export function useConfirmDialog() {
  const [state, setState] = useState<ConfirmState>({
    isOpen: false,
    options: { title: '', message: '' },
    onConfirm: null
  })
  const [isLoading, setIsLoading] = useState(false)

  const confirm = useCallback((options: UseConfirmDialogOptions): Promise<boolean> => {
    return new Promise((resolve) => {
      setState({
        isOpen: true,
        options,
        onConfirm: () => resolve(true)
      })
    })
  }, [])

  const handleConfirm = useCallback(async () => {
    if (state.onConfirm) {
      setIsLoading(true)
      try {
        state.onConfirm()
      } finally {
        setIsLoading(false)
        setState(prev => ({ ...prev, isOpen: false, onConfirm: null }))
      }
    }
  }, [state.onConfirm])

  const handleCancel = useCallback(() => {
    setState(prev => ({ ...prev, isOpen: false, onConfirm: null }))
  }, [])

  const dialogProps: ConfirmDialogProps = {
    isOpen: state.isOpen,
    title: state.options.title,
    message: state.options.message,
    confirmLabel: state.options.confirmLabel || 'Delete',
    variant: state.options.variant || 'danger',
    onConfirm: handleConfirm,
    onCancel: handleCancel,
    isLoading
  }

  return { confirm, dialogProps, ConfirmDialog }
}
