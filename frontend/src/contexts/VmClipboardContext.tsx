// frontend/src/contexts/VmClipboardContext.tsx
/**
 * Context for sharing clipboard content between walkthrough and VNC console.
 *
 * Due to browser security restrictions, the browser clipboard and KasmVNC's
 * internal clipboard are isolated. This context provides a bridge:
 * 1. When text is copied from the walkthrough, it's stored here
 * 2. The VNC console can then send this text to KasmVNC via postMessage
 */
import { createContext, useContext, useState, useCallback, ReactNode } from 'react'

interface VmClipboardContextType {
  /** The text currently staged for sending to VM */
  clipboardText: string | null
  /** Set text to be sent to VM clipboard */
  setClipboardText: (text: string) => void
  /** Clear the staged clipboard text */
  clearClipboard: () => void
  /** Timestamp of when text was last copied */
  lastCopiedAt: number | null
}

const VmClipboardContext = createContext<VmClipboardContextType | null>(null)

export function VmClipboardProvider({ children }: { children: ReactNode }) {
  const [clipboardText, setClipboardTextState] = useState<string | null>(null)
  const [lastCopiedAt, setLastCopiedAt] = useState<number | null>(null)

  const setClipboardText = useCallback((text: string) => {
    setClipboardTextState(text)
    setLastCopiedAt(Date.now())
  }, [])

  const clearClipboard = useCallback(() => {
    setClipboardTextState(null)
    setLastCopiedAt(null)
  }, [])

  return (
    <VmClipboardContext.Provider
      value={{
        clipboardText,
        setClipboardText,
        clearClipboard,
        lastCopiedAt,
      }}
    >
      {children}
    </VmClipboardContext.Provider>
  )
}

export function useVmClipboard() {
  const context = useContext(VmClipboardContext)
  if (!context) {
    throw new Error('useVmClipboard must be used within a VmClipboardProvider')
  }
  return context
}

// Optional hook that returns null if context is not available
// (for components that may be used outside StudentLab)
export function useVmClipboardOptional() {
  return useContext(VmClipboardContext)
}
