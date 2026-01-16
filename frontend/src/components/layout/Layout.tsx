// frontend/src/components/layout/Layout.tsx
import { ReactNode, useState, useEffect } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '../../stores/authStore'
import { versionApi, VersionInfo } from '../../services/api'
import {
  LayoutDashboard,
  Server,
  Network,
  FileBox,
  LogOut,
  Menu,
  X,
  HardDrive,
  Users,
  Shield,
  Key
} from 'lucide-react'
import clsx from 'clsx'
import PasswordChangeModal from '../common/PasswordChangeModal'
import { ToastContainer } from '../common/Toast'

interface LayoutProps {
  children: ReactNode
}

interface NavItem {
  name: string
  href: string
  icon: typeof LayoutDashboard
  adminOnly?: boolean
}

const navigation: NavItem[] = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Image Cache', href: '/cache', icon: HardDrive },
  { name: 'Templates', href: '/templates', icon: Server },
  { name: 'Ranges', href: '/ranges', icon: Network },
  { name: 'Users', href: '/users', icon: Users, adminOnly: true },
  { name: 'Artifacts', href: '/artifacts', icon: FileBox },
]

export default function Layout({ children }: LayoutProps) {
  const { user, logout, passwordResetRequired } = useAuthStore()
  const navigate = useNavigate()
  const location = useLocation()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [showPasswordModal, setShowPasswordModal] = useState(false)
  const [versionInfo, setVersionInfo] = useState<VersionInfo | null>(null)

  useEffect(() => {
    versionApi.get()
      .then(res => setVersionInfo(res.data))
      .catch(() => {}) // Silently fail if version endpoint unavailable
  }, [])

  // Filter navigation based on user roles (ABAC: check roles array)
  const isAdmin = user?.roles?.includes('admin') ?? false
  const filteredNavigation = navigation.filter(item => !item.adminOnly || isAdmin)

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  // Show forced password modal if required
  const shouldShowForcedPasswordModal = passwordResetRequired && !showPasswordModal

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Mobile sidebar backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-gray-600 bg-opacity-75 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Mobile sidebar */}
      <div className={clsx(
        "fixed inset-y-0 left-0 z-50 w-64 bg-gray-900 transform transition-transform duration-300 lg:hidden",
        sidebarOpen ? "translate-x-0" : "-translate-x-full"
      )}>
        <div className="flex items-center justify-between h-16 px-4 bg-gray-800">
          <span className="text-xl font-bold text-white">CYROID</span>
          <button onClick={() => setSidebarOpen(false)} className="text-gray-300 hover:text-white">
            <X className="h-6 w-6" />
          </button>
        </div>
        <nav className="mt-4 px-2 space-y-1">
          {filteredNavigation.map((item) => (
            <Link
              key={item.name}
              to={item.href}
              onClick={() => setSidebarOpen(false)}
              className={clsx(
                "flex items-center px-3 py-2 text-sm font-medium rounded-md",
                location.pathname === item.href
                  ? "bg-gray-800 text-white"
                  : "text-gray-300 hover:bg-gray-700 hover:text-white"
              )}
            >
              <item.icon className="mr-3 h-5 w-5" />
              {item.name}
            </Link>
          ))}
        </nav>
      </div>

      {/* Desktop sidebar */}
      <div className="hidden lg:fixed lg:inset-y-0 lg:flex lg:w-64 lg:flex-col">
        <div className="flex flex-col flex-grow bg-gray-900 overflow-y-auto">
          <div className="flex items-center h-16 px-4 bg-gray-800">
            <span className="text-xl font-bold text-white">CYROID</span>
          </div>
          <nav className="mt-4 flex-1 px-2 space-y-1">
            {filteredNavigation.map((item) => (
              <Link
                key={item.name}
                to={item.href}
                className={clsx(
                  "flex items-center px-3 py-2 text-sm font-medium rounded-md",
                  location.pathname === item.href
                    ? "bg-gray-800 text-white"
                    : "text-gray-300 hover:bg-gray-700 hover:text-white"
                )}
              >
                <item.icon className="mr-3 h-5 w-5" />
                {item.name}
              </Link>
            ))}
          </nav>
          <div className="px-2 pb-4">
            <div className="px-3 py-2 text-sm text-gray-400">
              <div>Signed in as <span className="font-medium text-white">{user?.username}</span></div>
              {user?.roles && user.roles.length > 0 && (
                <div className="mt-1 flex items-center flex-wrap gap-1">
                  <Shield className="h-3 w-3 mr-1" />
                  {user.roles.map((role) => (
                    <span key={role} className="capitalize text-xs bg-gray-700 px-1.5 py-0.5 rounded">{role}</span>
                  ))}
                </div>
              )}
              {user?.tags && user.tags.length > 0 && (
                <div className="mt-1 flex items-center flex-wrap gap-1">
                  {user.tags.slice(0, 3).map((tag) => (
                    <span key={tag} className="text-xs bg-gray-700 px-1.5 py-0.5 rounded text-gray-300">{tag}</span>
                  ))}
                  {user.tags.length > 3 && <span className="text-xs text-gray-500">+{user.tags.length - 3}</span>}
                </div>
              )}
            </div>
            <button
              onClick={() => setShowPasswordModal(true)}
              className="flex items-center w-full px-3 py-2 text-sm font-medium text-gray-300 rounded-md hover:bg-gray-700 hover:text-white"
            >
              <Key className="mr-3 h-5 w-5" />
              Change Password
            </button>
            <button
              onClick={handleLogout}
              className="flex items-center w-full px-3 py-2 text-sm font-medium text-gray-300 rounded-md hover:bg-gray-700 hover:text-white"
            >
              <LogOut className="mr-3 h-5 w-5" />
              Sign out
            </button>
            {versionInfo && (
              <div className="mt-4 pt-4 border-t border-gray-700 px-3 text-xs text-gray-500">
                <span>v{versionInfo.version}</span>
                {versionInfo.commit !== 'dev' && (
                  <span className="ml-1">({versionInfo.commit.substring(0, 7)})</span>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="lg:pl-64 flex flex-col flex-1">
        {/* Top bar */}
        <div className="sticky top-0 z-10 flex h-16 bg-white shadow lg:hidden">
          <button
            onClick={() => setSidebarOpen(true)}
            className="px-4 text-gray-500 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-primary-500"
          >
            <Menu className="h-6 w-6" />
          </button>
          <div className="flex items-center flex-1 px-4">
            <span className="text-lg font-semibold text-gray-900">CYROID</span>
          </div>
        </div>

        {/* Page content */}
        <main className="flex-1">
          <div className="py-6 px-4 sm:px-6 lg:px-8">
            {children}
          </div>
        </main>
      </div>

      {/* Voluntary password change modal */}
      <PasswordChangeModal
        isOpen={showPasswordModal}
        onClose={() => setShowPasswordModal(false)}
        isForced={false}
      />

      {/* Forced password change modal (when admin requires reset) */}
      <PasswordChangeModal
        isOpen={shouldShowForcedPasswordModal}
        onClose={() => {}}
        isForced={true}
      />

      {/* Toast notifications */}
      <ToastContainer />
    </div>
  )
}
