// frontend/src/pages/StudentLab.tsx
import { useEffect, useState, useCallback, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { BookOpen, Loader2, AlertCircle, ChevronRight, GripVertical } from 'lucide-react'
import { rangesApi, vmsApi, walkthroughApi } from '../services/api'
import { Range, VM, Walkthrough } from '../types'
import { WalkthroughPanel } from '../components/walkthrough'
import { VMSelector, ConsoleEmbed } from '../components/lab'

export default function StudentLab() {
  const { rangeId } = useParams<{ rangeId: string }>()
  const [range, setRange] = useState<Range | null>(null)
  const [vms, setVMs] = useState<VM[]>([])
  const [walkthrough, setWalkthrough] = useState<Walkthrough | null>(null)
  const [selectedVmId, setSelectedVmId] = useState<string | null>(null)
  const [isCollapsed, setIsCollapsed] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Panel width state (percentage) - default 40% walkthrough, 60% console
  const [walkthroughWidth, setWalkthroughWidth] = useState(() => {
    const saved = localStorage.getItem('student-lab-width')
    return saved ? parseInt(saved, 10) : 40
  })
  const [isDragging, setIsDragging] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  const token = localStorage.getItem('token') || ''
  const selectedVm = vms.find(vm => vm.id === selectedVmId) || null

  useEffect(() => {
    if (!rangeId) {
      setError('No range ID provided')
      setLoading(false)
      return
    }

    const loadData = async () => {
      try {
        const [rangeRes, vmsRes, walkthroughRes] = await Promise.all([
          rangesApi.get(rangeId),
          vmsApi.list(rangeId),
          walkthroughApi.get(rangeId),
        ])

        setRange(rangeRes.data)
        setVMs(vmsRes.data)
        setWalkthrough(walkthroughRes.data.walkthrough)

        // Auto-select first running VM
        const runningVm = vmsRes.data.find(vm => vm.status === 'running')
        if (runningVm) {
          setSelectedVmId(runningVm.id)
        }

        setLoading(false)
      } catch (err: unknown) {
        const error = err as { response?: { data?: { detail?: string } } }
        setError(error.response?.data?.detail || 'Failed to load lab')
        setLoading(false)
      }
    }

    loadData()
  }, [rangeId])

  // Update document title
  useEffect(() => {
    if (range) {
      document.title = `Lab: ${range.name} - CYROID`
    }
    return () => {
      document.title = 'CYROID'
    }
  }, [range])

  const handleOpenVM = (vmHostname: string) => {
    const vm = vms.find(v => v.hostname === vmHostname)
    if (vm) {
      setSelectedVmId(vm.id)
    }
  }

  // Handle drag to resize
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  useEffect(() => {
    if (!isDragging) return

    const handleMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return
      const containerRect = containerRef.current.getBoundingClientRect()
      const newWidth = ((e.clientX - containerRect.left) / containerRect.width) * 100
      // Clamp between 20% and 60%
      const clampedWidth = Math.max(20, Math.min(60, newWidth))
      setWalkthroughWidth(clampedWidth)
    }

    const handleMouseUp = () => {
      setIsDragging(false)
      // Save to localStorage
      localStorage.setItem('student-lab-width', walkthroughWidth.toString())
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDragging, walkthroughWidth])

  if (loading) {
    return (
      <div className="h-screen w-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin mx-auto mb-2" />
          <p className="text-gray-400">Loading lab...</p>
        </div>
      </div>
    )
  }

  if (error || !range) {
    return (
      <div className="h-screen w-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center max-w-md px-4">
          <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-3" />
          <p className="text-red-400 mb-2">{error || 'Range not found'}</p>
          <a href="/ranges" className="text-blue-400 hover:underline">
            Return to ranges
          </a>
        </div>
      </div>
    )
  }

  if (!walkthrough) {
    return (
      <div className="h-screen w-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center max-w-md px-4">
          <BookOpen className="w-12 h-12 text-gray-600 mx-auto mb-3" />
          <p className="text-gray-400 mb-2">No walkthrough available for this range</p>
          <p className="text-gray-500 text-sm mb-4">
            An instructor needs to upload an MSEL with a walkthrough section.
          </p>
          <a href={`/ranges/${rangeId}`} className="text-blue-400 hover:underline">
            View range details
          </a>
        </div>
      </div>
    )
  }

  return (
    <div className="h-screen w-screen bg-gray-900 flex flex-col">
      <div ref={containerRef} className="flex-1 flex overflow-hidden">
        {/* Walkthrough Panel - Guide on the left */}
        {!isCollapsed && (
          <>
            <div
              className="h-full bg-gray-900 overflow-hidden flex-shrink-0"
              style={{ width: `${walkthroughWidth}%` }}
            >
              <WalkthroughPanel
                rangeId={rangeId!}
                walkthrough={walkthrough}
                onOpenVM={handleOpenVM}
                onCollapse={() => setIsCollapsed(true)}
              />
            </div>

            {/* Resize Handle */}
            <div
              className={`w-2 flex-shrink-0 cursor-col-resize flex items-center justify-center transition-colors ${
                isDragging ? 'bg-blue-500' : 'bg-gray-700 hover:bg-blue-500'
              }`}
              onMouseDown={handleMouseDown}
            >
              <GripVertical className={`w-4 h-4 ${isDragging ? 'text-white' : 'text-gray-500'}`} />
            </div>
          </>
        )}

        {/* Console Panel - VNC on the right */}
        <div className="flex-1 h-full flex flex-col relative bg-gray-900 min-w-0">
          {/* Expand button when collapsed */}
          {isCollapsed && (
            <button
              onClick={() => setIsCollapsed(false)}
              className="absolute left-2 top-2 z-10 p-2 bg-gray-800 rounded hover:bg-gray-700 flex items-center gap-2 border border-gray-700"
              title="Show walkthrough"
            >
              <BookOpen className="w-5 h-5 text-blue-400" />
              <ChevronRight className="w-4 h-4 text-gray-400" />
            </button>
          )}

          {/* Console */}
          <div className="flex-1 min-h-0">
            <ConsoleEmbed
              vmId={selectedVmId}
              vmHostname={selectedVm?.hostname || null}
              token={token}
            />
          </div>

          {/* VM Selector */}
          <VMSelector
            vms={vms}
            selectedVmId={selectedVmId}
            onSelectVM={setSelectedVmId}
          />
        </div>
      </div>

      {/* Drag overlay to prevent iframe from capturing mouse events */}
      {isDragging && (
        <div className="fixed inset-0 z-50 cursor-col-resize" />
      )}
    </div>
  )
}
