// frontend/src/components/console/VncConsole.tsx
import { useEffect, useState, useRef, useCallback } from 'react'
import { Maximize2, Minimize2, X, RefreshCw, Monitor, AlertTriangle, Clock, Check } from 'lucide-react'
import clsx from 'clsx'
import { useVmClipboardOptional } from '../../contexts'

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

type ConnectionStatus = 'connecting' | 'connected' | 'timeout' | 'error'

const CONNECTION_TIMEOUT_MS = 30000 // 30 seconds

// Clipboard bridge script injected into KasmVNC iframe
// Enables automatic clipboard sync from walkthrough to VM console
const CLIPBOARD_BRIDGE_SCRIPT = `
(function() {
  if (window.__cyroidClipboardBridge) return;
  window.__cyroidClipboardBridge = true;

  // Find and fill KasmVNC's clipboard textarea
  function fillClipboardUI(text) {
    var selectors = [
      '#noVNC_clipboard_text',
      '#clipboard-text',
      'textarea[id*="clipboard"]'
    ];

    for (var i = 0; i < selectors.length; i++) {
      var el = document.querySelector(selectors[i]);
      if (el && el.tagName === 'TEXTAREA') {
        el.value = text;
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        return true;
      }
    }
    return false;
  }

  // Listen for clipboard messages from parent frame
  window.addEventListener('message', function(event) {
    var data = event.data;
    if (!data || typeof data !== 'object') return;

    var text = null;
    if (data.action === 'clipboard' && data.text) {
      text = data.text;
    } else if (data.type === 'clipboard' && data.data) {
      text = data.data;
    }

    if (text) {
      var success = fillClipboardUI(text);

      if (event.source && event.source !== window) {
        event.source.postMessage({
          type: 'clipboard-ack',
          success: success
        }, '*');
      }
    }
  });

  // Notify parent that bridge is ready
  if (window.parent && window.parent !== window) {
    window.parent.postMessage({ type: 'clipboard-bridge-ready' }, '*');
  }
})();
`;

