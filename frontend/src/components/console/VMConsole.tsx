// frontend/src/components/console/VMConsole.tsx
import { useEffect, useRef, useState } from 'react'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'
import { Maximize2, Minimize2, X, RefreshCw, Terminal as TerminalIcon, AlertTriangle } from 'lucide-react'
import clsx from 'clsx'

interface VMConsoleProps {
  vmId: string
  vmHostname: string
  token: string
  onClose: () => void
}

type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

const CONNECTION_TIMEOUT_MS = 15000 // 15 seconds

export function VMConsole({ vmId, vmHostname, token, onClose }: VMConsoleProps) {
  const terminalRef = useRef<HTMLDivElement>(null)
  const terminalInstance = useRef<Terminal | null>(null)
  const fitAddon = useRef<FitAddon | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('connecting')
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showHelp, setShowHelp] = useState(false)
  const [reconnectCount, setReconnectCount] = useState(0)

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
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }
    }
  }, [vmId, token, reconnectCount])

  const connectWebSocket = (terminal: Terminal) => {
    setConnectionStatus('connecting')
    setError(null)

    // Start connection timeout
    timeoutRef.current = setTimeout(() => {
      if (connectionStatus === 'connecting') {
        setConnectionStatus('error')
        setError('Connection timeout - VM may not support terminal console')
        terminal.writeln('\r\n\x1b[31mConnection timeout\x1b[0m')
        terminal.writeln('\x1b[33mThis VM may not support terminal console access.\x1b[0m')
        terminal.writeln('\x1b[33mTry using VNC console if available.\x1b[0m')
      }
    }, CONNECTION_TIMEOUT_MS)

    // Use wss:// for HTTPS, ws:// for HTTP
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = wsProtocol + '//' + window.location.host + '/api/v1/ws/console/' + vmId + '?token=' + token

    terminal.writeln('\x1b[90mConnecting to ' + vmHostname + '...\x1b[0m')

    const ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }
      setConnectionStatus('connected')
      setError(null)
      terminal.writeln('\x1b[32mConnected to ' + vmHostname + '\x1b[0m')
      terminal.writeln('')
    }

    ws.onmessage = (event) => {
      terminal.write(event.data)
    }

    ws.onerror = () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }
      setConnectionStatus('error')
      setError('WebSocket connection failed')
      terminal.writeln('\r\n\x1b[31mConnection error\x1b[0m')
      terminal.writeln('\x1b[33mPossible causes:\x1b[0m')
      terminal.writeln('\x1b[33m  - VM is not running\x1b[0m')
      terminal.writeln('\x1b[33m  - Container does not have a TTY\x1b[0m')
      terminal.writeln('\x1b[33m  - Network connectivity issue\x1b[0m')
    }

    ws.onclose = (event) => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }
      setConnectionStatus('disconnected')
      terminal.writeln('\r\n\x1b[33mConnection closed\x1b[0m')
      if (event.reason) {
        setError(event.reason)
        terminal.writeln('\x1b[90mReason: ' + event.reason + '\x1b[0m')
      }
      if (event.code !== 1000) {
        terminal.writeln('\x1b[90mCode: ' + event.code + '\x1b[0m')
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
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
    }
    if (terminalInstance.current) {
      terminalInstance.current.clear()
    }
    setReconnectCount(prev => prev + 1)
  }

  const toggleFullscreen = () => {
    setIsFullscreen(!isFullscreen)
    setTimeout(() => {
      fitAddon.current?.fit()
    }, 100)
  }

  const getStatusColor = () => {
    switch (connectionStatus) {
      case 'connected': return 'bg-green-500'
      case 'connecting': return 'bg-yellow-500 animate-pulse'
      case 'disconnected': return 'bg-gray-500'
      case 'error': return 'bg-red-500'
    }
  }

  const getStatusText = () => {
    switch (connectionStatus) {
      case 'connected': return 'Connected'
      case 'connecting': return 'Connecting...'
      case 'disconnected': return 'Disconnected'
      case 'error': return 'Error'
    }
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
          <TerminalIcon className="w-4 h-4 text-green-400" />
          <div className={clsx('w-2 h-2 rounded-full', getStatusColor())} />
          <span className="text-sm font-medium text-gray-200">
            {vmHostname}
          </span>
          <span className="text-xs text-gray-400">
            {getStatusText()}
          </span>
          {error && (
            <span className="text-xs text-red-400 ml-2">{error}</span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setShowHelp(!showHelp)}
            className={clsx(
              "p-1.5 hover:bg-gray-700 rounded",
              showHelp ? "text-blue-400" : "text-gray-400 hover:text-white"
            )}
            title="Help"
          >
            <AlertTriangle className="w-4 h-4" />
          </button>
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
            {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
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

      {/* Help panel */}
      {showHelp && (
        <div className="px-4 py-3 bg-gray-800/50 border-b border-gray-700 text-sm">
          <p className="text-gray-300 font-medium mb-2">Troubleshooting Terminal Console</p>
          <ul className="text-gray-400 space-y-1 text-xs">
            <li>• <strong>Connection failed?</strong> The VM must be running and have a TTY available.</li>
            <li>• <strong>Linux containers</strong> support terminal console via docker exec.</li>
            <li>• <strong>KasmVNC/Windows VMs</strong> use VNC console instead of terminal.</li>
            <li>• <strong>No output?</strong> Try pressing Enter or running a command like `ls`.</li>
            <li>• Use the <strong>Reconnect</strong> button if connection is lost.</li>
          </ul>
        </div>
      )}

      {/* Terminal */}
      <div ref={terminalRef} className="flex-1 p-2" />
    </div>
  )
}
