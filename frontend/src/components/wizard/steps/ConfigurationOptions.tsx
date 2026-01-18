// frontend/src/components/wizard/steps/ConfigurationOptions.tsx
import { useState } from 'react';
import { Eye, EyeOff, RefreshCw, Router } from 'lucide-react';
import { useWizard } from '../WizardContext';

function generatePassword(length: number = 16): string {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789!@#$%';
  return Array.from({ length }, () => chars[Math.floor(Math.random() * chars.length)]).join('');
}

export function ConfigurationOptions() {
  const { state, dispatch } = useWizard();
  const [showPassword, setShowPassword] = useState(false);

  const hasWindowsDC = state.zones.some(
    (z) => z.enabled && z.systems.some((s) => s.enabled && s.role === 'domain-controller')
  );

  const handleConfigChange = (key: string, value: string | number) => {
    dispatch({ type: 'UPDATE_CONFIG', config: { [key]: value } });
  };

  const regeneratePassword = () => {
    dispatch({ type: 'UPDATE_CONFIG', config: { adminPassword: generatePassword() } });
  };

  return (
    <div className="space-y-6">
      <div className="text-center">
        <h2 className="text-xl font-semibold text-gray-900">Configuration</h2>
        <p className="mt-1 text-sm text-gray-500">
          Set up your range name and environment options
        </p>
      </div>

      <div className="space-y-6">
        {/* Range Name */}
        <div>
          <label className="block text-sm font-medium text-gray-700">Range Name</label>
          <input
            type="text"
            value={state.rangeName}
            onChange={(e) => dispatch({ type: 'SET_RANGE_NAME', name: e.target.value })}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
            placeholder="My Cyber Range"
          />
        </div>

        {/* Range Description */}
        <div>
          <label className="block text-sm font-medium text-gray-700">Description</label>
          <textarea
            value={state.rangeDescription}
            onChange={(e) => dispatch({ type: 'SET_RANGE_DESCRIPTION', description: e.target.value })}
            rows={2}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
            placeholder="Optional description..."
          />
        </div>

        {/* AD Configuration - only show if DC present */}
        {hasWindowsDC && (
          <div className="border-t pt-6">
            <h3 className="text-sm font-medium text-gray-900 mb-4">Active Directory Settings</h3>

            {/* Domain Name */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700">Domain Name</label>
              <input
                type="text"
                value={state.config.domainName}
                onChange={(e) => handleConfigChange('domainName', e.target.value)}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                placeholder="lab.local"
              />
            </div>

            {/* Admin Password */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700">Admin Password</label>
              <div className="mt-1 flex rounded-md shadow-sm">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={state.config.adminPassword}
                  onChange={(e) => handleConfigChange('adminPassword', e.target.value)}
                  className="flex-1 block w-full rounded-l-md border-gray-300 focus:border-primary-500 focus:ring-primary-500 sm:text-sm font-mono"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="inline-flex items-center px-3 border border-l-0 border-gray-300 bg-gray-50 text-gray-500 hover:bg-gray-100"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
                <button
                  type="button"
                  onClick={regeneratePassword}
                  className="inline-flex items-center px-3 rounded-r-md border border-l-0 border-gray-300 bg-gray-50 text-gray-500 hover:bg-gray-100"
                >
                  <RefreshCw className="h-4 w-4" />
                </button>
              </div>
            </div>

            {/* User Count */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700">Number of Domain Users</label>
              <select
                value={state.config.userCount}
                onChange={(e) => handleConfigChange('userCount', parseInt(e.target.value))}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
              >
                <option value={5}>5 users</option>
                <option value={10}>10 users</option>
                <option value={25}>25 users</option>
                <option value={50}>50 users</option>
              </select>
            </div>
          </div>
        )}

        {/* Vulnerability Level */}
        <div className={hasWindowsDC ? '' : 'border-t pt-6'}>
          <label className="block text-sm font-medium text-gray-700">Vulnerability Level</label>
          <p className="text-xs text-gray-500 mb-2">
            Controls the security posture of deployed systems
          </p>
          <div className="grid grid-cols-3 gap-3">
            {(['none', 'some', 'many'] as const).map((level) => (
              <button
                key={level}
                type="button"
                onClick={() => handleConfigChange('vulnerabilityLevel', level)}
                className={`px-4 py-3 rounded-lg border-2 text-sm font-medium transition-all ${
                  state.config.vulnerabilityLevel === level
                    ? 'border-primary-500 bg-primary-50 text-primary-700'
                    : 'border-gray-200 text-gray-700 hover:border-gray-300'
                }`}
              >
                {level === 'none' && 'Hardened'}
                {level === 'some' && 'Realistic'}
                {level === 'many' && 'Vulnerable'}
              </button>
            ))}
          </div>
        </div>

        {/* Edge Router Configuration */}
        <div className="border-t pt-6">
          <div className="flex items-center gap-2 mb-4">
            <Router className="h-5 w-5 text-gray-500" />
            <h3 className="text-sm font-medium text-gray-900">Edge Router Settings</h3>
          </div>
          <p className="text-xs text-gray-500 mb-4">
            Configure the VyOS edge router that handles routing between networks
          </p>

          {/* DHCP Toggle */}
          <div className="mb-4">
            <div className="flex items-center justify-between">
              <div>
                <label className="text-sm font-medium text-gray-700">DHCP Server</label>
                <p className="text-xs text-gray-500">
                  Automatically assign IPs to VMs on non-isolated networks
                </p>
              </div>
              <button
                type="button"
                onClick={() => handleConfigChange('dhcpEnabled', !state.config.dhcpEnabled)}
                className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 ${
                  state.config.dhcpEnabled ? 'bg-primary-600' : 'bg-gray-200'
                }`}
              >
                <span
                  className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                    state.config.dhcpEnabled ? 'translate-x-5' : 'translate-x-0'
                  }`}
                />
              </button>
            </div>
          </div>

          {/* DNS Servers */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700">DNS Servers</label>
            <input
              type="text"
              value={state.config.dnsServers}
              onChange={(e) => handleConfigChange('dnsServers', e.target.value)}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
              placeholder="8.8.8.8, 8.8.4.4"
            />
            <p className="mt-1 text-xs text-gray-500">
              Comma-separated list of DNS servers for DHCP clients
            </p>
          </div>

          {/* DNS Search Domain */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700">DNS Search Domain</label>
            <input
              type="text"
              value={state.config.dnsSearchDomain}
              onChange={(e) => handleConfigChange('dnsSearchDomain', e.target.value)}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
              placeholder="lab.local (optional)"
            />
            <p className="mt-1 text-xs text-gray-500">
              Domain suffix for unqualified hostnames (e.g., lab.local)
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
