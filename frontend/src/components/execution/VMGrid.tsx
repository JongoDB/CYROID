// frontend/src/components/execution/VMGrid.tsx
import { useEffect, useState } from 'react'
import { VM, VMStats } from '../../types'
import { vmsApi } from '../../services/api'
import {
  Play, Square, RotateCcw, Terminal, Server, Cpu, HardDrive
} from 'lucide-react'
import clsx from 'clsx'

interface Props {
  vms: VM[]
  onRefresh: () => void
  onOpenConsole: (vmId: string, hostname: string) => void
}

const statusColors: Record<VM['status'], string> = {
  pending: 'bg-gray-500',
  creating: 'bg-yellow-500 animate-pulse',
  running: 'bg-green-500',
  stopped: 'bg-red-500',
  error: 'bg-red-700',
}

export function VMGrid({ vms, onRefresh, onOpenConsole }: Props) {
  const [vmStats, setVmStats] = useState<Record<string, VMStats | null>>({})

  useEffect(() => {
    const runningVms = vms.filter(vm => vm.status === 'running')
    if (runningVms.length === 0) return

    const fetchStats = async () => {
      const statsMap: Record<string, VMStats | null> = {}
      await Promise.all(
        runningVms.map(async (vm) => {
          try {
            const response = await vmsApi.getStats(vm.id)
            statsMap[vm.id] = response.data.stats
          } catch {
            statsMap[vm.id] = null
          }
        })
      )
      setVmStats(statsMap)
    }

    fetchStats()
    const interval = setInterval(fetchStats, 5000)
    return () => clearInterval(interval)
  }, [vms])

  const handleAction = async (vmId: string, action: 'start' | 'stop' | 'restart') => {
    try {
      switch (action) {
        case 'start':
          await vmsApi.start(vmId)
          break
        case 'stop':
          await vmsApi.stop(vmId)
          break
        case 'restart':
          await vmsApi.restart(vmId)
          break
      }
      onRefresh()
    } catch (error) {
      console.error(`Failed to ${action} VM:`, error)
    }
  }

  if (vms.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No VMs in this range
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3 lg:gap-4">
      {vms.map((vm) => {
        const stats = vmStats[vm.id]
        return (
          <div
            key={vm.id}
            className="bg-white rounded-lg shadow p-3 lg:p-4 border border-gray-200 min-w-0"
          >
            <div className="flex items-center justify-between mb-3 gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <Server className="w-5 h-5 text-orange-500 shrink-0" />
                <span className="font-medium truncate">{vm.hostname}</span>
              </div>
              <span className={clsx('w-3 h-3 rounded-full shrink-0', statusColors[vm.status])} />
            </div>

            <div className="text-xs text-gray-500 mb-3 space-y-1">
              <p>IP: {vm.ip_address}</p>
              {vm.status === 'running' && stats ? (
                <>
                  <div className="flex items-center gap-1" title="CPU Usage">
                    <Cpu className="w-3 h-3" />
                    <span>{stats.cpu_percent.toFixed(1)}%</span>
                    <div className="flex-1 bg-gray-200 rounded h-1.5">
                      <div
                        className="bg-blue-500 h-1.5 rounded"
                        style={{ width: `${Math.min(stats.cpu_percent, 100)}%` }}
                      />
                    </div>
                  </div>
                  <div className="flex items-center gap-1" title="Memory Usage">
                    <HardDrive className="w-3 h-3" />
                    <span>{stats.memory_percent.toFixed(1)}%</span>
                    <div className="flex-1 bg-gray-200 rounded h-1.5">
                      <div
                        className={clsx(
                          'h-1.5 rounded',
                          stats.memory_percent > 80 ? 'bg-red-500' : 'bg-green-500'
                        )}
                        style={{ width: `${Math.min(stats.memory_percent, 100)}%` }}
                      />
                    </div>
                  </div>
                </>
              ) : (
                <>
                  <p>CPU: {vm.cpu} cores</p>
                  <p>RAM: {vm.ram_mb} MB</p>
                </>
              )}
            </div>

            <div className="flex gap-1">
              {vm.status === 'stopped' || vm.status === 'pending' ? (
                <button
                  onClick={() => handleAction(vm.id, 'start')}
                  className="p-1.5 hover:bg-green-100 rounded"
                  title="Start"
                >
                  <Play className="w-4 h-4 text-green-600" />
                </button>
              ) : null}
              {vm.status === 'running' && (
                <>
                  <button
                    onClick={() => handleAction(vm.id, 'stop')}
                    className="p-1.5 hover:bg-red-100 rounded"
                    title="Stop"
                  >
                    <Square className="w-4 h-4 text-red-600" />
                  </button>
                  <button
                    onClick={() => handleAction(vm.id, 'restart')}
                    className="p-1.5 hover:bg-blue-100 rounded"
                    title="Restart"
                  >
                    <RotateCcw className="w-4 h-4 text-blue-600" />
                  </button>
                  <button
                    onClick={() => onOpenConsole(vm.id, vm.hostname)}
                    className="p-1.5 hover:bg-gray-100 rounded"
                    title="Console"
                  >
                    <Terminal className="w-4 h-4 text-gray-600" />
                  </button>
                </>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
