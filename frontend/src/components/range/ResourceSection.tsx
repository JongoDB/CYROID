// frontend/src/components/range/ResourceSection.tsx
import { ReactNode } from 'react'

interface Props {
  title: string
  completed: number
  total: number
  children: ReactNode
}

export function ResourceSection({ title, completed, total, children }: Props) {
  const isComplete = completed === total && total > 0
  const hasFailures = completed < total && total > 0

  return (
    <div className="border-b border-gray-700 last:border-b-0">
      <div className="flex items-center justify-between px-4 py-2 bg-gray-800">
        <span className="text-sm font-medium text-gray-300 uppercase tracking-wide">
          {title}
        </span>
        <span className={
          isComplete ? 'text-green-400 text-sm' :
          hasFailures ? 'text-yellow-400 text-sm' :
          'text-gray-400 text-sm'
        }>
          {completed}/{total}
        </span>
      </div>
      <div className="bg-gray-900">
        {children}
      </div>
    </div>
  )
}
