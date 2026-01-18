// frontend/src/pages/Admin.tsx
import { useEffect, useState } from 'react'
import { adminApi, usersApi, type CleanupResult, type DockerStatusResponse, type User, type RoleInfo, type UserAttribute, type AdminCreateUser } from '../services/api'
import { useAuthStore } from '../stores/authStore'
import {
  Shield,
  Loader2,
  Trash2,
  Plus,
  X,
  Tag,
  UserPlus,
  Clock,
  Check,
  Ban,
  Key,
  RefreshCw,
  Server,
  Network,
  AlertTriangle,
  Activity,
  Users,
  Settings,
  Container
} from 'lucide-react'
import clsx from 'clsx'

type TabType = 'system' | 'users'

export default function Admin() {
  const { user: currentUser } = useAuthStore()
  const [activeTab, setActiveTab] = useState<TabType>('system')

  // System tab state
  const [dockerStatus, setDockerStatus] = useState<DockerStatusResponse | null>(null)
  const [dockerLoading, setDockerLoading] = useState(false)
  const [cleanupLoading, setCleanupLoading] = useState(false)
  const [cleanupResult, setCleanupResult] = useState<CleanupResult | null>(null)
  const [showCleanupConfirm, setShowCleanupConfirm] = useState(false)
  const [cleanupOptions, setCleanupOptions] = useState({ clean_database: true, delete_database_records: false, force: false })

  // Users tab state
  const [users, setUsers] = useState<User[]>([])
  const [pendingUsers, setPendingUsers] = useState<User[]>([])
  const [roles, setRoles] = useState<RoleInfo[]>([])
  const [allTags, setAllTags] = useState<string[]>([])
  const [usersLoading, setUsersLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null)

  // Attribute editing state
  const [editingUserId, setEditingUserId] = useState<string | null>(null)
  const [userAttributes, setUserAttributes] = useState<UserAttribute[]>([])
  const [newTagInput, setNewTagInput] = useState('')
  const [attributeLoading, setAttributeLoading] = useState(false)

  // Create user modal state
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [createForm, setCreateForm] = useState<AdminCreateUser>({
    username: '',
    email: '',
    password: '',
    roles: ['engineer'],
    tags: [],
    is_approved: true
  })
  const [createLoading, setCreateLoading] = useState(false)

  const isAdmin = currentUser?.roles?.includes('admin') ?? false

  useEffect(() => {
    if (isAdmin) {
      fetchDockerStatus()
      fetchUsersData()
    }
  }, [isAdmin])

  // System functions
  const fetchDockerStatus = async () => {
    try {
      setDockerLoading(true)
      const res = await adminApi.getDockerStatus()
      setDockerStatus(res.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load Docker status')
    } finally {
      setDockerLoading(false)
    }
  }

  const handleCleanup = async () => {
    try {
      setCleanupLoading(true)
      setCleanupResult(null)
      const res = await adminApi.cleanupAll(cleanupOptions)
      setCleanupResult(res.data)
      setShowCleanupConfirm(false)
      setSuccessMessage('Cleanup completed successfully')
      // Refresh Docker status
      fetchDockerStatus()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Cleanup failed')
    } finally {
      setCleanupLoading(false)
    }
  }

  // Users functions
  const fetchUsersData = async () => {
    try {
      setUsersLoading(true)
      const [usersRes, pendingRes, rolesRes, tagsRes] = await Promise.all([
        usersApi.list(),
        usersApi.listPending(),
        usersApi.getAvailableRoles(),
        usersApi.getAllTags()
      ])
      setUsers(usersRes.data.filter(u => u.is_approved))
      setPendingUsers(pendingRes.data)
      setRoles(rolesRes.data)
      setAllTags(tagsRes.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load users')
    } finally {
      setUsersLoading(false)
    }
  }

  const handleEditUser = async (userId: string) => {
    try {
      setAttributeLoading(true)
      const res = await usersApi.getAttributes(userId)
      setUserAttributes(res.data)
      setEditingUserId(userId)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load user attributes')
    } finally {
      setAttributeLoading(false)
    }
  }

  const handleAddRole = async (userId: string, role: string) => {
    try {
      setAttributeLoading(true)
      await usersApi.addAttribute(userId, { attribute_type: 'role', attribute_value: role })
      const [usersRes, attrsRes] = await Promise.all([
        usersApi.list(),
        usersApi.getAttributes(userId)
      ])
      setUsers(usersRes.data.filter(u => u.is_approved))
      setUserAttributes(attrsRes.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to add role')
    } finally {
      setAttributeLoading(false)
    }
  }

  const handleRemoveAttribute = async (userId: string, attributeId: string) => {
    try {
      setAttributeLoading(true)
      await usersApi.removeAttribute(userId, attributeId)
      const [usersRes, attrsRes] = await Promise.all([
        usersApi.list(),
        usersApi.getAttributes(userId)
      ])
      setUsers(usersRes.data.filter(u => u.is_approved))
      setUserAttributes(attrsRes.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to remove attribute')
    } finally {
      setAttributeLoading(false)
    }
  }

  const handleAddTag = async (userId: string) => {
    if (!newTagInput.trim()) return
    try {
      setAttributeLoading(true)
      await usersApi.addAttribute(userId, { attribute_type: 'tag', attribute_value: newTagInput.trim() })
      setNewTagInput('')
      const [usersRes, attrsRes, tagsRes] = await Promise.all([
        usersApi.list(),
        usersApi.getAttributes(userId),
        usersApi.getAllTags()
      ])
      setUsers(usersRes.data.filter(u => u.is_approved))
      setUserAttributes(attrsRes.data)
      setAllTags(tagsRes.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to add tag')
    } finally {
      setAttributeLoading(false)
    }
  }

  const handleToggleActive = async (userId: string, isActive: boolean) => {
    try {
      await usersApi.update(userId, { is_active: isActive })
      setUsers(users.map(u => u.id === userId ? { ...u, is_active: isActive } : u))
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to update user status')
    }
  }

  const handleDelete = async (userId: string) => {
    try {
      await usersApi.delete(userId)
      setUsers(users.filter(u => u.id !== userId))
      setDeleteConfirmId(null)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete user')
    }
  }

  const handleApprove = async (userId: string) => {
    try {
      await usersApi.approve(userId)
      setSuccessMessage('User approved successfully')
      fetchUsersData()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to approve user')
    }
  }

  const handleDeny = async (userId: string) => {
    try {
      await usersApi.deny(userId)
      setSuccessMessage('User registration denied')
      setPendingUsers(pendingUsers.filter(u => u.id !== userId))
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to deny user')
    }
  }

  const handleResetPassword = async (userId: string) => {
    try {
      await usersApi.resetPassword(userId)
      setSuccessMessage('Password reset flag set. User will be prompted to change password on next login.')
      fetchUsersData()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to reset password')
    }
  }

  const handleCreateUser = async () => {
    try {
      setCreateLoading(true)
      await usersApi.create(createForm)
      setSuccessMessage('User created successfully')
      setShowCreateModal(false)
      setCreateForm({
        username: '',
        email: '',
        password: '',
        roles: ['engineer'],
        tags: [],
        is_approved: true
      })
      fetchUsersData()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create user')
    } finally {
      setCreateLoading(false)
    }
  }

  const generateRandomPassword = () => {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*'
    let password = ''
    for (let i = 0; i < 16; i++) {
      password += chars.charAt(Math.floor(Math.random() * chars.length))
    }
    setCreateForm({ ...createForm, password })
  }

  const getRoleBadgeColor = (role: string) => {
    switch (role) {
      case 'admin': return 'bg-red-100 text-red-800'
      case 'engineer': return 'bg-blue-100 text-blue-800'
      case 'facilitator': return 'bg-green-100 text-green-800'
      case 'evaluator': return 'bg-purple-100 text-purple-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  if (!isAdmin) {
    return (
      <div className="text-center py-12">
        <Shield className="mx-auto h-12 w-12 text-gray-400" />
        <h3 className="mt-2 text-sm font-medium text-gray-900">Access Denied</h3>
        <p className="mt-1 text-sm text-gray-500">
          You need administrator privileges to access this page.
        </p>
      </div>
    )
  }

  const editingUser = editingUserId ? users.find(u => u.id === editingUserId) : null
  const userRoleAttrs = userAttributes.filter(a => a.attribute_type === 'role')
  const userTagAttrs = userAttributes.filter(a => a.attribute_type === 'tag')
  const availableRolesToAdd = roles.filter(r => !userRoleAttrs.some(a => a.attribute_value === r.value))

  return (
    <div>
      <div className="sm:flex sm:items-center">
        <div className="sm:flex-auto">
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Settings className="h-7 w-7" />
            Administration
          </h1>
          <p className="mt-2 text-sm text-gray-700">
            System management, cleanup operations, and user administration.
          </p>
        </div>
      </div>

      {/* Error/Success Messages */}
      {error && (
        <div className="mt-4 rounded-md bg-red-50 p-4">
          <div className="flex">
            <X className="h-5 w-5 text-red-400" />
            <p className="ml-3 text-sm text-red-700">{error}</p>
            <button onClick={() => setError(null)} className="ml-auto text-red-500 hover:text-red-700">
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>
      )}

      {successMessage && (
        <div className="mt-4 rounded-md bg-green-50 p-4">
          <div className="flex">
            <Check className="h-5 w-5 text-green-400" />
            <p className="ml-3 text-sm text-green-700">{successMessage}</p>
            <button onClick={() => setSuccessMessage(null)} className="ml-auto text-green-500 hover:text-green-700">
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="mt-6 border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('system')}
            className={clsx(
              'flex items-center gap-2 py-4 px-1 border-b-2 font-medium text-sm',
              activeTab === 'system'
                ? 'border-primary-500 text-primary-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            )}
          >
            <Activity className="h-5 w-5" />
            System
          </button>
          <button
            onClick={() => setActiveTab('users')}
            className={clsx(
              'flex items-center gap-2 py-4 px-1 border-b-2 font-medium text-sm',
              activeTab === 'users'
                ? 'border-primary-500 text-primary-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            )}
          >
            <Users className="h-5 w-5" />
            Users
            {pendingUsers.length > 0 && (
              <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800">
                {pendingUsers.length}
              </span>
            )}
          </button>
        </nav>
      </div>

      {/* Tab Content */}
      <div className="mt-6">
        {activeTab === 'system' && (
          <div className="space-y-6">
            {/* Docker Status */}
            <div className="bg-white shadow rounded-lg">
              <div className="px-4 py-5 sm:px-6 border-b border-gray-200">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-medium text-gray-900 flex items-center gap-2">
                    <Container className="h-5 w-5" />
                    Docker Status
                  </h3>
                  <button
                    onClick={fetchDockerStatus}
                    disabled={dockerLoading}
                    className="inline-flex items-center px-3 py-1.5 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
                  >
                    <RefreshCw className={clsx('h-4 w-4 mr-2', dockerLoading && 'animate-spin')} />
                    Refresh
                  </button>
                </div>
              </div>
              <div className="px-4 py-5 sm:p-6">
                {dockerLoading && !dockerStatus ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
                  </div>
                ) : dockerStatus ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* Containers */}
                    <div>
                      <h4 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
                        <Server className="h-4 w-4" />
                        CYROID Containers ({dockerStatus.container_count})
                      </h4>
                      {dockerStatus.containers.length > 0 ? (
                        <ul className="space-y-2 max-h-64 overflow-y-auto">
                          {dockerStatus.containers.map((container, idx) => (
                            <li key={idx} className="flex items-center justify-between py-2 px-3 bg-gray-50 rounded-md text-sm">
                              <span className="font-mono text-xs truncate">{container.name}</span>
                              <span className={clsx(
                                'px-2 py-0.5 rounded-full text-xs',
                                container.status === 'running' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                              )}>
                                {container.status}
                              </span>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-sm text-gray-500">No CYROID containers running</p>
                      )}
                    </div>
                    {/* Networks */}
                    <div>
                      <h4 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
                        <Network className="h-4 w-4" />
                        CYROID Networks ({dockerStatus.network_count})
                      </h4>
                      {dockerStatus.networks.length > 0 ? (
                        <ul className="space-y-2 max-h-64 overflow-y-auto">
                          {dockerStatus.networks.map((network, idx) => (
                            <li key={idx} className="flex items-center justify-between py-2 px-3 bg-gray-50 rounded-md text-sm">
                              <span className="font-mono text-xs truncate">{network.name}</span>
                              <span className="text-xs text-gray-500">{network.id}</span>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-sm text-gray-500">No CYROID networks</p>
                      )}
                    </div>
                  </div>
                ) : null}
              </div>
            </div>

            {/* Cleanup Section */}
            <div className="bg-white shadow rounded-lg">
              <div className="px-4 py-5 sm:px-6 border-b border-gray-200">
                <h3 className="text-lg font-medium text-gray-900 flex items-center gap-2">
                  <Trash2 className="h-5 w-5 text-red-500" />
                  System Cleanup
                </h3>
                <p className="mt-1 text-sm text-gray-500">
                  Remove all CYROID range resources (containers, networks, database records).
                </p>
              </div>
              <div className="px-4 py-5 sm:p-6">
                {cleanupResult && (
                  <div className="mb-6 p-4 bg-gray-50 rounded-lg">
                    <h4 className="text-sm font-medium text-gray-900 mb-2">Cleanup Results</h4>
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                      <div>
                        <span className="text-gray-500">Ranges cleaned:</span>
                        <span className="ml-2 font-medium">{cleanupResult.ranges_cleaned}</span>
                      </div>
                      <div>
                        <span className="text-gray-500">Containers removed:</span>
                        <span className="ml-2 font-medium">{cleanupResult.containers_removed}</span>
                      </div>
                      <div>
                        <span className="text-gray-500">Networks removed:</span>
                        <span className="ml-2 font-medium">{cleanupResult.networks_removed}</span>
                      </div>
                      <div>
                        <span className="text-gray-500">DB records updated:</span>
                        <span className="ml-2 font-medium">{cleanupResult.database_records_updated}</span>
                      </div>
                      <div>
                        <span className="text-gray-500">DB records deleted:</span>
                        <span className="ml-2 font-medium">{cleanupResult.database_records_deleted}</span>
                      </div>
                      <div>
                        <span className="text-gray-500">Orphaned resources:</span>
                        <span className="ml-2 font-medium">{cleanupResult.orphaned_resources_cleaned}</span>
                      </div>
                    </div>
                    {cleanupResult.errors.length > 0 && (
                      <div className="mt-4">
                        <h5 className="text-sm font-medium text-red-700">Errors:</h5>
                        <ul className="mt-1 text-sm text-red-600 list-disc list-inside">
                          {cleanupResult.errors.map((err, idx) => (
                            <li key={idx}>{err}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}

                <div className="space-y-4">
                  <div className="flex flex-col gap-3">
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={cleanupOptions.clean_database}
                        onChange={(e) => setCleanupOptions({ ...cleanupOptions, clean_database: e.target.checked, delete_database_records: false })}
                        disabled={cleanupOptions.delete_database_records}
                        className="rounded border-gray-300 text-primary-600 focus:ring-primary-500 disabled:opacity-50"
                      />
                      <span className="text-sm text-gray-700">Reset database records (resets ranges to draft state)</span>
                    </label>
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={cleanupOptions.delete_database_records}
                        onChange={(e) => setCleanupOptions({ ...cleanupOptions, delete_database_records: e.target.checked, clean_database: !e.target.checked })}
                        className="rounded border-gray-300 text-red-600 focus:ring-red-500"
                      />
                      <span className="text-sm text-red-700 font-medium">Delete ALL ranges from database (permanent)</span>
                    </label>
                  </div>

                  <div className="flex items-center gap-4">
                    <button
                      onClick={() => setShowCleanupConfirm(true)}
                      disabled={cleanupLoading}
                      className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50"
                    >
                      {cleanupLoading ? (
                        <>
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          Cleaning up...
                        </>
                      ) : (
                        <>
                          <Trash2 className="h-4 w-4 mr-2" />
                          Cleanup All Resources
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* Cleanup Confirmation Modal */}
            {showCleanupConfirm && (
              <div className="fixed inset-0 z-50 overflow-y-auto">
                <div className="flex items-center justify-center min-h-screen px-4">
                  <div className="fixed inset-0 bg-gray-500 bg-opacity-75" onClick={() => setShowCleanupConfirm(false)} />
                  <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full p-6">
                    <div className="flex items-center gap-4 mb-4">
                      <div className="flex-shrink-0 h-12 w-12 rounded-full bg-red-100 flex items-center justify-center">
                        <AlertTriangle className="h-6 w-6 text-red-600" />
                      </div>
                      <div>
                        <h3 className="text-lg font-medium text-gray-900">Confirm Cleanup</h3>
                        <p className="text-sm text-gray-500">This action cannot be undone.</p>
                      </div>
                    </div>

                    <div className="bg-red-50 border border-red-200 rounded-md p-4 mb-6">
                      <p className="text-sm text-red-700">
                        This will remove <strong>ALL</strong> CYROID range resources:
                      </p>
                      <ul className="mt-2 text-sm text-red-700 list-disc list-inside">
                        <li>Stop and remove all VM containers</li>
                        <li>Remove all range networks</li>
                        {cleanupOptions.delete_database_records ? (
                          <li className="font-bold">DELETE all ranges, VMs, and networks from database (PERMANENT)</li>
                        ) : cleanupOptions.clean_database && (
                          <li>Reset all database records to draft state</li>
                        )}
                      </ul>
                    </div>

                    <div className="flex justify-end gap-3">
                      <button
                        onClick={() => setShowCleanupConfirm(false)}
                        className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={handleCleanup}
                        disabled={cleanupLoading}
                        className="px-4 py-2 text-sm font-medium text-white bg-red-600 border border-transparent rounded-md hover:bg-red-700 disabled:opacity-50"
                      >
                        {cleanupLoading ? 'Cleaning...' : 'Yes, Clean Everything'}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'users' && (
          <div>
            {/* Create User Button */}
            <div className="mb-6 flex justify-end">
              <button
                onClick={() => setShowCreateModal(true)}
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
              >
                <UserPlus className="h-4 w-4 mr-2" />
                Create User
              </button>
            </div>

            {/* Role descriptions */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-6">
              {roles.map((role) => (
                <div key={role.value} className="bg-white overflow-hidden shadow rounded-lg p-4">
                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getRoleBadgeColor(role.value)}`}>
                    {role.label}
                  </span>
                  <p className="mt-2 text-sm text-gray-500">{role.description}</p>
                </div>
              ))}
            </div>

            {/* Pending Approvals Section */}
            {pendingUsers.length > 0 && (
              <div className="mb-8">
                <div className="flex items-center mb-4">
                  <Clock className="h-5 w-5 text-amber-500 mr-2" />
                  <h2 className="text-lg font-semibold text-gray-900">Pending Approvals ({pendingUsers.length})</h2>
                </div>
                <div className="bg-amber-50 border border-amber-200 rounded-lg overflow-hidden">
                  <ul className="divide-y divide-amber-200">
                    {pendingUsers.map((user) => (
                      <li key={user.id} className="px-4 py-4 sm:px-6">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center">
                            <div className="h-10 w-10 flex-shrink-0 rounded-full bg-amber-100 flex items-center justify-center">
                              <Users className="h-5 w-5 text-amber-600" />
                            </div>
                            <div className="ml-4">
                              <div className="font-medium text-gray-900">{user.username}</div>
                              <div className="text-sm text-gray-500">{user.email}</div>
                              <div className="text-xs text-gray-400">Registered: {new Date(user.created_at).toLocaleDateString()}</div>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => handleApprove(user.id)}
                              className="inline-flex items-center px-3 py-1.5 border border-transparent text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700"
                            >
                              <Check className="h-4 w-4 mr-1" />
                              Approve
                            </button>
                            <button
                              onClick={() => handleDeny(user.id)}
                              className="inline-flex items-center px-3 py-1.5 border border-transparent text-sm font-medium rounded-md text-white bg-red-600 hover:bg-red-700"
                            >
                              <Ban className="h-4 w-4 mr-1" />
                              Deny
                            </button>
                          </div>
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            )}

            {/* Users table */}
            {usersLoading ? (
              <div className="flex items-center justify-center h-64">
                <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
              </div>
            ) : (
              <div className="flex flex-col">
                <div className="-my-2 -mx-4 overflow-x-auto sm:-mx-6 lg:-mx-8">
                  <div className="inline-block min-w-full py-2 align-middle md:px-6 lg:px-8">
                    <div className="overflow-hidden shadow ring-1 ring-black ring-opacity-5 md:rounded-lg">
                      <table className="min-w-full divide-y divide-gray-300">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-gray-900 sm:pl-6">User</th>
                            <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Roles</th>
                            <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Tags</th>
                            <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Status</th>
                            <th className="relative py-3.5 pl-3 pr-4 sm:pr-6"><span className="sr-only">Actions</span></th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-200 bg-white">
                          {users.map((user) => (
                            <tr key={user.id}>
                              <td className="whitespace-nowrap py-4 pl-4 pr-3 text-sm sm:pl-6">
                                <div className="flex items-center">
                                  <div className="h-10 w-10 flex-shrink-0 rounded-full bg-primary-100 flex items-center justify-center">
                                    <Users className="h-5 w-5 text-primary-600" />
                                  </div>
                                  <div className="ml-4">
                                    <div className="font-medium text-gray-900">
                                      {user.username}
                                      {user.id === currentUser?.id && <span className="ml-2 text-xs text-gray-500">(you)</span>}
                                    </div>
                                    <div className="text-gray-500">{user.email}</div>
                                  </div>
                                </div>
                              </td>
                              <td className="px-3 py-4 text-sm">
                                <div className="flex flex-wrap gap-1">
                                  {user.roles?.map((role) => (
                                    <span key={role} className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${getRoleBadgeColor(role)}`}>
                                      {role}
                                    </span>
                                  )) || <span className="text-gray-400">-</span>}
                                </div>
                              </td>
                              <td className="px-3 py-4 text-sm">
                                <div className="flex flex-wrap gap-1 max-w-xs">
                                  {user.tags?.slice(0, 3).map((tag) => (
                                    <span key={tag} className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700">
                                      {tag}
                                    </span>
                                  ))}
                                  {(user.tags?.length || 0) > 3 && (
                                    <span className="text-xs text-gray-500">+{user.tags!.length - 3}</span>
                                  )}
                                  {(!user.tags || user.tags.length === 0) && <span className="text-gray-400">-</span>}
                                </div>
                              </td>
                              <td className="whitespace-nowrap px-3 py-4 text-sm">
                                <div className="flex flex-col gap-1">
                                  <button
                                    onClick={() => user.id !== currentUser?.id && handleToggleActive(user.id, !user.is_active)}
                                    disabled={user.id === currentUser?.id}
                                    className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                                      user.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                                    } ${user.id !== currentUser?.id ? 'cursor-pointer hover:opacity-80' : 'cursor-not-allowed'}`}
                                  >
                                    {user.is_active ? 'Active' : 'Inactive'}
                                  </button>
                                  {user.password_reset_required && (
                                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800">
                                      <Key className="h-3 w-3 mr-1" />
                                      Password Reset
                                    </span>
                                  )}
                                </div>
                              </td>
                              <td className="relative whitespace-nowrap py-4 pl-3 pr-4 text-right text-sm font-medium sm:pr-6">
                                <div className="flex items-center justify-end gap-2">
                                  <button
                                    onClick={() => handleEditUser(user.id)}
                                    className="text-primary-600 hover:text-primary-900"
                                  >
                                    Edit
                                  </button>
                                  {user.id !== currentUser?.id && (
                                    <button
                                      onClick={() => handleResetPassword(user.id)}
                                      className="text-amber-600 hover:text-amber-900"
                                      title="Force password reset on next login"
                                    >
                                      <Key className="h-4 w-4" />
                                    </button>
                                  )}
                                  {deleteConfirmId === user.id ? (
                                    <div className="flex items-center gap-1">
                                      <button onClick={() => handleDelete(user.id)} className="text-red-600 hover:text-red-900">Yes</button>
                                      <button onClick={() => setDeleteConfirmId(null)} className="text-gray-400 hover:text-gray-600">No</button>
                                    </div>
                                  ) : (
                                    <button
                                      onClick={() => setDeleteConfirmId(user.id)}
                                      disabled={user.id === currentUser?.id}
                                      className={`text-red-600 hover:text-red-900 ${user.id === currentUser?.id ? 'opacity-50 cursor-not-allowed' : ''}`}
                                    >
                                      <Trash2 className="h-4 w-4" />
                                    </button>
                                  )}
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Create User Modal */}
            {showCreateModal && (
              <div className="fixed inset-0 z-50 overflow-y-auto">
                <div className="flex items-center justify-center min-h-screen px-4">
                  <div className="fixed inset-0 bg-gray-500 bg-opacity-75" onClick={() => setShowCreateModal(false)} />
                  <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full p-6">
                    <div className="flex justify-between items-center mb-4">
                      <h3 className="text-lg font-medium text-gray-900">Create New User</h3>
                      <button onClick={() => setShowCreateModal(false)} className="text-gray-400 hover:text-gray-600">
                        <X className="h-5 w-5" />
                      </button>
                    </div>

                    <div className="space-y-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700">Username</label>
                        <input
                          type="text"
                          value={createForm.username}
                          onChange={(e) => setCreateForm({ ...createForm, username: e.target.value })}
                          className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm px-3 py-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
                          placeholder="Enter username"
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700">Email</label>
                        <input
                          type="email"
                          value={createForm.email}
                          onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })}
                          className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm px-3 py-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
                          placeholder="user@example.com"
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700">Password</label>
                        <div className="mt-1 flex gap-2">
                          <input
                            type="text"
                            value={createForm.password}
                            onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })}
                            className="block flex-1 border border-gray-300 rounded-md shadow-sm px-3 py-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
                            placeholder="Enter or generate password"
                          />
                          <button
                            type="button"
                            onClick={generateRandomPassword}
                            className="px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-700 hover:bg-gray-50"
                            title="Generate random password"
                          >
                            <RefreshCw className="h-4 w-4" />
                          </button>
                        </div>
                        <p className="mt-1 text-xs text-gray-500">User will be required to change password on first login.</p>
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700">Roles</label>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {roles.map((role) => (
                            <label key={role.value} className="inline-flex items-center">
                              <input
                                type="checkbox"
                                checked={createForm.roles?.includes(role.value) ?? false}
                                onChange={(e) => {
                                  const newRoles = e.target.checked
                                    ? [...(createForm.roles || []), role.value]
                                    : (createForm.roles || []).filter(r => r !== role.value)
                                  setCreateForm({ ...createForm, roles: newRoles })
                                }}
                                className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                              />
                              <span className={`ml-2 text-sm ${getRoleBadgeColor(role.value)} px-2 py-0.5 rounded-full`}>
                                {role.label}
                              </span>
                            </label>
                          ))}
                        </div>
                      </div>
                    </div>

                    <div className="mt-6 flex justify-end gap-3">
                      <button
                        onClick={() => setShowCreateModal(false)}
                        className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={handleCreateUser}
                        disabled={createLoading || !createForm.username || !createForm.email || !createForm.password}
                        className="px-4 py-2 text-sm font-medium text-white bg-primary-600 border border-transparent rounded-md hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {createLoading ? 'Creating...' : 'Create User'}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* User Attribute Editor Modal */}
            {editingUser && (
              <div className="fixed inset-0 z-50 overflow-y-auto">
                <div className="flex items-center justify-center min-h-screen px-4">
                  <div className="fixed inset-0 bg-gray-500 bg-opacity-75" onClick={() => setEditingUserId(null)} />
                  <div className="relative bg-white rounded-lg shadow-xl max-w-lg w-full p-6">
                    <div className="flex justify-between items-center mb-4">
                      <h3 className="text-lg font-medium text-gray-900">Edit {editingUser.username}</h3>
                      <button onClick={() => setEditingUserId(null)} className="text-gray-400 hover:text-gray-600">
                        <X className="h-5 w-5" />
                      </button>
                    </div>

                    {attributeLoading && (
                      <div className="flex items-center justify-center py-4">
                        <Loader2 className="h-6 w-6 animate-spin text-primary-600" />
                      </div>
                    )}

                    {/* Roles Section */}
                    <div className="mb-6">
                      <h4 className="text-sm font-medium text-gray-700 mb-2">Roles</h4>
                      <div className="flex flex-wrap gap-2 mb-2">
                        {userRoleAttrs.map((attr) => (
                          <span key={attr.id} className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getRoleBadgeColor(attr.attribute_value)}`}>
                            {attr.attribute_value}
                            {!(editingUser.id === currentUser?.id && attr.attribute_value === 'admin') && (
                              <button
                                onClick={() => handleRemoveAttribute(editingUser.id, attr.id)}
                                className="ml-1 hover:text-red-600"
                                disabled={attributeLoading}
                              >
                                <X className="h-3 w-3" />
                              </button>
                            )}
                          </span>
                        ))}
                        {userRoleAttrs.length === 0 && (
                          <span className="text-sm text-gray-500">No roles assigned</span>
                        )}
                      </div>
                      {availableRolesToAdd.length > 0 && (
                        <div className="flex gap-2">
                          {availableRolesToAdd.map((role) => (
                            <button
                              key={role.value}
                              onClick={() => handleAddRole(editingUser.id, role.value)}
                              disabled={attributeLoading}
                              className="inline-flex items-center px-2 py-1 text-xs border border-dashed border-gray-300 rounded hover:border-gray-400 hover:bg-gray-50"
                            >
                              <Plus className="h-3 w-3 mr-1" />
                              {role.label}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Tags Section */}
                    <div>
                      <h4 className="text-sm font-medium text-gray-700 mb-2">Tags</h4>
                      <div className="flex flex-wrap gap-2 mb-2">
                        {userTagAttrs.map((attr) => (
                          <span key={attr.id} className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                            <Tag className="h-3 w-3 mr-1" />
                            {attr.attribute_value}
                            <button
                              onClick={() => handleRemoveAttribute(editingUser.id, attr.id)}
                              className="ml-1 hover:text-red-600"
                              disabled={attributeLoading}
                            >
                              <X className="h-3 w-3" />
                            </button>
                          </span>
                        ))}
                        {userTagAttrs.length === 0 && (
                          <span className="text-sm text-gray-500">No tags assigned</span>
                        )}
                      </div>
                      <div className="flex gap-2">
                        <input
                          type="text"
                          value={newTagInput}
                          onChange={(e) => setNewTagInput(e.target.value)}
                          onKeyDown={(e) => e.key === 'Enter' && handleAddTag(editingUser.id)}
                          placeholder="Add tag (e.g., team:red-team)"
                          className="flex-1 text-sm border border-gray-300 rounded-md px-3 py-1.5 focus:ring-primary-500 focus:border-primary-500"
                          list="tag-suggestions"
                        />
                        <datalist id="tag-suggestions">
                          {allTags.filter(t => !userTagAttrs.some(a => a.attribute_value === t)).map(tag => (
                            <option key={tag} value={tag} />
                          ))}
                        </datalist>
                        <button
                          onClick={() => handleAddTag(editingUser.id)}
                          disabled={!newTagInput.trim() || attributeLoading}
                          className="px-3 py-1.5 bg-primary-600 text-white text-sm rounded-md hover:bg-primary-700 disabled:opacity-50"
                        >
                          Add
                        </button>
                      </div>
                      <p className="mt-2 text-xs text-gray-500">
                        Tags control resource visibility. Format: category:value (e.g., team:blue-team, role:analyst)
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
