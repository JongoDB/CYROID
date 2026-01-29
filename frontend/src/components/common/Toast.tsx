// frontend/src/components/common/Toast.tsx
/**
 * Toast notification component for displaying real-time feedback.
 * Supports optional action buttons for user interaction.
 */
import { useToastStore, ToastType, ToastAction } from '../../stores/toastStore'
import { X, CheckCircle, AlertCircle, AlertTriangle, Info } from 'lucide-react'
import clsx from 'clsx'

const iconMap: Record<ToastType, React.ReactNode> = {
  success: <CheckCircle className="w-5 h-5 text-green-400" />,
  error: <AlertCircle className="w-5 h-5 text-red-400" />,
  warning: <AlertTriangle className="w-5 h-5 text-yellow-400" />,
  info: <Info className="w-5 h-5 text-blue-400" />,
}

const bgColorMap: Record<ToastType, string> = {
  success: 'bg-green-900/90 border-green-700',
  error: 'bg-red-900/90 border-red-700',
  warning: 'bg-yellow-900/90 border-yellow-700',
  info: 'bg-blue-900/90 border-blue-700',
}

function ActionButton({
  action,
  toastId,
  removeToast,
}: {
  action: ToastAction
  toastId: string
  removeToast: (id: string) => void
}) {
  const handleClick = () => {
    action.onClick()
    removeToast(toastId)
  }

  return (
    <button
      onClick={handleClick}
      className={clsx(
        'px-3 py-1 text-xs font-medium rounded transition-colors',
        action.variant === 'primary'
          ? 'bg-white text-gray-900 hover:bg-gray-100'
          : 'bg-white/20 text-white hover:bg-white/30'
      )}
    >
      {action.label}
    </button>
  )
}

export function ToastContainer() {
  const toasts = useToastStore((state) => state.toasts)
  const removeToast = useToastStore((state) => state.removeToast)

  if (toasts.length === 0) return null

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`
            flex flex-col gap-2 px-4 py-3 rounded-lg border shadow-lg
            animate-slide-in-right
            ${bgColorMap[toast.type]}
          `}
        >
          <div className="flex items-start gap-3">
            <div className="flex-shrink-0 mt-0.5">
              {iconMap[toast.type]}
            </div>
            <p className="text-sm text-white flex-1">{toast.message}</p>
            <button
              onClick={() => removeToast(toast.id)}
              className="flex-shrink-0 text-gray-400 hover:text-white transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          {toast.actions && toast.actions.length > 0 && (
            <div className="flex items-center gap-2 ml-8">
              {toast.actions.map((action, idx) => (
                <ActionButton
                  key={idx}
                  action={action}
                  toastId={toast.id}
                  removeToast={removeToast}
                />
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
