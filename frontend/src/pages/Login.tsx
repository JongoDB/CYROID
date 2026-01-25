// frontend/src/pages/Login.tsx
import { useState, FormEvent, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import { getLandingPage } from '../utils/roleUtils'
import PasswordChangeModal from '../components/common/PasswordChangeModal'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPasswordModal, setShowPasswordModal] = useState(false)
  const { login, isLoading, error, clearError, passwordResetRequired } = useAuthStore()
  const navigate = useNavigate()

  // Check if password reset is required after login
  useEffect(() => {
    if (passwordResetRequired) {
      setShowPasswordModal(true)
    }
  }, [passwordResetRequired])

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    try {
      await login({ username, password })
      // If password reset is required, the useEffect will show the modal
      // Otherwise, navigate to role-appropriate landing page
      const state = useAuthStore.getState()
      if (!state.passwordResetRequired) {
        const effectiveRole = state.getEffectiveRole()
        const landingPage = getLandingPage(effectiveRole)
        navigate(landingPage)
      }
    } catch {
      // Error is handled by store
    }
  }

  const handlePasswordChangeComplete = () => {
    setShowPasswordModal(false)
    const state = useAuthStore.getState()
    const effectiveRole = state.getEffectiveRole()
    const landingPage = getLandingPage(effectiveRole)
    navigate(landingPage)
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h1 className="text-center text-4xl font-bold text-primary-600">CYROID</h1>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
            Sign in to your account
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600">
            Or{' '}
            <Link to="/register" className="font-medium text-primary-600 hover:text-primary-500">
              create a new account
            </Link>
          </p>
        </div>

        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded relative">
              {error}
              <button
                type="button"
                className="absolute top-0 right-0 p-4"
                onClick={clearError}
              >
                &times;
              </button>
            </div>
          )}

          <div className="rounded-md shadow-sm -space-y-px">
            <div>
              <label htmlFor="username" className="sr-only">
                Username or Email
              </label>
              <input
                id="username"
                name="username"
                type="text"
                required
                className="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-t-md focus:outline-none focus:ring-primary-500 focus:border-primary-500 focus:z-10 sm:text-sm"
                placeholder="Username or Email"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="password" className="sr-only">
                Password
              </label>
              <input
                id="password"
                name="password"
                type="password"
                required
                className="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-b-md focus:outline-none focus:ring-primary-500 focus:border-primary-500 focus:z-10 sm:text-sm"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
          </div>

          <div>
            <button
              type="submit"
              disabled={isLoading}
              className="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? 'Signing in...' : 'Sign in'}
            </button>
          </div>
        </form>
      </div>

      {/* Forced password change modal */}
      <PasswordChangeModal
        isOpen={showPasswordModal}
        onClose={handlePasswordChangeComplete}
        isForced={true}
      />
    </div>
  )
}
