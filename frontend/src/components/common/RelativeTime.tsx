import { useMemo } from 'react'

interface Props {
  date: string | null
  prefix?: string
}

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSecs = Math.floor(diffMs / 1000)
  const diffMins = Math.floor(diffSecs / 60)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffSecs < 60) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString()
}

export function RelativeTime({ date, prefix }: Props) {
  const formatted = useMemo(() => {
    if (!date) return null
    return formatRelativeTime(date)
  }, [date])

  if (!formatted) return null

  const fullDate = new Date(date!).toLocaleString()

  return (
    <span title={fullDate} className="cursor-help">
      {prefix}{formatted}
    </span>
  )
}
