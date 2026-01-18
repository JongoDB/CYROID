// frontend/src/components/wizard-v2/steps/EnvironmentStep.tsx
import { Building2, Factory, Cloud, Settings } from 'lucide-react';
import clsx from 'clsx';
import { useWizardStore, EnvironmentType } from '../../../stores/wizardStore';

interface EnvironmentOption {
  type: EnvironmentType;
  icon: typeof Building2;
  title: string;
  description: string;
  defaultNetworks: string[];
  suggestedServices: string[];
}

const ENVIRONMENT_OPTIONS: EnvironmentOption[] = [
  {
    type: 'enterprise',
    icon: Building2,
    title: 'Enterprise',
    description: 'Corporate network with DMZ, internal segments, Active Directory, and standard business services.',
    defaultNetworks: ['DMZ', 'Corporate', 'Management'],
    suggestedServices: ['Active Directory', 'DNS', 'Web Server', 'File Server'],
  },
  {
    type: 'industrial',
    icon: Factory,
    title: 'Industrial (OT/ICS)',
    description: 'Industrial control systems with SCADA, PLCs, and segmented IT/OT networks.',
    defaultNetworks: ['IT Network', 'OT Network', 'DMZ'],
    suggestedServices: ['HMI Workstation', 'Historian', 'Engineering Workstation', 'PLC Simulator'],
  },
  {
    type: 'cloud',
    icon: Cloud,
    title: 'Cloud',
    description: 'Cloud-native architecture with microservices, containers, and API gateways.',
    defaultNetworks: ['Public', 'Private', 'Database'],
    suggestedServices: ['API Gateway', 'Web App', 'Database', 'Cache'],
  },
  {
    type: 'custom',
    icon: Settings,
    title: 'Custom',
    description: 'Start with a blank canvas and build your own topology from scratch.',
    defaultNetworks: [],
    suggestedServices: [],
  },
];

export function EnvironmentStep() {
  const { environment, setEnvironment } = useWizardStore();

  const selectedOption = ENVIRONMENT_OPTIONS.find(o => o.type === environment.type);

  return (
    <div className="max-w-4xl mx-auto">
      <h2 className="text-2xl font-bold text-gray-900 mb-2">
        What type of environment are you building?
      </h2>
      <p className="text-gray-600 mb-8">
        Select an environment template to get started with pre-configured networks and suggested services.
      </p>

      {/* Environment type cards */}
      <div className="grid grid-cols-2 gap-4 mb-8">
        {ENVIRONMENT_OPTIONS.map((option) => {
          const Icon = option.icon;
          const isSelected = environment.type === option.type;

          return (
            <button
              key={option.type}
              onClick={() => setEnvironment({ type: option.type })}
              className={clsx(
                'flex flex-col items-center p-6 rounded-xl border-2 transition-all text-center',
                isSelected
                  ? 'border-primary-500 bg-primary-50 ring-2 ring-primary-200'
                  : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
              )}
            >
              <Icon
                className={clsx(
                  'w-12 h-12 mb-3',
                  isSelected ? 'text-primary-600' : 'text-gray-400'
                )}
              />
              <h3
                className={clsx(
                  'text-lg font-semibold mb-1',
                  isSelected ? 'text-primary-700' : 'text-gray-900'
                )}
              >
                {option.title}
              </h3>
              <div
                className={clsx(
                  'w-4 h-4 rounded-full border-2 mt-2',
                  isSelected
                    ? 'border-primary-500 bg-primary-500'
                    : 'border-gray-300'
                )}
              >
                {isSelected && (
                  <div className="w-full h-full flex items-center justify-center">
                    <div className="w-2 h-2 bg-white rounded-full" />
                  </div>
                )}
              </div>
            </button>
          );
        })}
      </div>

      {/* Selected environment details */}
      {selectedOption && (
        <div className="bg-gray-50 rounded-xl p-6 border border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            {selectedOption.title} Environment
          </h3>
          <p className="text-gray-600 mb-4">{selectedOption.description}</p>

          {selectedOption.defaultNetworks.length > 0 && (
            <div className="mb-3">
              <span className="text-sm font-medium text-gray-700">Default topology: </span>
              <span className="text-sm text-gray-600">
                {selectedOption.defaultNetworks.join(' → ')}
              </span>
            </div>
          )}

          {selectedOption.suggestedServices.length > 0 && (
            <div>
              <span className="text-sm font-medium text-gray-700">Suggested services: </span>
              <span className="text-sm text-gray-600">
                {selectedOption.suggestedServices.join(', ')}
              </span>
            </div>
          )}

          {selectedOption.type === 'custom' && (
            <p className="text-sm text-gray-500 italic">
              You'll configure everything manually in the next steps.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
