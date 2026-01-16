// frontend/src/components/range/DeploymentProgress.tsx
import { useEffect, useState, useRef } from 'react'
import { EventLog, EventType } from '../../types'
import { eventsApi } from '../../services/api'
import {
  CheckCircle, Loader2, XCircle,
  ChevronDown, ChevronUp, Router, Network, Server, Rocket
} from 'lucide-react'
import clsx from 'clsx'

interface Props {
  rangeId: string
  rangeStatus: string
  totalNetworks: number
  totalVMs: number
  onDeploymentComplete?: () => void
}

type DeploymentStep = 'router' | 'networks' | 'vms' | 'complete'

interface StepStatus {
  status: 'pending' | 'in_progress' | 'completed' | 'error'
  message?: string
  progress?: string
}

const DEPLOYMENT_EVENT_TYPES: EventType[] = [
  'deployment_started',
  'deployment_step',
  'deployment_completed',
  'deployment_failed',
  'router_creating',
  'router_created',
  'network_creating',
  'network_created',
  'vm_creating',
  'vm_started',
]

export function DeploymentProgress({
  rangeId,
  rangeStatus,
  totalNetworks,
  totalVMs,
  onDeploymentComplete
}: Props) {
  const [events, setEvents] = useState<EventLog[]>([])
  const [showLog, setShowLog] = useState(false)
  const [steps, setSteps] = useState<Record<DeploymentStep, StepStatus>>({
    router: { status: 'pending' },
    networks: { status: 'pending' },
    vms: { status: 'pending' },
    complete: { status: 'pending' }
  })
  const logEndRef = useRef<HTMLDivElement>(null)
  const prevEventsLengthRef = useRef(0)

  // Poll for deployment events
  useEffect(() => {
    if (rangeStatus !== 'deploying') return

    const loadEvents = async () => {
      try {
        const response = await eventsApi.getEvents(rangeId, {
          limit: 100,
          event_types: DEPLOYMENT_EVENT_TYPES
        })
        setEvents(response.data.events.reverse()) // Show oldest first
      } catch (error) {
        console.error('Failed to load deployment events:', error)
      }
    }

    loadEvents()
    const interval = setInterval(loadEvents, 1000) // Poll faster during deployment
    return () => clearInterval(interval)
  }, [rangeId, rangeStatus])

  // Update step status based on events
  useEffect(() => {
    if (events.length === 0) return

    const newSteps: Record<DeploymentStep, StepStatus> = {
      router: { status: 'pending' },
      networks: { status: 'pending' },
      vms: { status: 'pending' },
      complete: { status: 'pending' }
    }

    let networksCreated = 0
    let vmsStarted = 0

    for (const event of events) {
      switch (event.event_type) {
        case 'deployment_started':
          newSteps.router = { status: 'in_progress', message: 'Initializing...' }
          break
        case 'router_creating':
          newSteps.router = { status: 'in_progress', message: 'Creating router...' }
          break
        case 'router_created':
          newSteps.router = { status: 'completed', message: 'Router ready' }
          newSteps.networks = { status: 'in_progress', message: 'Starting...' }
          break
        case 'network_creating':
          newSteps.router = { status: 'completed' }
          newSteps.networks = { status: 'in_progress', message: event.message }
          break
        case 'network_created':
          networksCreated++
          newSteps.router = { status: 'completed' }
          newSteps.networks = {
            status: networksCreated >= totalNetworks ? 'completed' : 'in_progress',
            progress: `${networksCreated}/${totalNetworks}`
          }
          break
        case 'vm_creating':
          newSteps.router = { status: 'completed' }
          newSteps.networks = { status: 'completed', progress: `${totalNetworks}/${totalNetworks}` }
          newSteps.vms = { status: 'in_progress', message: event.message }
          break
        case 'vm_started':
          vmsStarted++
          newSteps.router = { status: 'completed' }
          newSteps.networks = { status: 'completed' }
          newSteps.vms = {
            status: vmsStarted >= totalVMs ? 'completed' : 'in_progress',
            progress: `${vmsStarted}/${totalVMs}`
          }
          break
        case 'deployment_completed':
          newSteps.router = { status: 'completed' }
          newSteps.networks = { status: 'completed' }
          newSteps.vms = { status: 'completed' }
          newSteps.complete = { status: 'completed', message: 'Deployment successful!' }
          onDeploymentComplete?.()
          break
        case 'deployment_failed':
          // Mark current step as error
          if (newSteps.vms.status === 'in_progress') {
            newSteps.vms = { status: 'error', message: event.message }
          } else if (newSteps.networks.status === 'in_progress') {
            newSteps.networks = { status: 'error', message: event.message }
          } else {
            newSteps.router = { status: 'error', message: event.message }
          }
          newSteps.complete = { status: 'error', message: 'Deployment failed' }
          break
      }
    }

    setSteps(newSteps)
  }, [events, totalNetworks, totalVMs, onDeploymentComplete])

  // Auto-scroll log to bottom when new events arrive
  useEffect(() => {
    if (events.length > prevEventsLengthRef.current && showLog) {
      logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
    prevEventsLengthRef.current = events.length
  }, [events.length, showLog])

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString()
  }

  const stepConfig = [
    { key: 'router' as const, label: 'Router', icon: Router, description: 'VyOS network router' },
    { key: 'networks' as const, label: 'Networks', icon: Network, description: 'Docker networks' },
    { key: 'vms' as const, label: 'VMs', icon: Server, description: 'Virtual machines' },
    { key: 'complete' as const, label: 'Complete', icon: Rocket, description: 'Ready to use' },
  ]

  return (
    <div className="bg-white rounded-lg shadow-lg border border-blue-200 overflow-hidden">
      {/* Header */}
      <div className="bg-blue-50 px-6 py-4 border-b border-blue-200">
        <div className="flex items-center gap-3">
          <Loader2 className="w-5 h-5 text-blue-600 animate-spin" />
          <h3 className="text-lg font-semibold text-blue-900">Deploying Range...</h3>
        </div>
      </div>

      {/* Stepper */}
      <div className="px-6 py-6">
        <div className="flex items-center justify-between">
          {stepConfig.map((config, index) => {
            const step = steps[config.key]
            const Icon = config.icon
            return (
              <div key={config.key} className="flex items-center">
                <div className="flex flex-col items-center">
                  <div className={clsx(
                    'w-12 h-12 rounded-full flex items-center justify-center border-2',
                    step.status === 'completed' && 'bg-green-50 border-green-500',
                    step.status === 'in_progress' && 'bg-blue-50 border-blue-500',
                    step.status === 'error' && 'bg-red-50 border-red-500',
                    step.status === 'pending' && 'bg-gray-50 border-gray-200'
                  )}>
                    {step.status === 'completed' ? (
                      <CheckCircle className="w-6 h-6 text-green-500" />
                    ) : step.status === 'in_progress' ? (
                      <Loader2 className="w-6 h-6 text-blue-500 animate-spin" />
                    ) : step.status === 'error' ? (
                      <XCircle className="w-6 h-6 text-red-500" />
                    ) : (
                      <Icon className="w-6 h-6 text-gray-400" />
                    )}
                  </div>
                  <div className="mt-2 text-center">
                    <p className={clsx(
                      'text-sm font-medium',
                      step.status === 'completed' && 'text-green-700',
                      step.status === 'in_progress' && 'text-blue-700',
                      step.status === 'error' && 'text-red-700',
                      step.status === 'pending' && 'text-gray-500'
                    )}>
                      {config.label}
                    </p>
                    {step.progress && (
                      <p className="text-xs text-gray-500">{step.progress}</p>
                    )}
                  </div>
                </div>
                {index < stepConfig.length - 1 && (
                  <div className={clsx(
                    'flex-1 h-0.5 mx-4',
                    steps[stepConfig[index + 1].key].status !== 'pending' ? 'bg-green-500' : 'bg-gray-200'
                  )} />
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Current Status Message */}
      {events.length > 0 && (
        <div className="px-6 pb-4">
          <p className="text-sm text-gray-600 text-center">
            {events[events.length - 1]?.message}
          </p>
        </div>
      )}

      {/* Expandable Log */}
      <div className="border-t border-gray-200">
        <button
          onClick={() => setShowLog(!showLog)}
          className="w-full px-6 py-3 flex items-center justify-between text-sm text-gray-600 hover:bg-gray-50"
        >
          <span>Deployment Log ({events.length} events)</span>
          {showLog ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>

        {showLog && (
          <div className="max-h-64 overflow-y-auto bg-gray-900 p-4">
            {events.length === 0 ? (
              <p className="text-gray-500 text-sm">Waiting for deployment events...</p>
            ) : (
              <div className="space-y-1 font-mono text-xs">
                {events.map((event) => (
                  <div key={event.id} className="flex items-start gap-2">
                    <span className="text-gray-500 whitespace-nowrap">
                      [{formatTime(event.created_at)}]
                    </span>
                    <span className={clsx(
                      event.event_type === 'deployment_failed' && 'text-red-400',
                      event.event_type === 'deployment_completed' && 'text-green-400',
                      event.event_type.includes('creating') && 'text-yellow-400',
                      event.event_type.includes('created') && 'text-green-400',
                      event.event_type === 'vm_started' && 'text-green-400',
                      !['deployment_failed', 'deployment_completed'].includes(event.event_type) &&
                        !event.event_type.includes('creating') &&
                        !event.event_type.includes('created') &&
                        event.event_type !== 'vm_started' && 'text-gray-300'
                    )}>
                      {event.message}
                    </span>
                  </div>
                ))}
                <div ref={logEndRef} />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
