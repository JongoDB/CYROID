// frontend/src/components/console/VncConsole.tsx
import { useEffect, useState } from 'react'
import { Maximize2, Minimize2, X, RefreshCw, Monitor, ExternalLink } from 'lucide-react'
import clsx from 'clsx'

interface VncConsoleProps {
  vmId: string
  vmHostname: string
  token: string
  onClose: () => void
}

interface VncInfo {
  url: string
  path: string
  hostname: string
  traefik_port: number
}

export function VncConsole({ vmId, vmHostname, token, onClose }: VncConsoleProps) {
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [vncInfo, setVncInfo] = useState<VncInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [iframeKey, setIframeKey] = useState(0)

  useEffect(() => {
    // Fetch VM info to get VNC proxy URL
    const fetchVmInfo = async () => {
      try {
        const response = await fetch(`/api/v1/vms/${vmId}/vnc-info`, {
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        })

        if (!response.ok) {
          const data = await response.json().catch(() => ({}))
          throw new Error(data.detail || 'Failed to get VNC info')
        }

        const data = await response.json()
        // Build URL using browser's hostname (not the Docker internal hostname)
        const browserHostname = window.location.hostname
        const traefikPort = data.traefik_port || 80

        // Build VNC URL with proper WebSocket path for KasmVNC
        // The 'path' parameter tells the client where to connect for WebSocket
        // We need to include the full path so WebSocket connects to the correct proxied endpoint
        const wsPath = `${data.path}/`.replace(/^\//, '') // Remove leading slash for path param
        const vncUrl = `http://${browserHostname}:${traefikPort}${data.path}/?autoconnect=1&resize=scale&path=${wsPath}`

        setVncInfo({
          url: vncUrl,
          path: data.path,
          hostname: data.hostname,
          traefik_port: traefikPort,
        })
        setLoading(false)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to connect')
        setLoading(false)
      }
    }

    fetchVmInfo()
  }, [vmId, token])

  const toggleFullscreen = () => {
    setIsFullscreen(!isFullscreen)
  }

  const openInNewTab = () => {
    if (vncInfo) {
      window.open(vncInfo.url, '_blank')
    }
  }

  const reload = () => {
    setLoading(true)
    setError(null)
    // Force iframe reload by incrementing key
    setIframeKey(prev => prev + 1)
    setLoading(false)
  }

  return (
    <div
      className={clsx(
        'flex flex-col bg-gray-900 rounded-lg overflow-hidden shadow-xl',
        isFullscreen ? 'fixed inset-4 z-50' : 'h-[600px]'
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-800 border-b border-gray-700">
        <div className="flex items-center gap-2">
          <Monitor className="w-4 h-4 text-blue-400" />
          <div
            className={clsx(
              'w-2 h-2 rounded-full',
              vncInfo && !error ? 'bg-green-500' : error ? 'bg-red-500' : 'bg-yellow-500'
            )}
          />
          <span className="text-sm font-medium text-gray-200">
            {vmHostname}
          </span>
          <span className="text-xs text-gray-400">
            {loading ? 'Loading...' : error ? 'Error' : 'Connected via Traefik'}
          </span>
          {error && (
            <span className="text-xs text-red-400 ml-2">{error}</span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {vncInfo && (
            <button
              onClick={openInNewTab}
              className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded"
              title="Open in new tab"
            >
              <ExternalLink className="w-4 h-4" />
            </button>
          )}
          <button
            onClick={reload}
            className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded"
            title="Reload"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          <button
            onClick={toggleFullscreen}
            className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded"
            title={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
          >
            {isFullscreen ? (
              <Minimize2 className="w-4 h-4" />
            ) : (
              <Maximize2 className="w-4 h-4" />
            )}
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

      {/* VNC iframe or loading/error state */}
      <div className="flex-1 bg-black relative">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center">
              <div className="animate-spin w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full mx-auto mb-2" />
              <p className="text-gray-400">Connecting to console...</p>
            </div>
          </div>
        )}

        {error && !loading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center max-w-md px-4">
              <p className="text-red-400 mb-2">{error}</p>
              <p className="text-gray-500 text-sm mb-4">
                Make sure the VM is running and traefik is properly configured.
              </p>
              <button
                onClick={reload}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
              >
                Retry
              </button>
            </div>
          </div>
        )}

        {vncInfo && !error && (
          <iframe
            key={iframeKey}
            src={vncInfo.url}
            className="w-full h-full border-0"
            title={`Console: ${vmHostname}`}
            sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
          />
        )}
      </div>
    </div>
  )
}