export function VncConsole({ vmId, vmHostname, token, onClose }: VncConsoleProps) {
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [vncInfo, setVncInfo] = useState<VncInfo | null>(null)
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('connecting')
  const [iframeKey, setIframeKey] = useState(0)
  const [showHelp, setShowHelp] = useState(false)
  const [clipboardSynced, setClipboardSynced] = useState(false)
  const [bridgeReady, setBridgeReady] = useState(false)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const lastSyncedRef = useRef<number | null>(null)
  const bridgeInjectedRef = useRef(false)
  const vmClipboard = useVmClipboardOptional()

  useEffect(() => {
    // Fetch VM info to get VNC proxy URL
    const fetchVmInfo = async () => {
      setConnectionStatus('connecting')
      setError(null)
      setBridgeReady(false)
      bridgeInjectedRef.current = false

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
        const origin = window.location.origin

        // Build VNC URL with proper WebSocket path
        const websocketPath = data.websocket_path ?? 'websockify'
        // show_control_bar=true is required for KasmVNC to show sidebar when embedded in iframe
        // resize=remote changes VM resolution to match window (best for dynamic sizing)
        const vncUrl = `${origin}${data.path}/?autoconnect=1&resize=remote&path=${websocketPath}&show_control_bar=true`

        setVncInfo({
          url: vncUrl,
          path: data.path,
          hostname: data.hostname,
          traefik_port: window.location.port ? parseInt(window.location.port) : (window.location.protocol === 'https:' ? 443 : 80),
        })

        // Start connection timeout
        timeoutRef.current = setTimeout(() => {
          setConnectionStatus(prev => prev === 'connecting' ? 'timeout' : prev)
        }, CONNECTION_TIMEOUT_MS)

      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to connect')
        setConnectionStatus('error')
      }
    }

    fetchVmInfo()

    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }
    }
  }, [vmId, token, iframeKey])

  // Listen for messages from iframe (bridge ready, clipboard ack)
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      if (event.data?.type === 'clipboard-bridge-ready') {
        setBridgeReady(true)
      } else if (event.data?.type === 'clipboard-ack') {
        if (event.data.success) {
          setClipboardSynced(true)
          setTimeout(() => setClipboardSynced(false), 2000)
        }
      }
    }

    window.addEventListener('message', handleMessage)
    return () => window.removeEventListener('message', handleMessage)
  }, [])

  // Inject clipboard bridge script into iframe
  const injectClipboardBridge = useCallback(() => {
    if (bridgeInjectedRef.current) return false

    const iframe = iframeRef.current
    if (!iframe) return false

    try {
      // Access iframe's document (only works for same-origin)
      const iframeDoc = iframe.contentDocument || iframe.contentWindow?.document
      if (!iframeDoc) return false

      // Check if already injected
      if (iframeDoc.getElementById('cyroid-clipboard-bridge')) {
        bridgeInjectedRef.current = true
        return true
      }

      // Create and inject script
      const script = iframeDoc.createElement('script')
      script.id = 'cyroid-clipboard-bridge'
      script.textContent = CLIPBOARD_BRIDGE_SCRIPT

      const target = iframeDoc.head || iframeDoc.body || iframeDoc.documentElement
      if (target) {
        target.appendChild(script)
        bridgeInjectedRef.current = true
        return true
      }
    } catch {
      // Cross-origin or other access error - clipboard sync won't work
    }
    return false
  }, [])

  // Handle iframe load event
  const handleIframeLoad = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
    }
    setConnectionStatus('connected')

    // Try to inject clipboard bridge with retries
    // KasmVNC takes time to fully initialize its JS
    const tryInject = () => {
      if (!bridgeInjectedRef.current) {
        injectClipboardBridge()
      }
    }

    // Try at various intervals to catch the right moment
    setTimeout(tryInject, 500)
    setTimeout(tryInject, 1500)
    setTimeout(tryInject, 3000)
    setTimeout(tryInject, 5000)
    setTimeout(tryInject, 8000)
  }, [injectClipboardBridge])

  // Handle iframe error
  const handleIframeError = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
    }
    setConnectionStatus('error')
    setError('Failed to load VNC interface')
  }

  const toggleFullscreen = () => {
    setIsFullscreen(!isFullscreen)
  }

  const reload = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
    }
    setConnectionStatus('connecting')
    setError(null)
    setBridgeReady(false)
    bridgeInjectedRef.current = false
    setIframeKey(prev => prev + 1)
  }

  // Send clipboard to VNC via postMessage
  const sendClipboardToVM = useCallback((text: string) => {
    const iframe = iframeRef.current
    if (!iframe?.contentWindow || !text) return
    iframe.contentWindow.postMessage({ action: 'clipboard', text }, '*')
  }, [])

  // Automatically sync clipboard when content changes
  useEffect(() => {
    if (
      connectionStatus !== 'connected' ||
      !vmClipboard?.clipboardText ||
      !vmClipboard?.lastCopiedAt ||
      vmClipboard.lastCopiedAt === lastSyncedRef.current
    ) {
      return
    }

    sendClipboardToVM(vmClipboard.clipboardText)
    lastSyncedRef.current = vmClipboard.lastCopiedAt

    // Show optimistic feedback - will be confirmed by ack if bridge works
    if (bridgeReady) {
      // Bridge is ready, wait for ack
    } else {
      // Bridge not confirmed, show feedback anyway
      setClipboardSynced(true)
      setTimeout(() => setClipboardSynced(false), 2000)
    }
  }, [connectionStatus, bridgeReady, vmClipboard?.clipboardText, vmClipboard?.lastCopiedAt, sendClipboardToVM])

  const getStatusColor = () => {
    switch (connectionStatus) {
      case 'connected': return 'bg-green-500'
      case 'connecting': return 'bg-yellow-500 animate-pulse'
      case 'timeout': return 'bg-orange-500'
      case 'error': return 'bg-red-500'
    }
  }

  const getStatusText = () => {
    switch (connectionStatus) {
      case 'connected': return bridgeReady ? 'Connected (clipboard ready)' : 'Connected'
      case 'connecting': return 'Connecting...'
      case 'timeout': return 'Connection slow'
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
          <Monitor className="w-4 h-4 text-blue-400" />
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
          {/* Clipboard sync indicator */}
          {clipboardSynced && (
            <div className="px-2 py-1 text-xs rounded bg-green-600 text-white flex items-center gap-1.5">
              <Check className="w-3 h-3" />
              <span>Clipboard synced!</span>
            </div>
          )}
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
          <p className="text-gray-300 font-medium mb-2">Console Help</p>
          <ul className="text-gray-400 space-y-1 text-xs">
            <li>• <strong>Clipboard:</strong> Copy code from walkthrough, then Ctrl+V in VM to paste.</li>
            <li>• <strong>Blank screen?</strong> VM may still be booting. Wait 30-60 seconds and reload.</li>
            <li>• <strong>Connection timeout?</strong> Check if VM is running.</li>
            <li>• <strong>KasmVNC</strong> may take 1-2 minutes to initialize on first boot.</li>
            <li>• Try the <strong>Reload</strong> button if display appears frozen.</li>
          </ul>
        </div>
      )}

      {/* VNC iframe or status display */}
      <div className="flex-1 bg-black relative">
        {/* Loading overlay */}
        {connectionStatus === 'connecting' && (
          <div className="absolute inset-0 flex items-center justify-center z-10 bg-gray-900/80">
            <div className="text-center">
              <div className="animate-spin w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full mx-auto mb-3" />
              <p className="text-gray-300 mb-1">Connecting to {vmHostname}...</p>
              <p className="text-gray-500 text-sm">Establishing VNC connection</p>
            </div>
          </div>
        )}

        {/* Timeout warning overlay */}
        {connectionStatus === 'timeout' && (
          <div className="absolute inset-0 flex items-center justify-center z-10 bg-gray-900/90">
            <div className="text-center max-w-md px-4">
              <Clock className="w-12 h-12 text-orange-400 mx-auto mb-3" />
              <p className="text-orange-400 font-medium mb-2">Connection Taking Longer Than Expected</p>
              <p className="text-gray-400 text-sm mb-4">
                The VNC console is still loading. This can happen if:
              </p>
              <ul className="text-gray-500 text-sm text-left mb-4 space-y-1">
                <li>• The VM is still booting up</li>
                <li>• The VNC service hasn't started yet</li>
                <li>• Network connectivity issues</li>
              </ul>
              <div className="flex gap-3 justify-center">
                <button
                  onClick={() => setConnectionStatus('connected')}
                  className="px-4 py-2 bg-gray-700 text-white rounded hover:bg-gray-600"
                >
                  Keep Waiting
                </button>
                <button
                  onClick={reload}
                  className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                >
                  Retry Connection
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Error state */}
        {connectionStatus === 'error' && (
          <div className="absolute inset-0 flex items-center justify-center z-10">
            <div className="text-center max-w-md px-4">
              <AlertTriangle className="w-12 h-12 text-red-400 mx-auto mb-3" />
              <p className="text-red-400 font-medium mb-2">Console Connection Failed</p>
              <p className="text-gray-400 text-sm mb-2">{error}</p>
              <p className="text-gray-500 text-sm mb-4">
                Make sure the VM is running and has VNC console support.
              </p>
              <div className="flex gap-3 justify-center">
                <button
                  onClick={onClose}
                  className="px-4 py-2 bg-gray-700 text-white rounded hover:bg-gray-600"
                >
                  Close
                </button>
                <button
                  onClick={reload}
                  className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                >
                  Retry
                </button>
              </div>
            </div>
          </div>
        )}

        {/* VNC iframe */}
        {vncInfo && connectionStatus !== 'error' && (
          <iframe
            ref={iframeRef}
            key={iframeKey}
            src={vncInfo.url}
            className="w-full h-full border-0"
            title={`Console: ${vmHostname}`}
            sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
            onLoad={handleIframeLoad}
            onError={handleIframeError}
          />
        )}
      </div>
    </div>
  )
}
