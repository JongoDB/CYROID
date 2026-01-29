// frontend/src/components/layout/Layout.tsx
import { ReactNode, useState, useEffect, useMemo } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '../../stores/authStore'
import { versionApi, VersionInfo } from '../../services/api'
import { canAccessRoute } from '../../utils/roleUtils'
import {
  LayoutDashboard,
  Server,
  Network,
  FileBox,
  LogOut,
  Menu,
  X,
  HardDrive,
  Key,
  LayoutTemplate,
  Target,
  Settings,
  BookOpen,
  CalendarDays,
  GraduationCap,
  Store
} from 'lucide-react'
import clsx from 'clsx'
import PasswordChangeModal from '../common/PasswordChangeModal'
import { ToastContainer } from '../common/Toast'
import { NotificationBell } from '../notifications'
import PerspectiveSwitcher from '../common/PerspectiveSwitcher'

interface LayoutProps {
  children: ReactNode
}

interface NavItem {
  name: string
  href: string
  icon: typeof LayoutDashboard
  requiredRoles?: string[]  // If undefined, accessible by all roles
}

interface NavSection {
  title: string
  items: NavItem[]
  isStorefront?: boolean  // Special styling for marketplace/catalog section
}

// Standalone nav items (role-filtered)
const dashboardNav: NavItem = { name: 'Dashboard', href: '/', icon: LayoutDashboard, requiredRoles: ['admin', 'engineer', 'evaluator'] }
const studentPortalNav: NavItem = { name: 'Student Portal', href: '/student-portal', icon: GraduationCap, requiredRoles: ['student'] }

// Navigation sections with role-based access control
const navSections: NavSection[] = [
  {
    title: 'Content Development',
    items: [
      { name: 'Content Library', href: '/content', icon: BookOpen, requiredRoles: ['admin', 'engineer', 'evaluator'] },
      { name: 'Artifacts', href: '/artifacts', icon: FileBox, requiredRoles: ['admin', 'engineer'] },
    ]
  },
  {
    title: 'Range Development',
    items: [
      { name: 'Ranges', href: '/ranges', icon: Network, requiredRoles: ['admin', 'engineer', 'evaluator'] },
      { name: 'Range Blueprints', href: '/blueprints', icon: LayoutTemplate, requiredRoles: ['admin', 'engineer'] },
      { name: 'Training Scenarios', href: '/scenarios', icon: Target, requiredRoles: ['admin', 'engineer'] },
      { name: 'VM Library', href: '/vm-library', icon: Server, requiredRoles: ['admin', 'engineer'] },
      { name: 'Image Cache', href: '/cache', icon: HardDrive, requiredRoles: ['admin', 'engineer'] },
    ]
  },
  {
    title: 'Event Management',
    items: [
      { name: 'Training Events', href: '/events', icon: CalendarDays },  // Accessible to all
    ]
  },
  {
    title: 'Content Catalog',
    isStorefront: true,  // Distinct styling for marketplace
    items: [
      { name: 'Browse Catalog', href: '/catalog', icon: Store, requiredRoles: ['admin', 'engineer', 'evaluator'] },
    ]
  },
]

