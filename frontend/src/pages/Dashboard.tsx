// frontend/src/pages/Dashboard.tsx
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import { rangesApi } from '../services/api'
import type { Range } from '../types'
import { Network, Plus, Loader2, GraduationCap } from 'lucide-react'

export default function Dashboard() {
  const { user } = useAuthStore()
  const [ranges, setRanges] = useState<Range[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const rangesRes = await rangesApi.list()
        setRanges(rangesRes.data)
      } catch (error) {
        console.error('Failed to fetch dashboard data:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  const runningVMs = ranges.reduce((count, range) => {
    return count + (range.vms?.filter(vm => vm.status === 'running').length || 0)
  }, 0)

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    )
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
      <p className="mt-2 text-gray-600">
        Welcome back, {user?.username}!
      </p>

      <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {/* Stats cards */}
        <Link to="/ranges" className="bg-white overflow-hidden shadow rounded-lg hover:shadow-md transition-shadow cursor-pointer">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <div className="rounded-md bg-primary-100 p-3">
                  <Network className="h-6 w-6 text-primary-600" />
                </div>
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">Total Ranges</dt>
                  <dd className="text-2xl font-semibold text-gray-900">{ranges.length}</dd>
                </dl>
              </div>
            </div>
          </div>
        </Link>

        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <div className="rounded-md bg-green-100 p-3">
                  <svg className="h-6 w-6 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">Running VMs</dt>
                  <dd className="text-2xl font-semibold text-gray-900">{runningVMs}</dd>
                </dl>
              </div>
            </div>
          </div>
        </div>

      </div>

      <div className="mt-8">
        <h2 className="text-lg font-medium text-gray-900">Quick Actions</h2>
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Link
            to="/ranges"
            className="relative rounded-lg border border-gray-300 bg-white px-6 py-5 shadow-sm flex items-center space-x-3 hover:border-gray-400 focus-within:ring-2 focus-within:ring-offset-2 focus-within:ring-primary-500"
          >
            <div className="flex-shrink-0">
              <div className="rounded-md bg-primary-100 p-3">
                <Plus className="h-6 w-6 text-primary-600" />
              </div>
            </div>
            <div className="flex-1 min-w-0">
              <span className="absolute inset-0" aria-hidden="true" />
              <p className="text-sm font-medium text-gray-900">Create New Range</p>
              <p className="text-sm text-gray-500">Set up a new cyber training environment</p>
            </div>
          </Link>

          {/* Student Portal - Coming Soon */}
          <div
            className="relative rounded-lg border border-gray-200 bg-gray-50 px-6 py-5 shadow-sm flex items-center space-x-3 cursor-not-allowed opacity-60"
            title="Student Portal will be available in a future release"
          >
            <div className="flex-shrink-0">
              <div className="rounded-md bg-purple-100 p-3">
                <GraduationCap className="h-6 w-6 text-purple-600" />
              </div>
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <p className="text-sm font-medium text-gray-900">Student Portal</p>
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-800">
                  Coming Soon
                </span>
              </div>
              <p className="text-sm text-gray-500">Access your assigned labs, submit evidence, and view progress</p>
            </div>
          </div>

        </div>
      </div>

      {/* Recent Ranges */}
      {ranges.length > 0 && (
        <div className="mt-8">
          <h2 className="text-lg font-medium text-gray-900">Recent Ranges</h2>
          <div className="mt-4 bg-white shadow overflow-hidden sm:rounded-md">
            <ul className="divide-y divide-gray-200">
              {ranges.slice(0, 5).map((range) => (
                <li key={range.id}>
                  <Link to={`/ranges/${range.id}`} className="block hover:bg-gray-50">
                    <div className="px-4 py-4 sm:px-6">
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-medium text-primary-600 truncate">{range.name}</p>
                        <div className="ml-2 flex-shrink-0 flex">
                          <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                            range.status === 'running' ? 'bg-green-100 text-green-800' :
                            range.status === 'stopped' ? 'bg-gray-100 text-gray-800' :
                            range.status === 'error' ? 'bg-red-100 text-red-800' :
                            'bg-yellow-100 text-yellow-800'
                          }`}>
                            {range.status}
                          </span>
                        </div>
                      </div>
                      <div className="mt-2 sm:flex sm:justify-between">
                        <div className="sm:flex">
                          <p className="text-sm text-gray-500">
                            {range.description || 'No description'}
                          </p>
                        </div>
                      </div>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  )
}
