// frontend/src/components/scenarios/ScenarioPickerModal.tsx
import { useEffect, useState } from 'react'
import { scenariosApi } from '../../services/api'
import type { Scenario } from '../../types'
import { X, Loader2, Target, Shield, UserX, Clock, Zap, Search } from 'lucide-react'
import clsx from 'clsx'

interface ScenarioPickerModalProps {
  onSelect: (scenario: Scenario) => void
  onClose: () => void
}

const categoryConfig = {
  'red-team': {
    label: 'Red Team',
    icon: Target,
    color: 'text-red-600',
    bgColor: 'bg-red-100',
    borderColor: 'border-red-200',
  },
  'blue-team': {
    label: 'Blue Team',
    icon: Shield,
    color: 'text-blue-600',
    bgColor: 'bg-blue-100',
    borderColor: 'border-blue-200',
  },
  'insider-threat': {
    label: 'Insider Threat',
    icon: UserX,
    color: 'text-yellow-600',
    bgColor: 'bg-yellow-100',
    borderColor: 'border-yellow-200',
  },
}

const difficultyConfig = {
  beginner: { label: 'Beginner', color: 'bg-green-100 text-green-800' },
  intermediate: { label: 'Intermediate', color: 'bg-yellow-100 text-yellow-800' },
  advanced: { label: 'Advanced', color: 'bg-red-100 text-red-800' },
}

export default function ScenarioPickerModal({ onSelect, onClose }: ScenarioPickerModalProps) {
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [categoryFilter, setCategoryFilter] = useState<string>('')

  useEffect(() => {
    const fetchScenarios = async () => {
      try {
        const response = await scenariosApi.list(categoryFilter || undefined)
        setScenarios(response.data)
      } catch (err) {
        console.error('Failed to fetch scenarios:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchScenarios()
  }, [categoryFilter])

  const filteredScenarios = scenarios.filter((s) =>
    s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    s.description.toLowerCase().includes(searchQuery.toLowerCase())
  )

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4">
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75" onClick={onClose} />

        <div className="relative bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[85vh] overflow-hidden">
          <div className="flex items-center justify-between p-4 border-b sticky top-0 bg-white z-10">
            <h3 className="text-lg font-medium text-gray-900">Add Training Scenario</h3>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-500">
              <X className="h-5 w-5" />
            </button>
          </div>

          <div className="p-4 border-b bg-gray-50">
            <div className="flex gap-3">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search scenarios..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                />
              </div>
              <select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
              >
                <option value="">All Categories</option>
                <option value="red-team">Red Team</option>
                <option value="blue-team">Blue Team</option>
                <option value="insider-threat">Insider Threat</option>
              </select>
            </div>
          </div>

          <div className="p-4 overflow-y-auto max-h-[calc(85vh-140px)]">
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
              </div>
            ) : filteredScenarios.length === 0 ? (
              <div className="text-center py-12">
                <p className="text-sm text-gray-500">No scenarios found</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {filteredScenarios.map((scenario) => {
                  const catConfig = categoryConfig[scenario.category]
                  const diffConfig = difficultyConfig[scenario.difficulty]
                  const CategoryIcon = catConfig.icon

                  return (
                    <button
                      key={scenario.id}
                      onClick={() => onSelect(scenario)}
                      className={clsx(
                        "text-left p-4 rounded-lg border-2 hover:border-primary-500 transition-colors",
                        catConfig.borderColor
                      )}
                    >
                      <div className="flex items-start">
                        <div className={clsx("flex-shrink-0 rounded-md p-2", catConfig.bgColor)}>
                          <CategoryIcon className={clsx("h-5 w-5", catConfig.color)} />
                        </div>
                        <div className="ml-3 flex-1">
                          <div className="flex items-center justify-between">
                            <h4 className="text-sm font-medium text-gray-900">{scenario.name}</h4>
                            <span className={clsx("text-xs px-2 py-0.5 rounded", diffConfig.color)}>
                              {diffConfig.label}
                            </span>
                          </div>
                          <p className="mt-1 text-xs text-gray-500 line-clamp-2">
                            {scenario.description}
                          </p>
                          <div className="mt-2 flex items-center text-xs text-gray-400 space-x-3">
                            <span className="flex items-center">
                              <Clock className="h-3 w-3 mr-1" />
                              {scenario.duration_minutes} min
                            </span>
                            <span className="flex items-center">
                              <Zap className="h-3 w-3 mr-1" />
                              {scenario.event_count} events
                            </span>
                          </div>
                        </div>
                      </div>
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
