// frontend/src/components/diagnostics/LogViewer.tsx
import { useState, useEffect, useRef } from 'react'
import { X, RefreshCw, Copy, Check, AlertCircle } from 'lucide-react'
import { vmsApi } from '../../services/api'
import type { VMLogsResponse } from '../../types'
import clsx from 'clsx'

interface LogViewerProps {
  vmId: string
  vmHostname: string
  onClose: () => void
}

export function LogViewer({ vmId, vmHostname, onClose }: LogViewerProps) {
  const [logs, setLogs] = useState<VMLogsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const logContainerRef = useRef<HTMLPreElement>(null)

  const fetchLogs = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await vmsApi.getVmLogs(vmId, 100)
      setLogs(data)
      // Auto-scroll to bottom
      setTimeout(() => {
        if (logContainerRef.current) {
          logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight
        }
      }, 100)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch logs')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchLogs()
  }, [vmId])

  const handleCopy = async () => {
    if (logs?.lines) {
      await navigator.clipboard.writeText(logs.lines.join('\n'))
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <div className="border border-gray-200 rounded-lg bg-gray-900 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-800 border-b border-gray-700">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-gray-200">
            Logs: {vmHostname}
          </span>
          {logs?.container_id && (
            <span className="text-xs text-gray-500">
              ({logs.container_id})
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={fetchLogs}
            disabled={loading}
            className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded disabled:opacity-50"
            title="Refresh"
          >
            <RefreshCw className={clsx("w-4 h-4", loading && "animate-spin")} />
          </button>
          <button
            onClick={handleCopy}
            disabled={!logs?.lines?.length}
            className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded disabled:opacity-50"
            title="Copy to clipboard"
          >
            {copied ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
          </button>
          <button
            onClick={onClose}
            className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded"
            title="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Log content */}
      <div className="relative">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-900/80 z-10">
            <RefreshCw className="w-6 h-6 text-gray-400 animate-spin" />
          </div>
        )}

        {error && (
          <div className="p-4 flex items-center gap-2 text-red-400">
            <AlertCircle className="w-4 h-4" />
            <span className="text-sm">{error}</span>
          </div>
        )}

        <pre
          ref={logContainerRef}
          className="p-4 text-xs font-mono text-gray-300 overflow-auto max-h-64 whitespace-pre-wrap"
        >
          {logs?.lines?.length ? (
            logs.lines.map((line, i) => (
              <div key={i} className="hover:bg-gray-800">
                {line}
              </div>
            ))
          ) : !loading && !error ? (
            <span className="text-gray-500">No logs available</span>
          ) : null}
        </pre>

        {/* Note about QEMU/Windows VMs */}
        {logs?.note && (
          <div className="px-4 py-2 bg-gray-800/50 border-t border-gray-700 text-xs text-gray-500">
            {logs.note}
          </div>
        )}
      </div>
    </div>
  )
}
