// frontend/src/components/admin/InfrastructureTab.tsx
import { useState, useEffect, useCallback } from 'react'
import {
  RefreshCw,
  Server,
  Activity,
  Database,
  HardDrive,
  FileText,
  Settings,
  ChevronDown,
  ChevronUp,
  Loader2,
  CheckCircle,
  XCircle,
  AlertCircle,
  Clock,
  Cpu,
  MemoryStick,
  Container,
  Network,
  Box,
  Search,
  Download,
} from 'lucide-react'
import clsx from 'clsx'
import {
  infrastructureApi,
  InfrastructureServicesResponse,
  ServiceLogsResponse,
  DockerOverviewResponse,
  InfrastructureMetricsResponse,
  SystemInfoResponse,
  RangeDebugResponse,
} from '../../services/api'

// Status badge component
function StatusBadge({ status }: { status: string }) {
  const config = {
    healthy: { color: 'bg-green-100 text-green-800', icon: CheckCircle },
    unhealthy: { color: 'bg-red-100 text-red-800', icon: XCircle },
    degraded: { color: 'bg-yellow-100 text-yellow-800', icon: AlertCircle },
    unknown: { color: 'bg-gray-100 text-gray-800', icon: AlertCircle },
    running: { color: 'bg-green-100 text-green-800', icon: CheckCircle },
    exited: { color: 'bg-red-100 text-red-800', icon: XCircle },
    stopped: { color: 'bg-gray-100 text-gray-800', icon: XCircle },
  }[status] || { color: 'bg-gray-100 text-gray-800', icon: AlertCircle }

  const Icon = config.icon

  return (
    <span className={clsx('inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium', config.color)}>
      <Icon className="h-3 w-3" />
      {status}
    </span>
  )
}

// Progress bar component
function ProgressBar({ value, max = 100, color = 'blue' }: { value: number; max?: number; color?: string }) {
  const percent = Math.min((value / max) * 100, 100)
  const colorClass = {
    blue: 'bg-blue-500',
    green: 'bg-green-500',
    yellow: 'bg-yellow-500',
    red: 'bg-red-500',
  }[color] || 'bg-blue-500'

  return (
    <div className="w-full bg-gray-200 rounded-full h-2">
      <div className={clsx('h-2 rounded-full transition-all', colorClass)} style={{ width: `${percent}%` }} />
    </div>
  )
}

// Collapsible section component
function CollapsibleSection({
  title,
  icon: Icon,
  defaultOpen = false,
  badge,
  children,
}: {
  title: string
  icon: typeof Server
  defaultOpen?: boolean
  badge?: string | number
  children: React.ReactNode
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen)

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Icon className="h-5 w-5 text-gray-500" />
          <span className="font-medium text-gray-900">{title}</span>
          {badge !== undefined && (
            <span className="px-2 py-0.5 bg-gray-200 text-gray-700 rounded-full text-xs">{badge}</span>
          )}
        </div>
        {isOpen ? <ChevronUp className="h-5 w-5 text-gray-400" /> : <ChevronDown className="h-5 w-5 text-gray-400" />}
      </button>
      {isOpen && <div className="p-4 border-t border-gray-200">{children}</div>}
    </div>
  )
}

