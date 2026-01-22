import React, { useState } from 'react'
import { AlertTriangle, Plus, X, Zap, Shield, Settings } from 'lucide-react'
import { ContainerConfig } from '../types'

interface Props {
  value: ContainerConfig | null
  onChange: (config: ContainerConfig | null) => void
}

// Common Linux capabilities for quick selection
const COMMON_CAPABILITIES = [
  { name: 'NET_ADMIN', description: 'Network configuration (routing, iptables)' },
  { name: 'NET_RAW', description: 'Raw sockets (packet capture, ping)' },
  { name: 'SYS_ADMIN', description: 'System administration (mount, cgroups)' },
  { name: 'SYS_PTRACE', description: 'Process tracing (debugging)' },
  { name: 'CHOWN', description: 'Change file ownership' },
  { name: 'DAC_OVERRIDE', description: 'Bypass file permission checks' },
  { name: 'FOWNER', description: 'Bypass owner checks on files' },
  { name: 'SETFCAP', description: 'Set file capabilities' },
  { name: 'SETUID', description: 'Set UID on execution' },
  { name: 'SETGID', description: 'Set GID on execution' },
  { name: 'MKNOD', description: 'Create special files' },
  { name: 'AUDIT_WRITE', description: 'Write to kernel audit log' },
]

// Presets for common use cases
const PRESETS: Record<string, { name: string; description: string; config: ContainerConfig }> = {
  'samba-ad': {
    name: 'Samba AD DC',
    description: 'Active Directory Domain Controller',
    config: {
      cap_add: ['SYS_ADMIN', 'CHOWN', 'FOWNER', 'DAC_OVERRIDE', 'SETFCAP'],
      security_opt: ['apparmor=unconfined'],
    }
  },
  'vpn': {
    name: 'VPN Server',
    description: 'OpenVPN, WireGuard, etc.',
    config: {
      cap_add: ['NET_ADMIN', 'NET_RAW'],
      devices: ['/dev/net/tun'],
      sysctls: { 'net.ipv4.ip_forward': '1' },
    }
  },
  'packet-capture': {
    name: 'Packet Capture',
    description: 'tcpdump, Wireshark, etc.',
    config: {
      cap_add: ['NET_ADMIN', 'NET_RAW'],
    }
  },
  'network-tools': {
    name: 'Network Tools',
    description: 'nmap, netcat, routing tools',
    config: {
      cap_add: ['NET_ADMIN', 'NET_RAW', 'SYS_PTRACE'],
    }
  },
}