export default function Layout({ children }: LayoutProps) {
  const { user, logout, passwordResetRequired, getEffectiveRole } = useAuthStore()
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

  // Get effective role for filtering navigation
  const effectiveRole = getEffectiveRole()

  // Filter sections - only show sections that have at least one visible item
  const filteredSections = useMemo(() => {
    return navSections.map(section => ({
      ...section,
      items: section.items.filter(item => canAccessRoute(effectiveRole, item.requiredRoles))
    })).filter(section => section.items.length > 0)
  }, [effectiveRole])

  // Check if standalone nav items are visible
  const showDashboard = canAccessRoute(effectiveRole, dashboardNav.requiredRoles)
  const showStudentPortal = canAccessRoute(effectiveRole, studentPortalNav.requiredRoles)

  // Check if user is admin (ABAC: check roles array)
  const isAdmin = user?.roles?.includes('admin') ?? false

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
          {/* Dashboard or Student Portal - standalone */}
          {showDashboard && (
            <Link
              to={dashboardNav.href}
              onClick={() => setSidebarOpen(false)}
              className={clsx(
                "flex items-center px-3 py-2 text-sm font-medium rounded-md",
                location.pathname === dashboardNav.href
                  ? "bg-gray-800 text-white"
                  : "text-gray-300 hover:bg-gray-700 hover:text-white"
              )}
            >
              <dashboardNav.icon className="mr-3 h-5 w-5" />
              {dashboardNav.name}
            </Link>
          )}
          {showStudentPortal && (
            <Link
              to={studentPortalNav.href}
              onClick={() => setSidebarOpen(false)}
              className={clsx(
                "flex items-center px-3 py-2 text-sm font-medium rounded-md",
                location.pathname === studentPortalNav.href
                  ? "bg-gray-800 text-white"
                  : "text-gray-300 hover:bg-gray-700 hover:text-white"
              )}
            >
              <studentPortalNav.icon className="mr-3 h-5 w-5" />
              {studentPortalNav.name}
            </Link>
          )}

          {/* Sectioned navigation */}
          {filteredSections.map((section, index) => (
            <div key={section.title} className={clsx(
              "pt-4",
              section.isStorefront && "mt-4 mx-2 rounded-lg bg-gradient-to-r from-indigo-900/50 to-purple-900/50 p-2"
            )}>
              {index > 0 && !section.isStorefront && <div className="mx-3 mb-3 border-t border-gray-700" />}
              <h3 className={clsx(
                "px-3 text-xs font-semibold uppercase tracking-wider",
                section.isStorefront ? "text-indigo-300" : "text-gray-400"
              )}>
                {section.title}
              </h3>
              <div className="mt-2 space-y-1">
                {section.items.map((item) => (
                  <Link
                    key={item.name}
                    to={item.href}
                    onClick={() => setSidebarOpen(false)}
                    className={clsx(
                      "flex items-center px-3 py-2 text-sm font-medium rounded-md",
                      section.isStorefront
                        ? location.pathname === item.href || location.pathname.startsWith(item.href + '/')
                          ? "bg-indigo-600 text-white"
                          : "text-indigo-200 hover:bg-indigo-800/50 hover:text-white"
                        : location.pathname === item.href
                          ? "bg-gray-800 text-white"
                          : "text-gray-300 hover:bg-gray-700 hover:text-white"
                    )}
                  >
                    <item.icon className={clsx(
                      "mr-3 h-5 w-5",
                      section.isStorefront && "text-indigo-300"
                    )} />
                    {item.name}
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </nav>
        {/* Mobile user section */}
        <div className="absolute bottom-0 left-0 right-0 px-2 pb-4 bg-gray-900">
          <div className="px-3 py-2 text-sm text-gray-400 border-t border-gray-700 pt-4">
            <div>Signed in as <span className="font-medium text-white">{user?.username}</span></div>
            {/* Role Perspective Switcher (Mobile) */}
            {user?.roles && user.roles.length > 0 && (
              <div className="mt-2">
                <PerspectiveSwitcher />
              </div>
            )}
          </div>
          {isAdmin && (
            <Link
              to="/admin"
              onClick={() => setSidebarOpen(false)}
              className={clsx(
                "flex items-center w-full px-3 py-2 text-sm font-medium rounded-md",
                location.pathname === '/admin'
                  ? "bg-gray-800 text-white"
                  : "text-gray-300 hover:bg-gray-700 hover:text-white"
              )}
            >
              <Settings className="mr-3 h-5 w-5" />
              Admin Settings
            </Link>
          )}
          <button
            onClick={() => { setShowPasswordModal(true); setSidebarOpen(false); }}
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
        </div>
      </div>

      {/* Desktop sidebar - z-30 ensures notification dropdown overlays main content */}
      <div className="hidden lg:fixed lg:inset-y-0 lg:flex lg:w-64 lg:flex-col lg:z-30">
        {/* Header outside scrollable area so dropdown isn't clipped */}
        <div className="flex items-center justify-between h-16 px-4 bg-gray-800 relative z-20">
          <span className="text-xl font-bold text-white">CYROID</span>
          <NotificationBell />
        </div>
        <div className="flex flex-col flex-grow bg-gray-900 overflow-y-auto">
          <nav className="mt-4 flex-1 px-2 space-y-1">
            {/* Dashboard or Student Portal - standalone */}
            {showDashboard && (
              <Link
                to={dashboardNav.href}
                className={clsx(
                  "flex items-center px-3 py-2 text-sm font-medium rounded-md",
                  location.pathname === dashboardNav.href
                    ? "bg-gray-800 text-white"
                    : "text-gray-300 hover:bg-gray-700 hover:text-white"
                )}
              >
                <dashboardNav.icon className="mr-3 h-5 w-5" />
                {dashboardNav.name}
              </Link>
            )}
            {showStudentPortal && (
              <Link
                to={studentPortalNav.href}
                className={clsx(
                  "flex items-center px-3 py-2 text-sm font-medium rounded-md",
                  location.pathname === studentPortalNav.href
                    ? "bg-gray-800 text-white"
                    : "text-gray-300 hover:bg-gray-700 hover:text-white"
                )}
              >
                <studentPortalNav.icon className="mr-3 h-5 w-5" />
                {studentPortalNav.name}
              </Link>
            )}

            {/* Sectioned navigation */}
            {filteredSections.map((section, index) => (
              <div key={section.title} className={clsx(
                "pt-4",
                section.isStorefront && "mt-4 mx-2 rounded-lg bg-gradient-to-r from-indigo-900/50 to-purple-900/50 p-2"
              )}>
                {index > 0 && !section.isStorefront && <div className="mx-3 mb-3 border-t border-gray-700" />}
                <h3 className={clsx(
                  "px-3 text-xs font-semibold uppercase tracking-wider",
                  section.isStorefront ? "text-indigo-300" : "text-gray-400"
                )}>
                  {section.title}
                </h3>
                <div className="mt-2 space-y-1">
                  {section.items.map((item) => (
                    <Link
                      key={item.name}
                      to={item.href}
                      className={clsx(
                        "flex items-center px-3 py-2 text-sm font-medium rounded-md",
                        section.isStorefront
                          ? location.pathname === item.href || location.pathname.startsWith(item.href + '/')
                            ? "bg-indigo-600 text-white"
                            : "text-indigo-200 hover:bg-indigo-800/50 hover:text-white"
                          : location.pathname === item.href
                            ? "bg-gray-800 text-white"
                            : "text-gray-300 hover:bg-gray-700 hover:text-white"
                      )}
                    >
                      <item.icon className={clsx(
                        "mr-3 h-5 w-5",
                        section.isStorefront && "text-indigo-300"
                      )} />
                      {item.name}
                    </Link>
                  ))}
                </div>
              </div>
            ))}
          </nav>
          <div className="px-2 pb-4">
            <div className="px-3 py-2 text-sm text-gray-400">
              <div>Signed in as <span className="font-medium text-white">{user?.username}</span></div>
              {/* Role Perspective Switcher */}
              {user?.roles && user.roles.length > 0 && (
                <div className="mt-2">
                  <PerspectiveSwitcher />
                </div>
              )}
              {user?.tags && user.tags.length > 0 && (
                <div className="mt-2 flex items-center flex-wrap gap-1">
                  {user.tags.slice(0, 3).map((tag) => (
                    <span key={tag} className="text-xs bg-gray-700 px-1.5 py-0.5 rounded text-gray-300">{tag}</span>
                  ))}
                  {user.tags.length > 3 && <span className="text-xs text-gray-500">+{user.tags.length - 3}</span>}
                </div>
              )}
            </div>
            {isAdmin && (
              <Link
                to="/admin"
                className={clsx(
                  "flex items-center w-full px-3 py-2 text-sm font-medium rounded-md",
                  location.pathname === '/admin'
                    ? "bg-gray-800 text-white"
                    : "text-gray-300 hover:bg-gray-700 hover:text-white"
                )}
              >
                <Settings className="mr-3 h-5 w-5" />
                Admin Settings
              </Link>
            )}
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
          <div className="flex items-center justify-between flex-1 px-4">
            <span className="text-lg font-semibold text-gray-900">CYROID</span>
            <NotificationBell />
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
