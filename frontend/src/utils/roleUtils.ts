// frontend/src/utils/roleUtils.ts
/**
 * Role utilities for ABAC-based navigation and access control.
 * Provides role hierarchy, landing page mapping, and access checking.
 */

// Role hierarchy from highest to lowest privilege
export const ROLE_HIERARCHY = ['admin', 'engineer', 'evaluator', 'student'] as const
export type UserRole = typeof ROLE_HIERARCHY[number]

/**
 * Get the highest privilege role from a list of roles.
 * Returns null if no valid roles provided.
 */
export function getHighestRole(roles: string[]): UserRole | null {
  if (!roles || roles.length === 0) return null

  for (const role of ROLE_HIERARCHY) {
    if (roles.includes(role)) {
      return role
    }
  }
  return null
}

/**
 * Get the appropriate landing page for a role.
 */
export function getLandingPage(role: string | null): string {
  switch (role) {
    case 'admin':
    case 'engineer':
      return '/'
    case 'evaluator':
      return '/events'
    case 'student':
      return '/student-portal'
    default:
      return '/'
  }
}

/**
 * Check if a role can access a route that requires specific roles.
 * If requiredRoles is empty or undefined, access is granted.
 */
export function canAccessRoute(activeRole: string | null, requiredRoles?: string[]): boolean {
  // If no roles required, allow access
  if (!requiredRoles || requiredRoles.length === 0) return true

  // If no active role, deny access
  if (!activeRole) return false

  return requiredRoles.includes(activeRole)
}

/**
 * Get display label for a role.
 */
export function getRoleLabel(role: string): string {
  const labels: Record<string, string> = {
    admin: 'Administrator',
    engineer: 'Range Engineer',
    evaluator: 'Evaluator',
    student: 'Student',
  }
  return labels[role] || role.charAt(0).toUpperCase() + role.slice(1)
}

/**
 * Check if a role is a valid UserRole.
 */
export function isValidRole(role: string): role is UserRole {
  return ROLE_HIERARCHY.includes(role as UserRole)
}
