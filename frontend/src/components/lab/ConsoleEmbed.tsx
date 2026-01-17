// frontend/src/components/lab/ConsoleEmbed.tsx
import { VncConsole } from '../console/VncConsole'
import { Monitor } from 'lucide-react'

interface ConsoleEmbedProps {
  vmId: string | null
  vmHostname: string | null
  token: string
}

export function ConsoleEmbed({ vmId, vmHostname, token }: ConsoleEmbedProps) {
  if (!vmId || !vmHostname) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-900">
        <div className="text-center">
          <Monitor className="w-16 h-16 text-gray-600 mx-auto mb-4" />
          <p className="text-gray-400">Select a VM to view its console</p>
          <p className="text-gray-500 text-sm mt-2">
            Use the VM selector below or click "Open VM" in the walkthrough
          </p>
        </div>
      </div>
    )
  }

  return (
    <VncConsole
      vmId={vmId}
      vmHostname={vmHostname}
      token={token}
      onClose={() => {}}
    />
  )
}
