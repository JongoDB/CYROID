// frontend/src/components/console/VMConsole.tsx
import { useEffect, useRef, useState } from 'react'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'
import { Maximize2, Minimize2, X, RefreshCw } from 'lucide-react'
import clsx from 'clsx'

interface VMConsoleProps {
  vmId: string
  vmHostname: string
  token: string
  onClose: () => void
}

export function VMConsole({ vmId, vmHostname, token, onClose }: VMConsoleProps) {
  const terminalRef = useRef<HTMLDivElement>(null)
  const terminalInstance = useRef<Terminal | null>(null)
  const fitAddon = useRef<FitAddon | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!terminalRef.current) return

    // Initialize terminal
    const terminal = new Terminal({
      cursorBlink: true,
      fontSize: 14,
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
      theme: {
        background: '#1e1e1e',
        foreground: '#d4d4d4',
        cursor: '#d4d4d4',
        selectionBackground: '#264f78',
      },
    })

    const fit = new FitAddon()
    terminal.loadAddon(fit)
    terminal.open(terminalRef.current)
    fit.fit()

    terminalInstance.current = terminal
    fitAddon.current = fit

    // Connect WebSocket
    connectWebSocket(terminal)

    // Handle resize
    const handleResize = () => {
      fit.fit()
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      terminal.dispose()
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [vmId, token])

  const connectWebSocket = (terminal: Terminal) => {
    // Use wss:// for HTTPS, ws:// for HTTP
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = wsProtocol + '//' + window.location.host + '/api/v1/ws/console/' + vmId + '?token=' + token
    const ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      setIsConnected(true)
      setError(null)
      terminal.writeln('Connected to ' + vmHostname)
      terminal.writeln('')
    }

    ws.onmessage = (event) => {
      terminal.write(event.data)
    }

    ws.onerror = () => {
      setError('Connection error')
      terminal.writeln('\r\n\x1b[31mConnection error\x1b[0m')
    }

    ws.onclose = (event) => {
      setIsConnected(false)
      terminal.writeln('\r\n\x1b[33mConnection closed\x1b[0m')
      if (event.reason) {
        setError(event.reason)
      }
    }

    // Send terminal input to WebSocket
    terminal.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(data)
      }
    })

    wsRef.current = ws
  }

  const reconnect = () => {
    if (wsRef.current) {
      wsRef.current.close()
    }
    if (terminalInstance.current) {
      terminalInstance.current.clear()
      connectWebSocket(terminalInstance.current)
    }
  }

  const toggleFullscreen = () => {
    setIsFullscreen(!isFullscreen)
    setTimeout(() => {
      fitAddon.current?.fit()
    }, 100)
  }

  return (
    <div
      className={clsx(
        'flex flex-col bg-gray-900 rounded-lg overflow-hidden shadow-xl',
        isFullscreen ? 'fixed inset-4 z-50' : 'h-full'
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-800 border-b border-gray-700">
        <div className="flex items-center gap-2">
          <div
            className={clsx(
              'w-2 h-2 rounded-full',
              isConnected ? 'bg-green-500' : 'bg-red-500'
            )}
          />
          <span className="text-sm font-medium text-gray-200">
            {vmHostname}
          </span>
          {error && (
            <span className="text-xs text-red-400 ml-2">{error}</span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={reconnect}
            className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded"
            title="Reconnect"
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

      {/* Terminal */}
      <div ref={terminalRef} className="flex-1 p-2" />
    </div>
  )
}
