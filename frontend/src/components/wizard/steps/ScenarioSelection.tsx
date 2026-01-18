// frontend/src/components/wizard/steps/ScenarioSelection.tsx
import { Building, Shield, Search, Target } from 'lucide-react';
import clsx from 'clsx';
import { useWizard } from '../WizardContext';
import { ALL_PRESETS, ScenarioPreset } from '../presets';

const iconMap = {
  Building,
  Shield,
  Search,
  Target,
};

export function ScenarioSelection() {
  const { state, dispatch } = useWizard();

  const handleSelect = (preset: ScenarioPreset) => {
    dispatch({ type: 'SELECT_SCENARIO', scenario: preset });
  };

  return (
    <div className="space-y-6">
      <div className="text-center">
        <h2 className="text-xl font-semibold text-gray-900">Choose a Scenario</h2>
        <p className="mt-1 text-sm text-gray-500">
          Select a starting point for your cyber range environment
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {ALL_PRESETS.map((preset) => {
          const Icon = iconMap[preset.icon];
          const vmCount = preset.zones.reduce((acc, z) => acc + z.systems.length, 0);
          const networkCount = preset.zones.length;
          const isSelected = state.scenario?.id === preset.id;

          return (
            <button
              key={preset.id}
              onClick={() => handleSelect(preset)}
              className={clsx(
                'relative p-6 text-left rounded-lg border-2 transition-all',
                isSelected
                  ? 'border-primary-500 bg-primary-50 ring-2 ring-primary-500'
                  : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
              )}
            >
              <div className="flex items-start space-x-4">
                <div
                  className={clsx(
                    'flex-shrink-0 p-3 rounded-lg',
                    isSelected ? 'bg-primary-100 text-primary-600' : 'bg-gray-100 text-gray-600'
                  )}
                >
                  <Icon className="h-6 w-6" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="text-lg font-medium text-gray-900">{preset.name}</h3>
                  <p className="mt-1 text-sm text-gray-500">{preset.description}</p>
                  <div className="mt-3 flex items-center space-x-4 text-xs text-gray-400">
                    <span>{vmCount} VMs</span>
                    <span>{networkCount} {networkCount === 1 ? 'network' : 'networks'}</span>
                  </div>
                </div>
              </div>
              {isSelected && (
                <div className="absolute top-3 right-3">
                  <div className="h-6 w-6 rounded-full bg-primary-500 flex items-center justify-center">
                    <svg className="h-4 w-4 text-white" fill="currentColor" viewBox="0 0 20 20">
                      <path
                        fillRule="evenodd"
                        d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                        clipRule="evenodd"
                      />
                    </svg>
                  </div>
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
