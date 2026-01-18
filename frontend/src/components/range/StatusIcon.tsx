// frontend/src/components/range/StatusIcon.tsx
import { CheckCircle, XCircle, Loader2, Circle } from 'lucide-react'
import clsx from 'clsx'

interface Props {
  status: string
  className?: string
}

export function StatusIcon({ status, className }: Props) {
  const baseClass = clsx('w-5 h-5', className)

  switch (status) {
    case 'running':
    case 'created':
      return <CheckCircle className={clsx(baseClass, 'text-green-500')} />
    case 'creating':
    case 'starting':
      return <Loader2 className={clsx(baseClass, 'text-blue-500 animate-spin')} />
    case 'failed':
      return <XCircle className={clsx(baseClass, 'text-red-500')} />
    case 'pending':
    default:
      return <Circle className={clsx(baseClass, 'text-gray-400')} />
  }
}
