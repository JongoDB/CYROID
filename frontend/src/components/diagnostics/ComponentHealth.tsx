// frontend/src/components/diagnostics/ComponentHealth.tsx
import { useState } from 'react'
import { ChevronDown, ChevronRight, Server, Network as NetworkIcon, Router, Box, AlertCircle, CheckCircle, Clock, XCircle } from 'lucide-react'
import type { Range, Network, VM } from '../../types'
import clsx from 'clsx'

interface ComponentHealthProps {
  range: Range
  networks: Network[]
  vms: VM[]
  onSelectVm: (vm: VM) => void
  selectedVmId: string | null
}

type HealthStatus = 'healthy' | 'warning' | 'error' | 'pending'

function getStatusIcon(status: string): { icon: typeof CheckCircle; color: string; health: HealthStatus } {
  switch (status) {
    case 'running':
      return { icon: CheckCircle, color: 'text-green-500', health: 'healthy' }
    case 'stopped':
      return { icon: Clock, color: 'text-gray-400', health: 'pending' }
    case 'error':
      return { icon: XCircle, color: 'text-red-500', health: 'error' }
    case 'creating':
    case 'deploying':
    case 'pending':
      return { icon: Clock, color: 'text-yellow-500', health: 'warning' }
    default:
      return { icon: AlertCircle, color: 'text-gray-400', health: 'pending' }
  }
}

function StatusBadge({ status }: { status: string }) {
  const { icon: Icon, color } = getStatusIcon(status)
  return (
    <div className="flex items-center gap-1.5">
      <Icon className={clsx("w-4 h-4", color)} />
      <span className="text-sm text-gray-600">{status}</span>
    </div>
  )
}

export function ComponentHealth({ range, networks, vms, onSelectVm, selectedVmId }: ComponentHealthProps) {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['range', 'networks', 'vms']))

  const toggleSection = (section: string) => {
    setExpandedSections(prev => {
      const next = new Set(prev)
      if (next.has(section)) {
        next.delete(section)
      } else {
        next.add(section)
      }
      return next
    })
  }

  const errorVms = vms.filter(vm => vm.status === 'error')
  const errorCount = errorVms.length + (range.status === 'error' ? 1 : 0) + (range.router?.status === 'error' ? 1 : 0)

  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
      <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-900">Component Health</h3>
        {errorCount > 0 && (
          <span className="px-2 py-0.5 text-xs font-medium bg-red-100 text-red-800 rounded-full">
            {errorCount} error{errorCount > 1 ? 's' : ''}
          </span>
        )}
      </div>

      <div className="divide-y divide-gray-100">
        {/* Range Status */}
        <div className="px-4 py-2">
          <button
            onClick={() => toggleSection('range')}
            className="flex items-center gap-2 w-full text-left"
          >
            {expandedSections.has('range') ? (
              <ChevronDown className="w-4 h-4 text-gray-400" />
            ) : (
              <ChevronRight className="w-4 h-4 text-gray-400" />
            )}
            <Box className="w-4 h-4 text-primary-500" />
            <span className="text-sm font-medium text-gray-700">Range</span>
            <StatusBadge status={range.status} />
          </button>
          {expandedSections.has('range') && range.error_message && (
            <div className="ml-10 mt-1 text-xs text-red-600 bg-red-50 px-2 py-1 rounded">
              {range.error_message}
            </div>
          )}
        </div>

        {/* Router Status */}
        {range.router && (
          <div className="px-4 py-2">
            <div className="flex items-center gap-2 ml-6">
              <Router className="w-4 h-4 text-blue-500" />
              <span className="text-sm text-gray-700">VyOS Router</span>
              <StatusBadge status={range.router.status} />
            </div>
            {range.router.error_message && (
              <div className="ml-10 mt-1 text-xs text-red-600 bg-red-50 px-2 py-1 rounded">
                {range.router.error_message}
              </div>
            )}
          </div>
        )}

        {/* Networks */}
        <div className="px-4 py-2">
          <button
            onClick={() => toggleSection('networks')}
            className="flex items-center gap-2 w-full text-left"
          >
            {expandedSections.has('networks') ? (
              <ChevronDown className="w-4 h-4 text-gray-400" />
            ) : (
              <ChevronRight className="w-4 h-4 text-gray-400" />
            )}
            <NetworkIcon className="w-4 h-4 text-green-500" />
            <span className="text-sm font-medium text-gray-700">Networks</span>
            <span className="text-xs text-gray-400">({networks.length})</span>
          </button>
          {expandedSections.has('networks') && (
            <div className="ml-10 mt-1 space-y-1">
              {networks.map(network => (
                <div key={network.id} className="flex items-center gap-2 text-sm text-gray-600">
                  <CheckCircle className="w-3 h-3 text-green-500" />
                  <span>{network.name}</span>
                  <span className="text-xs text-gray-400">({network.subnet})</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* VMs */}
        <div className="px-4 py-2">
          <button
            onClick={() => toggleSection('vms')}
            className="flex items-center gap-2 w-full text-left"
          >
            {expandedSections.has('vms') ? (
              <ChevronDown className="w-4 h-4 text-gray-400" />
            ) : (
              <ChevronRight className="w-4 h-4 text-gray-400" />
            )}
            <Server className="w-4 h-4 text-purple-500" />
            <span className="text-sm font-medium text-gray-700">VMs</span>
            <span className="text-xs text-gray-400">({vms.length})</span>
            {errorVms.length > 0 && (
              <span className="px-1.5 py-0.5 text-xs bg-red-100 text-red-700 rounded">
                {errorVms.length} error
              </span>
            )}
          </button>
          {expandedSections.has('vms') && (
            <div className="ml-10 mt-1 space-y-1">
              {vms.map(vm => (
                <button
                  key={vm.id}
                  onClick={() => onSelectVm(vm)}
                  className={clsx(
                    "flex items-center gap-2 text-sm w-full text-left px-2 py-1 rounded",
                    selectedVmId === vm.id ? "bg-primary-50" : "hover:bg-gray-50"
                  )}
                >
                  <StatusBadge status={vm.status} />
                  <span className={clsx(
                    "font-medium",
                    vm.status === 'error' ? 'text-red-700' : 'text-gray-700'
                  )}>
                    {vm.hostname}
                  </span>
                  <span className="text-xs text-gray-400">({vm.ip_address})</span>
                </button>
              ))}
              {vms.length === 0 && (
                <span className="text-xs text-gray-400">No VMs configured</span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
