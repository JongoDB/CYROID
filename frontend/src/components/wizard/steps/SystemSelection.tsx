// frontend/src/components/wizard/steps/SystemSelection.tsx
import { Monitor, Server } from 'lucide-react';
import clsx from 'clsx';
import { useWizard } from '../WizardContext';

export function SystemSelection() {
  const { state, dispatch } = useWizard();

  const handleToggleSystem = (zoneId: string, systemId: string) => {
    dispatch({ type: 'TOGGLE_SYSTEM', zoneId, systemId });
  };

  const enabledZones = state.zones.filter((z) => z.enabled);

  return (
    <div className="space-y-6">
      <div className="text-center">
        <h2 className="text-xl font-semibold text-gray-900">Select Systems</h2>
        <p className="mt-1 text-sm text-gray-500">
          Choose which systems to include in each network zone
        </p>
      </div>

      <div className="space-y-6">
        {enabledZones.map((zone) => (
          <div key={zone.id} className="rounded-lg border border-gray-200 overflow-hidden">
            <div className="bg-gray-50 px-4 py-3 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Server className="h-5 w-5 text-gray-400" />
                  <span className="font-medium text-gray-900">{zone.name}</span>
                </div>
                <span className="text-sm text-gray-500">{zone.subnet}</span>
              </div>
            </div>

            <div className="p-4 space-y-3">
              {zone.systems.map((system) => (
                <label
                  key={system.id}
                  className={clsx(
                    'flex items-center justify-between p-3 rounded-lg border cursor-pointer transition-all',
                    system.enabled
                      ? 'border-primary-200 bg-primary-50'
                      : 'border-gray-200 bg-white hover:bg-gray-50'
                  )}
                >
                  <div className="flex items-center space-x-3">
                    <input
                      type="checkbox"
                      checked={system.enabled}
                      onChange={() => handleToggleSystem(zone.id, system.id)}
                      className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                    />
                    <div className="flex items-center space-x-2">
                      <Monitor
                        className={clsx(
                          'h-5 w-5',
                          system.osType === 'windows' ? 'text-blue-500' : 'text-orange-500'
                        )}
                      />
                      <div>
                        <span className="font-medium text-gray-900">{system.name}</span>
                        <span className="ml-2 text-sm text-gray-500">({system.templateName})</span>
                      </div>
                    </div>
                  </div>
                  <div className="text-sm text-gray-500 font-mono">{system.ip}</div>
                </label>
              ))}
            </div>
          </div>
        ))}
      </div>

      {enabledZones.every((z) => !z.systems.some((s) => s.enabled)) && (
        <div className="text-center p-4 bg-yellow-50 rounded-lg">
          <p className="text-sm text-yellow-700">
            Please select at least one system to continue.
          </p>
        </div>
      )}
    </div>
  );
}