export const ContainerConfigEditor: React.FC<Props> = ({ value, onChange }) => {
  const [newDevice, setNewDevice] = useState('')
  const [newSysctlKey, setNewSysctlKey] = useState('')
  const [newSysctlValue, setNewSysctlValue] = useState('')
  const [newSecurityOpt, setNewSecurityOpt] = useState('')

  const config = value || {}

  const updateConfig = (updates: Partial<ContainerConfig>) => {
    const newConfig = { ...config, ...updates }
    // Clean up empty arrays/objects
    if (newConfig.cap_add?.length === 0) delete newConfig.cap_add
    if (newConfig.cap_drop?.length === 0) delete newConfig.cap_drop
    if (newConfig.devices?.length === 0) delete newConfig.devices
    if (newConfig.security_opt?.length === 0) delete newConfig.security_opt
    if (newConfig.sysctls && Object.keys(newConfig.sysctls).length === 0) delete newConfig.sysctls

    // If completely empty, return null
    if (Object.keys(newConfig).length === 0) {
      onChange(null)
    } else {
      onChange(newConfig)
    }
  }

  const applyPreset = (presetKey: string) => {
    const preset = PRESETS[presetKey]
    if (preset) {
      // Merge preset with existing config
      const newConfig: ContainerConfig = { ...config }

      if (preset.config.cap_add) {
        const existing = newConfig.cap_add || []
        newConfig.cap_add = [...new Set([...existing, ...preset.config.cap_add])]
      }
      if (preset.config.devices) {
        const existing = newConfig.devices || []
        newConfig.devices = [...new Set([...existing, ...preset.config.devices])]
      }
      if (preset.config.security_opt) {
        const existing = newConfig.security_opt || []
        newConfig.security_opt = [...new Set([...existing, ...preset.config.security_opt])]
      }
      if (preset.config.sysctls) {
        newConfig.sysctls = { ...newConfig.sysctls, ...preset.config.sysctls }
      }
      if (preset.config.privileged !== undefined) {
        newConfig.privileged = preset.config.privileged
      }

      onChange(newConfig)
    }
  }

  const toggleCapability = (cap: string) => {
    const current = config.cap_add || []
    if (current.includes(cap)) {
      updateConfig({ cap_add: current.filter(c => c !== cap) })
    } else {
      updateConfig({ cap_add: [...current, cap] })
    }
  }

  const addDevice = () => {
    if (newDevice.trim()) {
      const current = config.devices || []
      if (!current.includes(newDevice.trim())) {
        updateConfig({ devices: [...current, newDevice.trim()] })
      }
      setNewDevice('')
    }
  }

  const removeDevice = (device: string) => {
    const current = config.devices || []
    updateConfig({ devices: current.filter(d => d !== device) })
  }

  const addSysctl = () => {
    if (newSysctlKey.trim() && newSysctlValue.trim()) {
      const current = config.sysctls || {}
      updateConfig({ sysctls: { ...current, [newSysctlKey.trim()]: newSysctlValue.trim() } })
      setNewSysctlKey('')
      setNewSysctlValue('')
    }
  }

  const removeSysctl = (key: string) => {
    const current = { ...config.sysctls }
    delete current[key]
    updateConfig({ sysctls: current })
  }

  const addSecurityOpt = () => {
    if (newSecurityOpt.trim()) {
      const current = config.security_opt || []
      if (!current.includes(newSecurityOpt.trim())) {
        updateConfig({ security_opt: [...current, newSecurityOpt.trim()] })
      }
      setNewSecurityOpt('')
    }
  }

  const removeSecurityOpt = (opt: string) => {
    const current = config.security_opt || []
    updateConfig({ security_opt: current.filter(o => o !== opt) })
  }

  const clearAll = () => {
    onChange(null)
  }

  return (
    <div className="space-y-6">
      {/* Presets */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          <Zap className="h-4 w-4 inline mr-1" />
          Quick Presets
        </label>
        <div className="flex flex-wrap gap-2">
          {Object.entries(PRESETS).map(([key, preset]) => (
            <button
              key={key}
              type="button"
              onClick={() => applyPreset(key)}
              className="px-3 py-1.5 text-sm bg-blue-50 text-blue-700 rounded-md hover:bg-blue-100 border border-blue-200"
              title={preset.description}
            >
              {preset.name}
            </button>
          ))}
          {value && (
            <button
              type="button"
              onClick={clearAll}
              className="px-3 py-1.5 text-sm bg-gray-50 text-gray-600 rounded-md hover:bg-gray-100 border border-gray-200"
            >
              Clear All
            </button>
          )}
        </div>
      </div>

      {/* Privileged Mode */}
      <div className="border-l-4 border-yellow-400 bg-yellow-50 p-4 rounded-r-md">
        <div className="flex items-start">
          <AlertTriangle className="h-5 w-5 text-yellow-600 mt-0.5 mr-3 flex-shrink-0" />
          <div className="flex-1">
            <label className="flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={config.privileged || false}
                onChange={(e) => updateConfig({ privileged: e.target.checked || undefined })}
                className="h-4 w-4 text-yellow-600 rounded border-gray-300 focus:ring-yellow-500"
              />
              <span className="ml-2 text-sm font-medium text-yellow-800">Privileged Mode</span>
            </label>
            <p className="mt-1 text-xs text-yellow-700">
              Full access to host devices. Use only when absolutely necessary (e.g., certain hypervisor containers).
            </p>
          </div>
        </div>
      </div>

      {/* Capabilities */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          <Shield className="h-4 w-4 inline mr-1" />
          Linux Capabilities (cap_add)
        </label>
        <div className="grid grid-cols-2 gap-2">
          {COMMON_CAPABILITIES.map(cap => (
            <label
              key={cap.name}
              className={`flex items-center p-2 rounded border cursor-pointer transition-colors ${
                (config.cap_add || []).includes(cap.name)
                  ? 'bg-blue-50 border-blue-300'
                  : 'bg-white border-gray-200 hover:border-gray-300'
              }`}
            >
              <input
                type="checkbox"
                checked={(config.cap_add || []).includes(cap.name)}
                onChange={() => toggleCapability(cap.name)}
                className="h-4 w-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
              />
              <div className="ml-2">
                <span className="text-sm font-medium text-gray-900">{cap.name}</span>
                <p className="text-xs text-gray-500">{cap.description}</p>
              </div>
            </label>
          ))}
        </div>
      </div>

      {/* Devices */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          <Settings className="h-4 w-4 inline mr-1" />
          Devices
        </label>
        <div className="space-y-2">
          {(config.devices || []).map(device => (
            <div key={device} className="flex items-center gap-2">
              <code className="flex-1 px-3 py-1.5 bg-gray-100 rounded text-sm font-mono">
                {device}
              </code>
              <button
                type="button"
                onClick={() => removeDevice(device)}
                className="p-1 text-gray-400 hover:text-red-500"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ))}
          <div className="flex gap-2">
            <input
              type="text"
              value={newDevice}
              onChange={(e) => setNewDevice(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addDevice())}
              placeholder="/dev/net/tun"
              className="flex-1 px-3 py-1.5 border border-gray-300 rounded-md text-sm focus:ring-blue-500 focus:border-blue-500"
            />
            <button
              type="button"
              onClick={addDevice}
              disabled={!newDevice.trim()}
              className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 disabled:opacity-50"
            >
              <Plus className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Sysctls */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Kernel Parameters (sysctls)
        </label>
        <div className="space-y-2">
          {Object.entries(config.sysctls || {}).map(([key, val]) => (
            <div key={key} className="flex items-center gap-2">
              <code className="flex-1 px-3 py-1.5 bg-gray-100 rounded text-sm font-mono">
                {key} = {val}
              </code>
              <button
                type="button"
                onClick={() => removeSysctl(key)}
                className="p-1 text-gray-400 hover:text-red-500"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ))}
          <div className="flex gap-2">
            <input
              type="text"
              value={newSysctlKey}
              onChange={(e) => setNewSysctlKey(e.target.value)}
              placeholder="net.ipv4.ip_forward"
              className="flex-1 px-3 py-1.5 border border-gray-300 rounded-md text-sm focus:ring-blue-500 focus:border-blue-500"
            />
            <input
              type="text"
              value={newSysctlValue}
              onChange={(e) => setNewSysctlValue(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addSysctl())}
              placeholder="1"
              className="w-24 px-3 py-1.5 border border-gray-300 rounded-md text-sm focus:ring-blue-500 focus:border-blue-500"
            />
            <button
              type="button"
              onClick={addSysctl}
              disabled={!newSysctlKey.trim() || !newSysctlValue.trim()}
              className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 disabled:opacity-50"
            >
              <Plus className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Security Options */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Security Options
        </label>
        <div className="space-y-2">
          {(config.security_opt || []).map(opt => (
            <div key={opt} className="flex items-center gap-2">
              <code className="flex-1 px-3 py-1.5 bg-gray-100 rounded text-sm font-mono">
                {opt}
              </code>
              <button
                type="button"
                onClick={() => removeSecurityOpt(opt)}
                className="p-1 text-gray-400 hover:text-red-500"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ))}
          <div className="flex gap-2">
            <input
              type="text"
              value={newSecurityOpt}
              onChange={(e) => setNewSecurityOpt(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addSecurityOpt())}
              placeholder="apparmor=unconfined"
              className="flex-1 px-3 py-1.5 border border-gray-300 rounded-md text-sm focus:ring-blue-500 focus:border-blue-500"
            />
            <button
              type="button"
              onClick={addSecurityOpt}
              disabled={!newSecurityOpt.trim()}
              className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 disabled:opacity-50"
            >
              <Plus className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Current Configuration Summary */}
      {value && Object.keys(value).length > 0 && (
        <div className="mt-4 p-3 bg-gray-50 rounded-md">
          <label className="block text-xs font-medium text-gray-500 mb-1">Current Configuration</label>
          <pre className="text-xs text-gray-700 overflow-x-auto">
            {JSON.stringify(value, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}

export default ContainerConfigEditor
