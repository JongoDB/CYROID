// frontend/src/pages/StandaloneConsole.tsx
import { useEffect, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { VMConsole } from '../components/console/VMConsole'
import { VncConsole } from '../components/console/VncConsole'
import { vmsApi } from '../services/api'
import { VM } from '../types'

type ConsoleType = 'terminal' | 'vnc'

export default function StandaloneConsole() {
  const { vmId } = useParams<{ vmId: string }>()
  const [searchParams] = useSearchParams()
  const [vm, setVM] = useState<VM | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Allow override via query param, otherwise auto-detect
  const consoleTypeParam = searchParams.get('type') as ConsoleType | null
  const [consoleType, setConsoleType] = useState<ConsoleType>(consoleTypeParam || 'terminal')

  const token = localStorage.getItem('token') || ''

  useEffect(() => {
    if (!vmId) {
      setError('No VM ID provided')
      setLoading(false)
      return
    }

    if (!token) {
      setError('Not authenticated')
      setLoading(false)
      return
    }

    // Fetch VM info and check if VNC is available
    const loadVM = async () => {
      try {
        const vmRes = await vmsApi.get(vmId)
        setVM(vmRes.data)

        // Auto-detect console type by checking if VNC is available
        if (!consoleTypeParam) {
          try {
            // Try to get VNC info - if it succeeds, this VM supports VNC
            const vncRes = await fetch(`/api/v1/vms/${vmId}/vnc-info`, {
              headers: { 'Authorization': `Bearer ${token}` }
            })
            if (vncRes.ok) {
              setConsoleType('vnc')
            } else {
              setConsoleType('terminal')
            }
          } catch {
            // VNC not available, use terminal
            setConsoleType('terminal')
          }
        }
        setLoading(false)
      } catch (err: unknown) {
        const error = err as { response?: { data?: { detail?: string } } }
        setError(error.response?.data?.detail || 'Failed to load VM')
        setLoading(false)
      }
    }

    loadVM()
  }, [vmId, token, consoleTypeParam])

  // Update document title
  useEffect(() => {
    if (vm) {
      document.title = `Console: ${vm.hostname} - CYROID`
    }
    return () => {
      document.title = 'CYROID'
    }
  }, [vm])

  const handleClose = () => {
    window.close()
  }

  if (loading) {
    return (
      <div className="h-screen w-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full mx-auto mb-2" />
          <p className="text-gray-400">Loading console...</p>
        </div>
      </div>
    )
  }

  if (error || !vm || !vmId) {
    return (
      <div className="h-screen w-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center max-w-md px-4">
          <p className="text-red-400 mb-2">{error || 'VM not found'}</p>
          <button
            onClick={handleClose}
            className="px-4 py-2 bg-gray-700 text-white rounded hover:bg-gray-600"
          >
            Close Window
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="h-screen w-screen bg-gray-900">
      {consoleType === 'vnc' ? (
        <VncConsole
          vmId={vmId}
          vmHostname={vm.hostname}
          token={token}
          onClose={handleClose}
        />
      ) : (
        <VMConsole
          vmId={vmId}
          vmHostname={vm.hostname}
          token={token}
          onClose={handleClose}
        />
      )}
    </div>
  )
}
