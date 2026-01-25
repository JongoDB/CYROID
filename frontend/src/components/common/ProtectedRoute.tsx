// frontend/src/components/common/ProtectedRoute.tsx
import { ReactNode, useEffect } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '../../stores/authStore'
import { canAccessRoute, getLandingPage } from '../../utils/roleUtils'
import { toast } from '../../stores/toastStore'

interface ProtectedRouteProps {
  children: ReactNode
  requiredRoles?: string[]  // If specified, only these roles can access the route
}

export default function ProtectedRoute({ children, requiredRoles }: ProtectedRouteProps) {
  const { user, token, isLoading, checkAuth, getEffectiveRole } = useAuthStore()
  const location = useLocation()

  useEffect(() => {
    if (token && !user) {
      checkAuth()
    }
  }, [token, user, checkAuth])

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  // Wait for user data before checking roles
  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  // Check role-based access if requiredRoles is specified
  if (requiredRoles && requiredRoles.length > 0) {
    const effectiveRole = getEffectiveRole()
    if (!canAccessRoute(effectiveRole, requiredRoles)) {
      // Show toast and redirect to user's landing page
      toast.error(`Access denied. This page requires one of: ${requiredRoles.join(', ')}`)
      const landingPage = getLandingPage(effectiveRole)
      return <Navigate to={landingPage} replace />
    }
  }

  return <>{children}</>
}
