// frontend/src/components/common/PerspectiveSwitcher.tsx
import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../stores/authStore'
import { getRoleLabel, getLandingPage, ROLE_HIERARCHY } from '../../utils/roleUtils'
import { ChevronDown, Check, Shield } from 'lucide-react'
import clsx from 'clsx'

export default function PerspectiveSwitcher() {
  const { user, setActiveRole, getEffectiveRole } = useAuthStore()
  const navigate = useNavigate()
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const effectiveRole = getEffectiveRole()
  const userRoles = user?.roles || []

  // Sort roles by hierarchy
  const sortedRoles = [...userRoles].sort((a, b) => {
    const aIndex = ROLE_HIERARCHY.indexOf(a as typeof ROLE_HIERARCHY[number])
    const bIndex = ROLE_HIERARCHY.indexOf(b as typeof ROLE_HIERARCHY[number])
    return aIndex - bIndex
  })

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleRoleSwitch = (role: string) => {
    setActiveRole(role)
    setIsOpen(false)
    // Navigate to the role's landing page
    const landingPage = getLandingPage(role)
    navigate(landingPage)
  }

  // Don't show switcher if user has only one role
  if (userRoles.length <= 1) {
    return (
      <div className="flex items-center gap-1 text-xs">
        <Shield className="h-3 w-3" />
        <span className="capitalize bg-gray-700 px-1.5 py-0.5 rounded">
          {getRoleLabel(effectiveRole || 'user')}
        </span>
      </div>
    )
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-1 text-xs bg-gray-700 hover:bg-gray-600 px-2 py-1 rounded transition-colors w-full"
      >
        <Shield className="h-3 w-3 flex-shrink-0" />
        <span className="capitalize truncate">{getRoleLabel(effectiveRole || 'user')}</span>
        <ChevronDown className={clsx(
          "h-3 w-3 ml-auto transition-transform flex-shrink-0",
          isOpen && "rotate-180"
        )} />
      </button>

      {isOpen && (
        <div className="absolute bottom-full left-0 right-0 mb-1 bg-gray-800 border border-gray-700 rounded-md shadow-lg overflow-hidden z-50">
          <div className="py-1">
            <div className="px-3 py-1.5 text-xs text-gray-500 uppercase tracking-wider">
              Switch Perspective
            </div>
            {sortedRoles.map((role) => (
              <button
                key={role}
                onClick={() => handleRoleSwitch(role)}
                className={clsx(
                  "w-full flex items-center justify-between px-3 py-2 text-sm text-left",
                  role === effectiveRole
                    ? "bg-primary-600/20 text-primary-300"
                    : "text-gray-300 hover:bg-gray-700"
                )}
              >
                <span className="capitalize">{getRoleLabel(role)}</span>
                {role === effectiveRole && (
                  <Check className="h-4 w-4 text-primary-400" />
                )}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
