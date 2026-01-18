// frontend/src/pages/TrainingScenarios.tsx
import { useEffect, useState } from 'react'
import { scenariosApi } from '../services/api'
import type { Scenario } from '../types'
import { Loader2, Target, Shield, UserX, Clock, Zap, AlertTriangle } from 'lucide-react'
import clsx from 'clsx'

const categoryConfig = {
  'red-team': {
    label: 'Red Team',
    icon: Target,
    color: 'text-red-600',
    bgColor: 'bg-red-100',
  },
  'blue-team': {
    label: 'Blue Team',
    icon: Shield,
    color: 'text-blue-600',
    bgColor: 'bg-blue-100',
  },
  'insider-threat': {
    label: 'Insider Threat',
    icon: UserX,
    color: 'text-yellow-600',
    bgColor: 'bg-yellow-100',
  },
}

const difficultyConfig = {
  beginner: { label: 'Beginner', color: 'bg-green-100 text-green-800' },
  intermediate: { label: 'Intermediate', color: 'bg-yellow-100 text-yellow-800' },
  advanced: { label: 'Advanced', color: 'bg-red-100 text-red-800' },
}

export default function TrainingScenarios() {
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [loading, setLoading] = useState(true)
  const [categoryFilter, setCategoryFilter] = useState<string>('')
  const [searchQuery, setSearchQuery] = useState('')

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

  useEffect(() => {
    fetchScenarios()
  }, [categoryFilter])

  const filteredScenarios = scenarios.filter((s) =>
    s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    s.description.toLowerCase().includes(searchQuery.toLowerCase())
  )

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    )
  }

  return (
    <div>
      <div className="sm:flex sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Training Scenarios</h1>
          <p className="mt-2 text-sm text-gray-700">
            Pre-built cyber training scenarios ready to deploy to your ranges
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="mt-6 flex flex-col sm:flex-row gap-4">
        <input
          type="text"
          placeholder="Search scenarios..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="flex-1 rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
        />
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

      {filteredScenarios.length === 0 ? (
        <div className="mt-8 text-center">
          <AlertTriangle className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900">No scenarios found</h3>
          <p className="mt-1 text-sm text-gray-500">
            {searchQuery || categoryFilter
              ? 'Try adjusting your filters.'
              : 'Training scenarios will appear here once seeded.'}
          </p>
        </div>
      ) : (
        <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {filteredScenarios.map((scenario) => {
            const catConfig = categoryConfig[scenario.category]
            const diffConfig = difficultyConfig[scenario.difficulty]
            const CategoryIcon = catConfig.icon

            return (
              <div
                key={scenario.id}
                className="bg-white rounded-lg shadow overflow-hidden hover:shadow-md transition-shadow"
              >
                <div className="p-5">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center">
                      <div className={clsx("flex-shrink-0 rounded-md p-2", catConfig.bgColor)}>
                        <CategoryIcon className={clsx("h-6 w-6", catConfig.color)} />
                      </div>
                      <div className="ml-3">
                        <h3 className="text-sm font-medium text-gray-900">{scenario.name}</h3>
                        <span className={clsx("inline-block mt-1 text-xs px-2 py-0.5 rounded", diffConfig.color)}>
                          {diffConfig.label}
                        </span>
                      </div>
                    </div>
                  </div>

                  <p className="mt-3 text-sm text-gray-500 line-clamp-3">
                    {scenario.description}
                  </p>

                  <div className="mt-4 flex items-center text-xs text-gray-500 space-x-4">
                    <span className="flex items-center">
                      <Clock className="h-3.5 w-3.5 mr-1" />
                      {scenario.duration_minutes} min
                    </span>
                    <span className="flex items-center">
                      <Zap className="h-3.5 w-3.5 mr-1" />
                      {scenario.event_count} events
                    </span>
                  </div>

                  <div className="mt-3">
                    <p className="text-xs text-gray-400 mb-1">Required roles:</p>
                    <div className="flex flex-wrap gap-1">
                      {scenario.required_roles.map((role) => (
                        <span
                          key={role}
                          className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700"
                        >
                          {role}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="bg-gray-50 px-5 py-3">
                  <p className="text-xs text-gray-500">
                    Deploy this scenario from a Range's detail page
                  </p>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
