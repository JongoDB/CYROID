// frontend/src/pages/ExecutionConsole.tsx
import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Range, VM, MSEL } from '../types'
import { rangesApi, vmsApi, mselApi } from '../services/api'
import { VMGrid } from '../components/execution/VMGrid'
import { EventLogComponent } from '../components/execution/EventLog'
import { VMConsole } from '../components/console/VMConsole'
import { MSELUpload } from '../components/execution/MSELUpload'
import { InjectTimeline } from '../components/execution/InjectTimeline'
import { ConnectionMonitor } from '../components/execution/ConnectionMonitor'
import { Activity, Server, ArrowLeft, X, FileText } from 'lucide-react'
import clsx from 'clsx'

type RightPanelTab = 'events' | 'injects' | 'connections'

export default function ExecutionConsole() {
  const { rangeId } = useParams<{ rangeId: string }>()
  const navigate = useNavigate()
  const [range, setRange] = useState<Range | null>(null)
  const [vms, setVMs] = useState<VM[]>([])
  const [msel, setMSEL] = useState<MSEL | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedVM, setSelectedVM] = useState<{ id: string; hostname: string } | null>(null)
  const [rightPanelTab, setRightPanelTab] = useState<RightPanelTab>('events')

  useEffect(() => {
    if (rangeId) {
      loadRangeData()
      loadMSEL()
      const interval = setInterval(loadRangeData, 10000)
      return () => clearInterval(interval)
    }
  }, [rangeId])

  const loadRangeData = async () => {
    if (!rangeId) return
    try {
      const [rangeData, vmsData] = await Promise.all([
        rangesApi.get(rangeId),
        vmsApi.list(rangeId),
      ])
      setRange(rangeData.data)
      setVMs(vmsData.data)
    } catch (error) {
      console.error('Failed to load range data:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadMSEL = async () => {
    if (!rangeId) return
    try {
      const response = await mselApi.get(rangeId)
      setMSEL(response.data)
    } catch {
      // No MSEL exists yet, that's okay
      setMSEL(null)
    }
  }

  const handleMSELLoaded = (newMSEL: MSEL) => {
    setMSEL(newMSEL)
    setRightPanelTab('injects')
  }

  const handleOpenConsole = (vmId: string, hostname: string) => {
    setSelectedVM({ id: vmId, hostname })
  }

  const handleCloseConsole = () => {
    setSelectedVM(null)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
      </div>
    )
  }

  if (!range || !rangeId) {
    return <div className="text-center py-8">Range not found</div>
  }

  const runningVMs = vms.filter(vm => vm.status === 'running').length

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="bg-white border-b px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate(`/ranges/${rangeId}`)}
              className="p-2 hover:bg-gray-100 rounded"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-xl font-semibold">{range.name}</h1>
              <p className="text-sm text-gray-500">{range.description}</p>
            </div>
          </div>
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <Server className="w-5 h-5 text-gray-400" />
              <span className="text-sm">
                <span className="font-medium">{runningVMs}</span>
                <span className="text-gray-500">/{vms.length} VMs</span>
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Activity className={clsx('w-5 h-5', range.status === 'running' ? 'text-green-500' : 'text-gray-400')} />
              <span className="text-sm capitalize">{range.status}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Panel - VM Grid */}
        <div className="flex-1 p-6 overflow-y-auto">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-medium">Virtual Machines</h2>
            <MSELUpload rangeId={rangeId} onMSELLoaded={handleMSELLoaded} />
          </div>
          <VMGrid
            vms={vms}
            onRefresh={loadRangeData}
            onOpenConsole={handleOpenConsole}
          />

          {/* Connection Monitor - Below VM Grid */}
          <div className="mt-6">
            <ConnectionMonitor rangeId={rangeId} vms={vms} />
          </div>
        </div>

        {/* Right Panel - Tabbed View */}
        <div className="w-[420px] border-l bg-gray-50 flex flex-col">
          {/* Tabs */}
          <div className="flex border-b bg-white">
            <button
              onClick={() => setRightPanelTab('events')}
              className={clsx(
                'flex-1 flex items-center justify-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition',
                rightPanelTab === 'events'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              )}
            >
              <Activity className="w-4 h-4" />
              Events
            </button>
            <button
              onClick={() => setRightPanelTab('injects')}
              className={clsx(
                'flex-1 flex items-center justify-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition',
                rightPanelTab === 'injects'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              )}
            >
              <FileText className="w-4 h-4" />
              Injects
              {msel && (
                <span className="ml-1 px-1.5 py-0.5 text-xs bg-gray-200 rounded">
                  {msel.injects.filter(i => i.status === 'pending').length}
                </span>
              )}
            </button>
          </div>

          {/* Tab Content */}
          <div className="flex-1 overflow-y-auto p-4">
            {rightPanelTab === 'events' && (
              <EventLogComponent rangeId={rangeId} maxHeight="calc(100vh - 280px)" />
            )}
            {rightPanelTab === 'injects' && (
              msel ? (
                <InjectTimeline msel={msel} onInjectUpdate={loadMSEL} />
              ) : (
                <div className="text-center py-8 text-gray-500">
                  <FileText className="w-12 h-12 mx-auto mb-3 opacity-50" />
                  <p className="text-sm">No MSEL loaded</p>
                  <p className="text-xs mt-1">Use the "Import MSEL" button above to load a scenario</p>
                </div>
              )
            )}
          </div>
        </div>
      </div>

      {/* Console Modal */}
      {selectedVM && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-4/5 h-4/5 flex flex-col">
            <div className="flex items-center justify-between px-4 py-2 border-b">
              <h3 className="font-medium">VM Console - {selectedVM.hostname}</h3>
              <button
                onClick={handleCloseConsole}
                className="p-1 hover:bg-gray-100 rounded"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="flex-1">
              <VMConsole
                vmId={selectedVM.id}
                vmHostname={selectedVM.hostname}
                token={localStorage.getItem('token') || ''}
                onClose={handleCloseConsole}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
