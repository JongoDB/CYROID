// frontend/src/components/wizard/steps/ReviewAndDeploy.tsx
import { Network, Server, Settings, Shield } from 'lucide-react';
import clsx from 'clsx';
import { useWizard } from '../WizardContext';

export function ReviewAndDeploy() {
  const { state } = useWizard();

  const enabledZones = state.zones.filter((z) => z.enabled);
  const totalSystems = enabledZones.reduce(
    (acc, z) => acc + z.systems.filter((s) => s.enabled).length,
    0
  );
  const totalCpu = enabledZones.reduce(
    (acc, z) => acc + z.systems.filter((s) => s.enabled).reduce((a, s) => a + (s.cpu || 2), 0),
    0
  );
  const totalRam = enabledZones.reduce(
    (acc, z) => acc + z.systems.filter((s) => s.enabled).reduce((a, s) => a + (s.ramMb || 2048), 0),
    0
  );
  const totalDisk = enabledZones.reduce(
    (acc, z) => acc + z.systems.filter((s) => s.enabled).reduce((a, s) => a + (s.diskGb || 20), 0),
    0
  );

  const hasWindowsDC = enabledZones.some(
    (z) => z.systems.some((s) => s.enabled && s.role === 'domain-controller')
  );

  return (
    <div className="space-y-6">
      <div className="text-center">
        <h2 className="text-xl font-semibold text-gray-900">Review & Deploy</h2>
        <p className="mt-1 text-sm text-gray-500">
          Confirm your configuration before deploying the range
        </p>
      </div>

      {/* Range Info */}
      <div className="bg-gray-50 rounded-lg p-4">
        <h3 className="font-medium text-gray-900 mb-2">{state.rangeName}</h3>
        {state.rangeDescription && (
          <p className="text-sm text-gray-600">{state.rangeDescription}</p>
        )}
      </div>

      {/* Resource Summary */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-blue-50 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-blue-700">{enabledZones.length}</div>
          <div className="text-xs text-blue-600">Networks</div>
        </div>
        <div className="bg-green-50 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-green-700">{totalSystems}</div>
          <div className="text-xs text-green-600">VMs</div>
        </div>
        <div className="bg-purple-50 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-purple-700">{totalCpu}</div>
          <div className="text-xs text-purple-600">CPU Cores</div>
        </div>
        <div className="bg-orange-50 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-orange-700">{Math.round(totalRam / 1024)}</div>
          <div className="text-xs text-orange-600">GB RAM</div>
        </div>
      </div>

      {/* Networks and Systems */}
      <div className="space-y-4">
        {enabledZones.map((zone) => (
          <div key={zone.id} className="border border-gray-200 rounded-lg overflow-hidden">
            <div className="bg-gray-50 px-4 py-2 border-b flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Network className="h-4 w-4 text-gray-400" />
                <span className="font-medium text-gray-900">{zone.name}</span>
              </div>
              <span className="text-sm font-mono text-gray-500">{zone.subnet}</span>
            </div>
            <div className="divide-y divide-gray-100">
              {zone.systems.filter((s) => s.enabled).map((system) => (
                <div key={system.id} className="px-4 py-2 flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Server
                      className={clsx(
                        'h-4 w-4',
                        system.osType === 'windows' ? 'text-blue-500' : 'text-orange-500'
                      )}
                    />
                    <span className="text-sm text-gray-900">{system.name}</span>
                    <span className="text-xs text-gray-400">({system.templateName})</span>
                  </div>
                  <span className="text-sm font-mono text-gray-500">{system.ip}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Configuration Summary */}
      {hasWindowsDC && (
        <div className="border border-gray-200 rounded-lg p-4">
          <div className="flex items-center space-x-2 mb-3">
            <Settings className="h-4 w-4 text-gray-400" />
            <span className="font-medium text-gray-900">Active Directory Configuration</span>
          </div>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-500">Domain:</span>
              <span className="ml-2 font-mono text-gray-900">{state.config.domainName}</span>
            </div>
            <div>
              <span className="text-gray-500">Users:</span>
              <span className="ml-2 text-gray-900">{state.config.userCount}</span>
            </div>
          </div>
        </div>
      )}

      {/* Security Level */}
      <div className="flex items-center justify-center space-x-2 py-2">
        <Shield
          className={clsx(
            'h-5 w-5',
            state.config.vulnerabilityLevel === 'none' && 'text-green-500',
            state.config.vulnerabilityLevel === 'some' && 'text-yellow-500',
            state.config.vulnerabilityLevel === 'many' && 'text-red-500'
          )}
        />
        <span className="text-sm text-gray-600">
          Security Level:{' '}
          <span className="font-medium">
            {state.config.vulnerabilityLevel === 'none' && 'Hardened'}
            {state.config.vulnerabilityLevel === 'some' && 'Realistic'}
            {state.config.vulnerabilityLevel === 'many' && 'Vulnerable'}
          </span>
        </span>
      </div>

      {/* Disk Space Notice */}
      <div className="bg-gray-50 rounded-lg p-3 text-center text-sm text-gray-600">
        Estimated disk usage: <span className="font-medium">{totalDisk} GB</span>
      </div>
    </div>
  );
}
