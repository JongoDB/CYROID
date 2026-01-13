// frontend/src/pages/UserManagement.tsx
import { useEffect, useState } from 'react'
import { usersApi, type User, type RoleInfo, type UserAttribute } from '../services/api'
import { useAuthStore } from '../stores/authStore'
import { Users, Shield, Loader2, Trash2, Plus, X, Tag } from 'lucide-react'

export default function UserManagement() {
  const { user: currentUser } = useAuthStore()
  const [users, setUsers] = useState<User[]>([])
  const [roles, setRoles] = useState<RoleInfo[]>([])
  const [allTags, setAllTags] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null)

  // Attribute editing state
  const [editingUserId, setEditingUserId] = useState<string | null>(null)
  const [userAttributes, setUserAttributes] = useState<UserAttribute[]>([])
  const [newTagInput, setNewTagInput] = useState('')
  const [attributeLoading, setAttributeLoading] = useState(false)

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      setLoading(true)
      const [usersRes, rolesRes, tagsRes] = await Promise.all([
        usersApi.list(),
        usersApi.getAvailableRoles(),
        usersApi.getAllTags()
      ])
      setUsers(usersRes.data)
      setRoles(rolesRes.data)
      setAllTags(tagsRes.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load users')
    } finally {
      setLoading(false)
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
      // Refresh user data and attributes
      const [usersRes, attrsRes] = await Promise.all([
        usersApi.list(),
        usersApi.getAttributes(userId)
      ])
      setUsers(usersRes.data)
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
      // Refresh
      const [usersRes, attrsRes] = await Promise.all([
        usersApi.list(),
        usersApi.getAttributes(userId)
      ])
      setUsers(usersRes.data)
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
      // Refresh
      const [usersRes, attrsRes, tagsRes] = await Promise.all([
        usersApi.list(),
        usersApi.getAttributes(userId),
        usersApi.getAllTags()
      ])
      setUsers(usersRes.data)
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

  const getRoleBadgeColor = (role: string) => {
    switch (role) {
      case 'admin': return 'bg-red-100 text-red-800'
      case 'engineer': return 'bg-blue-100 text-blue-800'
      case 'facilitator': return 'bg-green-100 text-green-800'
      case 'evaluator': return 'bg-purple-100 text-purple-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  const isAdmin = currentUser?.roles?.includes('admin') ?? false

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    )
  }

  if (!isAdmin) {
    return (
      <div className="text-center py-12">
        <Shield className="mx-auto h-12 w-12 text-gray-400" />
        <h3 className="mt-2 text-sm font-medium text-gray-900">Access Denied</h3>
        <p className="mt-1 text-sm text-gray-500">
          You need administrator privileges to access user management.
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
          <h1 className="text-2xl font-bold text-gray-900">User Management</h1>
          <p className="mt-2 text-sm text-gray-700">
            Manage user accounts, roles, and tags using Attribute-Based Access Control (ABAC).
          </p>
        </div>
      </div>

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

      {/* Role descriptions */}
      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {roles.map((role) => (
          <div key={role.value} className="bg-white overflow-hidden shadow rounded-lg p-4">
            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getRoleBadgeColor(role.value)}`}>
              {role.label}
            </span>
            <p className="mt-2 text-sm text-gray-500">{role.description}</p>
          </div>
        ))}
      </div>

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

      {/* Users table */}
      <div className="mt-8 flex flex-col">
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
                        <button
                          onClick={() => user.id !== currentUser?.id && handleToggleActive(user.id, !user.is_active)}
                          disabled={user.id === currentUser?.id}
                          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                            user.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                          } ${user.id !== currentUser?.id ? 'cursor-pointer hover:opacity-80' : 'cursor-not-allowed'}`}
                        >
                          {user.is_active ? 'Active' : 'Inactive'}
                        </button>
                      </td>
                      <td className="relative whitespace-nowrap py-4 pl-3 pr-4 text-right text-sm font-medium sm:pr-6">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => handleEditUser(user.id)}
                            className="text-primary-600 hover:text-primary-900"
                          >
                            Edit
                          </button>
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
    </div>
  )
}