export default function InfrastructureTab() {
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Data state
  const [services, setServices] = useState<InfrastructureServicesResponse | null>(null)
  const [docker, setDocker] = useState<DockerOverviewResponse | null>(null)
  const [metrics, setMetrics] = useState<InfrastructureMetricsResponse | null>(null)
  const [system, setSystem] = useState<SystemInfoResponse | null>(null)
  const [rangeDebug, setRangeDebug] = useState<RangeDebugResponse | null>(null)

  // Logs state
  const [selectedService, setSelectedService] = useState('api')
  const [logLevel, setLogLevel] = useState<string>('')
  const [logSearch, setLogSearch] = useState('')
  const [logs, setLogs] = useState<ServiceLogsResponse | null>(null)
  const [logsLoading, setLogsLoading] = useState(false)

  // Auto-refresh state
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [refreshInterval, setRefreshInterval] = useState(30)

  const fetchData = useCallback(async (showLoading = true) => {
    if (showLoading) setLoading(true)
    setRefreshing(true)
    setError(null)

    try {
      const [servicesRes, dockerRes, metricsRes, systemRes, rangeDebugRes] = await Promise.all([
        infrastructureApi.getServices(),
        infrastructureApi.getDocker(),
        infrastructureApi.getMetrics(),
        infrastructureApi.getSystem(),
        infrastructureApi.getRangeDebug(),
      ])

      setServices(servicesRes.data)
      setDocker(dockerRes.data)
      setMetrics(metricsRes.data)
      setSystem(systemRes.data)
      setRangeDebug(rangeDebugRes.data)
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch infrastructure data'
      setError(errorMessage)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  const fetchLogs = useCallback(async () => {
    setLogsLoading(true)
    try {
      const res = await infrastructureApi.getLogs({
        service: selectedService,
        level: logLevel || undefined,
        search: logSearch || undefined,
        limit: 200,
      })
      setLogs(res.data)
    } catch (err) {
      console.error('Failed to fetch logs:', err)
    } finally {
      setLogsLoading(false)
    }
  }, [selectedService, logLevel, logSearch])

  // Initial fetch
  useEffect(() => {
    fetchData()
  }, [fetchData])

  // Fetch logs when service or filters change
  useEffect(() => {
    fetchLogs()
  }, [fetchLogs])

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh) return

    const interval = setInterval(() => {
      fetchData(false)
      fetchLogs()
    }, refreshInterval * 1000)

    return () => clearInterval(interval)
  }, [autoRefresh, refreshInterval, fetchData, fetchLogs])

  const downloadLogs = () => {
    if (!logs) return
    const content = logs.logs.map((l) => l.raw).join('\n')
    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${selectedService}-logs-${new Date().toISOString().split('T')[0]}.log`
    a.click()
    URL.revokeObjectURL(url)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
        <span className="ml-2 text-gray-600">Loading infrastructure data...</span>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header with refresh controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold text-gray-900">Infrastructure Observability</h2>
          {services && (
            <StatusBadge status={services.overall_status} />
          )}
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-gray-600">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
            />
            Auto-refresh
          </label>
          {autoRefresh && (
            <select
              value={refreshInterval}
              onChange={(e) => setRefreshInterval(Number(e.target.value))}
              className="text-sm border-gray-300 rounded-md"
            >
              <option value={10}>10s</option>
              <option value={30}>30s</option>
              <option value={60}>60s</option>
            </select>
          )}
          <button
            onClick={() => { fetchData(); fetchLogs(); }}
            disabled={refreshing}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
          >
            <RefreshCw className={clsx('h-4 w-4', refreshing && 'animate-spin')} />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          {error}
        </div>
      )}

      {/* Service Health Grid */}
      <div className="bg-white rounded-lg shadow p-4">
        <h3 className="text-sm font-medium text-gray-900 mb-4 flex items-center gap-2">
          <Server className="h-4 w-4" />
          Service Health
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {services?.services.map((service) => (
            <div
              key={service.name}
              className={clsx(
                'p-4 rounded-lg border',
                service.status === 'healthy' && 'border-green-200 bg-green-50',
                service.status === 'unhealthy' && 'border-red-200 bg-red-50',
                service.status === 'degraded' && 'border-yellow-200 bg-yellow-50',
                service.status === 'unknown' && 'border-gray-200 bg-gray-50'
              )}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium text-gray-900">{service.display_name}</span>
                <StatusBadge status={service.status} />
              </div>
              {service.uptime_human && (
                <div className="flex items-center gap-1 text-xs text-gray-500 mb-2">
                  <Clock className="h-3 w-3" />
                  Uptime: {service.uptime_human}
                </div>
              )}
              {service.cpu_percent !== null && service.cpu_percent !== undefined && (
                <div className="mb-1">
                  <div className="flex items-center justify-between text-xs text-gray-500 mb-0.5">
                    <span className="flex items-center gap-1">
                      <Cpu className="h-3 w-3" />
                      CPU
                    </span>
                    <span>{service.cpu_percent.toFixed(1)}%</span>
                  </div>
                  <ProgressBar
                    value={service.cpu_percent}
                    color={service.cpu_percent > 80 ? 'red' : service.cpu_percent > 50 ? 'yellow' : 'green'}
                  />
                </div>
              )}
              {service.memory_percent !== null && service.memory_percent !== undefined && (
                <div>
                  <div className="flex items-center justify-between text-xs text-gray-500 mb-0.5">
                    <span className="flex items-center gap-1">
                      <MemoryStick className="h-3 w-3" />
                      Memory
                    </span>
                    <span>{service.memory_mb?.toFixed(0)} MB ({service.memory_percent.toFixed(1)}%)</span>
                  </div>
                  <ProgressBar
                    value={service.memory_percent}
                    color={service.memory_percent > 80 ? 'red' : service.memory_percent > 50 ? 'yellow' : 'green'}
                  />
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Log Viewer */}
      <div className="bg-white rounded-lg shadow p-4">
        <h3 className="text-sm font-medium text-gray-900 mb-4 flex items-center gap-2">
          <FileText className="h-4 w-4" />
          Log Viewer
        </h3>
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <select
            value={selectedService}
            onChange={(e) => setSelectedService(e.target.value)}
            className="text-sm border-gray-300 rounded-md"
          >
            <option value="api">API Server</option>
            <option value="worker">Task Worker</option>
            <option value="db">PostgreSQL</option>
            <option value="redis">Redis</option>
            <option value="minio">MinIO</option>
            <option value="traefik">Traefik</option>
            <option value="frontend">Frontend</option>
          </select>
          <select
            value={logLevel}
            onChange={(e) => setLogLevel(e.target.value)}
            className="text-sm border-gray-300 rounded-md"
          >
            <option value="">All Levels</option>
            <option value="error">Error</option>
            <option value="warning">Warning</option>
            <option value="info">Info</option>
            <option value="debug">Debug</option>
          </select>
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search logs..."
              value={logSearch}
              onChange={(e) => setLogSearch(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 text-sm border-gray-300 rounded-md"
            />
          </div>
          <button
            onClick={downloadLogs}
            disabled={!logs || logs.logs.length === 0}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
          >
            <Download className="h-4 w-4" />
            Download
          </button>
        </div>
        <div className="bg-gray-900 rounded-lg p-3 max-h-80 overflow-auto font-mono text-xs">
          {logsLoading ? (
            <div className="flex items-center justify-center py-8 text-gray-400">
              <Loader2 className="h-5 w-5 animate-spin mr-2" />
              Loading logs...
            </div>
          ) : logs && logs.logs.length > 0 ? (
            logs.logs.map((entry, idx) => (
              <div key={idx} className="py-0.5 hover:bg-gray-800 rounded">
                {entry.timestamp && (
                  <span className="text-gray-500">{new Date(entry.timestamp).toLocaleTimeString()} </span>
                )}
                {entry.level && (
                  <span
                    className={clsx(
                      'font-semibold',
                      entry.level === 'ERROR' && 'text-red-400',
                      entry.level === 'WARN' && 'text-yellow-400',
                      entry.level === 'INFO' && 'text-blue-400',
                      entry.level === 'DEBUG' && 'text-gray-400'
                    )}
                  >
                    [{entry.level}]{' '}
                  </span>
                )}
                <span className="text-gray-200">{entry.message}</span>
              </div>
            ))
          ) : (
            <div className="text-gray-400 text-center py-8">No logs found</div>
          )}
        </div>
        {logs && (
          <div className="mt-2 text-xs text-gray-500">
            Showing {logs.logs.length} of {logs.total_lines} lines
            {logs.has_more && ' (more available)'}
          </div>
        )}
      </div>

      {/* Docker Overview */}
      <div className="bg-white rounded-lg shadow p-4">
        <h3 className="text-sm font-medium text-gray-900 mb-4 flex items-center gap-2">
          <Container className="h-4 w-4" />
          Docker Overview
        </h3>
        {docker && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-4">
            <div className="text-center p-3 bg-gray-50 rounded-lg">
              <div className="text-2xl font-bold text-gray-900">{docker.summary.total_containers}</div>
              <div className="text-xs text-gray-500">Containers ({docker.summary.running_containers} running)</div>
            </div>
            <div className="text-center p-3 bg-gray-50 rounded-lg">
              <div className="text-2xl font-bold text-gray-900">{docker.summary.total_networks}</div>
              <div className="text-xs text-gray-500">Networks ({docker.summary.cyroid_networks} CYROID)</div>
            </div>
            <div className="text-center p-3 bg-gray-50 rounded-lg">
              <div className="text-2xl font-bold text-gray-900">{docker.summary.total_volumes}</div>
              <div className="text-xs text-gray-500">Volumes</div>
            </div>
            <div className="text-center p-3 bg-gray-50 rounded-lg">
              <div className="text-2xl font-bold text-gray-900">{docker.summary.total_images}</div>
              <div className="text-xs text-gray-500">Images</div>
            </div>
          </div>
        )}
        <div className="space-y-3">
          <CollapsibleSection title="Containers" icon={Container} badge={docker?.containers.length}>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-2 px-2 font-medium text-gray-600">Name</th>
                    <th className="text-left py-2 px-2 font-medium text-gray-600">Image</th>
                    <th className="text-left py-2 px-2 font-medium text-gray-600">Status</th>
                    <th className="text-left py-2 px-2 font-medium text-gray-600">Type</th>
                  </tr>
                </thead>
                <tbody>
                  {docker?.containers.map((c) => (
                    <tr key={c.id} className="border-b border-gray-100 hover:bg-gray-50">
                      <td className="py-2 px-2 font-mono text-xs">{c.name}</td>
                      <td className="py-2 px-2 text-gray-600 max-w-xs truncate">{c.image}</td>
                      <td className="py-2 px-2">
                        <StatusBadge status={c.status} />
                      </td>
                      <td className="py-2 px-2">
                        {c.is_cyroid_infra && <span className="text-xs bg-blue-100 text-blue-800 px-1.5 py-0.5 rounded">Infra</span>}
                        {c.is_cyroid_vm && <span className="text-xs bg-purple-100 text-purple-800 px-1.5 py-0.5 rounded">VM</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CollapsibleSection>

          <CollapsibleSection title="Networks" icon={Network} badge={docker?.networks.length}>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-2 px-2 font-medium text-gray-600">Name</th>
                    <th className="text-left py-2 px-2 font-medium text-gray-600">Subnet</th>
                    <th className="text-left py-2 px-2 font-medium text-gray-600">Driver</th>
                    <th className="text-left py-2 px-2 font-medium text-gray-600">Containers</th>
                  </tr>
                </thead>
                <tbody>
                  {docker?.networks.map((n) => (
                    <tr key={n.id} className="border-b border-gray-100 hover:bg-gray-50">
                      <td className="py-2 px-2 font-mono text-xs">
                        {n.name}
                        {n.is_cyroid_range && (
                          <span className="ml-2 text-xs bg-green-100 text-green-800 px-1.5 py-0.5 rounded">Range</span>
                        )}
                      </td>
                      <td className="py-2 px-2 text-gray-600">{n.subnet || '-'}</td>
                      <td className="py-2 px-2 text-gray-600">{n.driver}</td>
                      <td className="py-2 px-2 text-gray-600">{n.container_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CollapsibleSection>

          <CollapsibleSection title="Images" icon={Box} badge={docker?.images.length}>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-2 px-2 font-medium text-gray-600">Tags</th>
                    <th className="text-left py-2 px-2 font-medium text-gray-600">Size</th>
                    <th className="text-left py-2 px-2 font-medium text-gray-600">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {docker?.images.slice(0, 20).map((img) => (
                    <tr key={img.id} className="border-b border-gray-100 hover:bg-gray-50">
                      <td className="py-2 px-2">
                        {img.tags.length > 0 ? (
                          <span className="font-mono text-xs">{img.tags[0]}</span>
                        ) : (
                          <span className="text-gray-400 text-xs">&lt;none&gt;</span>
                        )}
                        {img.is_cyroid_related && (
                          <span className="ml-2 text-xs bg-purple-100 text-purple-800 px-1.5 py-0.5 rounded">CYROID</span>
                        )}
                      </td>
                      <td className="py-2 px-2 text-gray-600">{img.size_human}</td>
                      <td className="py-2 px-2 text-gray-600 text-xs">
                        {img.created ? new Date(img.created).toLocaleDateString() : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {docker && docker.images.length > 20 && (
                <div className="text-xs text-gray-500 mt-2">
                  Showing 20 of {docker.images.length} images
                </div>
              )}
            </div>
          </CollapsibleSection>
        </div>
      </div>

      {/* Resource Metrics */}
      <div className="bg-white rounded-lg shadow p-4">
        <h3 className="text-sm font-medium text-gray-900 mb-4 flex items-center gap-2">
          <Activity className="h-4 w-4" />
          Resource Metrics
        </h3>
        {metrics && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Host Metrics */}
            <div className="space-y-3">
              <h4 className="font-medium text-gray-700 flex items-center gap-2">
                <Cpu className="h-4 w-4" />
                Host System
              </h4>
              <div>
                <div className="flex justify-between text-sm text-gray-600 mb-1">
                  <span>CPU ({metrics.host.cpu_count} cores)</span>
                  <span>{metrics.host.cpu_percent.toFixed(1)}%</span>
                </div>
                <ProgressBar
                  value={metrics.host.cpu_percent}
                  color={metrics.host.cpu_percent > 80 ? 'red' : metrics.host.cpu_percent > 50 ? 'yellow' : 'blue'}
                />
              </div>
              <div>
                <div className="flex justify-between text-sm text-gray-600 mb-1">
                  <span>Memory</span>
                  <span>
                    {(metrics.host.memory_used_mb / 1024).toFixed(1)} / {(metrics.host.memory_total_mb / 1024).toFixed(1)} GB
                  </span>
                </div>
                <ProgressBar
                  value={metrics.host.memory_percent}
                  color={metrics.host.memory_percent > 80 ? 'red' : metrics.host.memory_percent > 50 ? 'yellow' : 'blue'}
                />
              </div>
              <div>
                <div className="flex justify-between text-sm text-gray-600 mb-1">
                  <span>Disk</span>
                  <span>
                    {metrics.host.disk_used_gb.toFixed(1)} / {metrics.host.disk_total_gb.toFixed(1)} GB
                  </span>
                </div>
                <ProgressBar
                  value={metrics.host.disk_percent}
                  color={metrics.host.disk_percent > 80 ? 'red' : metrics.host.disk_percent > 50 ? 'yellow' : 'blue'}
                />
              </div>
              {metrics.host.load_average && (
                <div className="text-sm text-gray-600">
                  Load Average: {metrics.host.load_average.map((l) => l.toFixed(2)).join(' / ')}
                </div>
              )}
            </div>

            {/* Database Metrics */}
            <div className="space-y-3">
              <h4 className="font-medium text-gray-700 flex items-center gap-2">
                <Database className="h-4 w-4" />
                Database
              </h4>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="p-2 bg-gray-50 rounded">
                  <div className="text-gray-500">Size</div>
                  <div className="font-medium">{metrics.database.database_size_human}</div>
                </div>
                <div className="p-2 bg-gray-50 rounded">
                  <div className="text-gray-500">Tables</div>
                  <div className="font-medium">{metrics.database.table_count}</div>
                </div>
                <div className="p-2 bg-gray-50 rounded">
                  <div className="text-gray-500">Connections</div>
                  <div className="font-medium">{metrics.database.connection_count}</div>
                </div>
                <div className="p-2 bg-gray-50 rounded">
                  <div className="text-gray-500">Active</div>
                  <div className="font-medium">{metrics.database.active_connections}</div>
                </div>
              </div>
            </div>

            {/* Task Queue Metrics */}
            <div className="space-y-3">
              <h4 className="font-medium text-gray-700 flex items-center gap-2">
                <Activity className="h-4 w-4" />
                Task Queue
              </h4>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="p-2 bg-gray-50 rounded">
                  <div className="text-gray-500">Queue Length</div>
                  <div className="font-medium">{metrics.task_queue.queue_length}</div>
                </div>
                <div className="p-2 bg-gray-50 rounded">
                  <div className="text-gray-500">Delayed</div>
                  <div className="font-medium">{metrics.task_queue.delayed_messages}</div>
                </div>
              </div>
            </div>

            {/* Storage Metrics */}
            <div className="space-y-3">
              <h4 className="font-medium text-gray-700 flex items-center gap-2">
                <HardDrive className="h-4 w-4" />
                Storage
              </h4>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="p-2 bg-gray-50 rounded">
                  <div className="text-gray-500">ISO Cache</div>
                  <div className="font-medium">{metrics.storage.iso_cache_size_mb.toFixed(1)} MB</div>
                  <div className="text-xs text-gray-400">{metrics.storage.iso_cache_files} files</div>
                </div>
                <div className="p-2 bg-gray-50 rounded">
                  <div className="text-gray-500">Templates</div>
                  <div className="font-medium">{metrics.storage.template_storage_size_mb.toFixed(1)} MB</div>
                  <div className="text-xs text-gray-400">{metrics.storage.template_storage_files} files</div>
                </div>
                <div className="p-2 bg-gray-50 rounded">
                  <div className="text-gray-500">VM Storage</div>
                  <div className="font-medium">{metrics.storage.vm_storage_size_mb.toFixed(1)} MB</div>
                  <div className="text-xs text-gray-400">{metrics.storage.vm_storage_dirs} VMs</div>
                </div>
                <div className="p-2 bg-gray-50 rounded">
                  <div className="text-gray-500">MinIO</div>
                  <div className="font-medium">{metrics.storage.minio_total_size_mb.toFixed(1)} MB</div>
                  <div className="text-xs text-gray-400">{metrics.storage.minio_total_objects} objects</div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* System Information */}
      <div className="bg-white rounded-lg shadow p-4">
        <h3 className="text-sm font-medium text-gray-900 mb-4 flex items-center gap-2">
          <Settings className="h-4 w-4" />
          System Information
        </h3>
        {system && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Version</span>
                <span className="font-medium">{system.version}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Commit</span>
                <span className="font-mono text-xs">{system.commit}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Architecture</span>
                <span className="font-medium">
                  {system.architecture}
                  {system.is_arm && <span className="ml-1 text-xs bg-yellow-100 text-yellow-800 px-1 rounded">ARM</span>}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Python</span>
                <span className="font-medium">{system.python_version}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Docker</span>
                <span className="font-medium">{system.docker_version || 'N/A'}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">DB Revision</span>
                <span className="font-mono text-xs">{system.database_revision || 'N/A'}</span>
              </div>
            </div>
            <div className="space-y-2">
              <h4 className="font-medium text-gray-700 text-sm">Configuration</h4>
              {system.config.map((item) => (
                <div key={item.key} className="flex justify-between text-sm">
                  <span className="text-gray-500">{item.key}</span>
                  <span className="font-mono text-xs truncate max-w-[200px]" title={item.value}>
                    {item.value}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Range Debug Information */}
      <div className="bg-white rounded-lg shadow p-4">
        <h3 className="text-sm font-medium text-gray-900 mb-4 flex items-center gap-2">
          <Database className="h-4 w-4" />
          Range Debug Info
          {rangeDebug && (
            <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
              {rangeDebug.total_count} ranges
            </span>
          )}
        </h3>
        {rangeDebug && (
          <div className="space-y-4">
            {/* Summary */}
            <div className="flex gap-4 text-sm">
              <div className="p-2 bg-gray-50 rounded">
                <span className="text-gray-500">DinD Containers (Docker): </span>
                <span className="font-medium">{rangeDebug.dind_containers_in_docker.length}</span>
              </div>
              <div className="p-2 bg-gray-50 rounded">
                <span className="text-gray-500">Ranges in DB: </span>
                <span className="font-medium">{rangeDebug.total_count}</span>
              </div>
            </div>

            {/* Range Details */}
            <div className="space-y-3">
              {rangeDebug.ranges.map((range) => (
                <CollapsibleSection
                  key={range.id}
                  title={range.name}
                  icon={Server}
                  badge={range.status}
                >
                  <div className="space-y-4">
                    {/* DinD Info */}
                    <div>
                      <h5 className="text-xs font-medium text-gray-700 mb-2">DinD Container</h5>
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <div>
                          <span className="text-gray-500">Container ID: </span>
                          <span className={clsx('font-mono', !range.dind_container_id && 'text-red-500')}>
                            {range.dind_container_id?.slice(0, 12) || 'NOT SET'}
                          </span>
                        </div>
                        <div>
                          <span className="text-gray-500">Docker URL: </span>
                          <span className={clsx('font-mono', !range.dind_docker_url && 'text-red-500')}>
                            {range.dind_docker_url || 'NOT SET'}
                          </span>
                        </div>
                        <div>
                          <span className="text-gray-500">Container Name: </span>
                          <span className="font-mono">{range.dind_container_name || '-'}</span>
                        </div>
                        <div>
                          <span className="text-gray-500">Mgmt IP: </span>
                          <span className="font-mono">{range.dind_mgmt_ip || '-'}</span>
                        </div>
                      </div>
                    </div>

                    {/* Router Info */}
                    <div>
                      <h5 className="text-xs font-medium text-gray-700 mb-2">Router</h5>
                      <div className="text-xs">
                        <span className="text-gray-500">Container: </span>
                        <span className="font-mono">{range.router_container_id?.slice(0, 12) || 'None'}</span>
                        {range.router_status && (
                          <span className="ml-2">
                            <StatusBadge status={range.router_status.toLowerCase()} />
                          </span>
                        )}
                      </div>
                    </div>

                    {/* VNC Proxy Mappings */}
                    <div>
                      <h5 className="text-xs font-medium text-gray-700 mb-2">
                        VNC Proxy Mappings ({Object.keys(range.vnc_proxy_mappings || {}).length})
                      </h5>
                      {range.vnc_proxy_mappings && Object.keys(range.vnc_proxy_mappings).length > 0 ? (
                        <div className="overflow-x-auto">
                          <table className="min-w-full text-xs">
                            <thead>
                              <tr className="border-b text-left">
                                <th className="py-1 px-2 text-gray-500">VM ID</th>
                                <th className="py-1 px-2 text-gray-500">Proxy Port</th>
                                <th className="py-1 px-2 text-gray-500">Original Port</th>
                                <th className="py-1 px-2 text-gray-500">Host</th>
                              </tr>
                            </thead>
                            <tbody>
                              {Object.entries(range.vnc_proxy_mappings).map(([vmId, mapping]) => (
                                <tr key={vmId} className="border-b border-gray-100">
                                  <td className="py-1 px-2 font-mono">{vmId.slice(0, 8)}...</td>
                                  <td className="py-1 px-2">{mapping.proxy_port}</td>
                                  <td className="py-1 px-2">{mapping.original_port}</td>
                                  <td className="py-1 px-2">{mapping.proxy_host}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      ) : (
                        <p className="text-xs text-gray-500">No VNC proxy mappings configured</p>
                      )}
                    </div>

                    {/* VMs */}
                    <div>
                      <h5 className="text-xs font-medium text-gray-700 mb-2">VMs ({range.vms.length})</h5>
                      {range.vms.length > 0 ? (
                        <div className="overflow-x-auto">
                          <table className="min-w-full text-xs">
                            <thead>
                              <tr className="border-b text-left">
                                <th className="py-1 px-2 text-gray-500">Hostname</th>
                                <th className="py-1 px-2 text-gray-500">Status</th>
                                <th className="py-1 px-2 text-gray-500">Container ID</th>
                                <th className="py-1 px-2 text-gray-500">IP</th>
                                <th className="py-1 px-2 text-gray-500">Image</th>
                              </tr>
                            </thead>
                            <tbody>
                              {range.vms.map((vm) => (
                                <tr key={vm.id} className="border-b border-gray-100">
                                  <td className="py-1 px-2 font-medium">{vm.hostname}</td>
                                  <td className="py-1 px-2">
                                    <StatusBadge status={vm.status.toLowerCase()} />
                                  </td>
                                  <td className="py-1 px-2 font-mono">
                                    {vm.container_id?.slice(0, 12) || <span className="text-gray-400">-</span>}
                                  </td>
                                  <td className="py-1 px-2">{vm.ip_address || '-'}</td>
                                  <td className="py-1 px-2 truncate max-w-[150px]" title={vm.base_image || ''}>
                                    {vm.base_image || '-'}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      ) : (
                        <p className="text-xs text-gray-500">No VMs in this range</p>
                      )}
                    </div>
                  </div>
                </CollapsibleSection>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
