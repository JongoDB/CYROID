// frontend/src/components/wizard/steps/ZoneConfiguration.tsx
import { Network, Server } from 'lucide-react';
import clsx from 'clsx';
import { useWizard } from '../WizardContext';

export function ZoneConfiguration() {
  const { state, dispatch } = useWizard();

  const handleToggleZone = (zoneId: string) => {
    dispatch({ type: 'TOGGLE_ZONE', zoneId });
  };

  return (
    <div className="space-y-6">
      <div className="text-center">
        <h2 className="text-xl font-semibold text-gray-900">Configure Network Zones</h2>
        <p className="mt-1 text-sm text-gray-500">
          Enable or disable network zones for your environment
        </p>
      </div>

      <div className="space-y-4">
        {state.zones.map((zone) => {
          const enabledSystems = zone.systems.filter((s) => s.enabled).length;

          return (
            <div
              key={zone.id}
              className={clsx(
                'rounded-lg border-2 p-4 transition-all',
                zone.enabled
                  ? 'border-primary-200 bg-white'
                  : 'border-gray-200 bg-gray-50 opacity-60'
              )}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={zone.enabled}
                      onChange={() => handleToggleZone(zone.id)}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"></div>
                  </label>
                  <div className="flex items-center space-x-2">
                    <Network className="h-5 w-5 text-gray-400" />
                    <span className="font-medium text-gray-900">{zone.name}</span>
                  </div>
                </div>
                <div className="text-sm text-gray-500">
                  {zone.subnet}
                </div>
              </div>

              {zone.enabled && (
                <div className="mt-4 pl-14">
                  <div className="flex items-center space-x-2 text-sm text-gray-600">
                    <Server className="h-4 w-4" />
                    <span>
                      {enabledSystems} {enabledSystems === 1 ? 'system' : 'systems'}
                    </span>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {zone.systems.map((sys) => (
                      <span
                        key={sys.id}
                        className={clsx(
                          'px-2 py-1 text-xs rounded-full',
                          sys.enabled
                            ? 'bg-primary-100 text-primary-700'
                            : 'bg-gray-100 text-gray-500'
                        )}
                      >
                        {sys.name}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {!state.zones.some((z) => z.enabled) && (
        <div className="text-center p-4 bg-yellow-50 rounded-lg">
          <p className="text-sm text-yellow-700">
            Please enable at least one network zone to continue.
          </p>
        </div>
      )}
    </div>
  );
}
