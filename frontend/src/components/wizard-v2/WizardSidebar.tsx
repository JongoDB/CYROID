// frontend/src/components/wizard-v2/WizardSidebar.tsx
import { CheckCircle, Circle } from 'lucide-react';
import clsx from 'clsx';
import { useWizardStore } from '../../stores/wizardStore';

const STEPS = [
  { id: 0, title: 'Environment', description: 'Select environment type' },
  { id: 1, title: 'Services', description: 'Choose systems & services' },
  { id: 2, title: 'Networks', description: 'Design network topology' },
  { id: 3, title: 'Users', description: 'Configure user groups' },
  { id: 4, title: 'Vulnerabilities', description: 'Set attack surface' },
  { id: 5, title: 'Review', description: 'Review & deploy' },
];

export function WizardSidebar() {
  const { currentStep, setStep, isValid } = useWizardStore();

  return (
    <div className="w-64 bg-gray-50 border-r border-gray-200 p-4">
      <h2 className="text-lg font-semibold text-gray-900 mb-6">Range Wizard</h2>
      <nav className="space-y-2">
        {STEPS.map((step) => {
          const isComplete = step.id < currentStep && isValid(step.id);
          const isCurrent = step.id === currentStep;
          const isClickable = step.id <= currentStep || isValid(step.id - 1);

          return (
            <button
              key={step.id}
              onClick={() => isClickable && setStep(step.id)}
              disabled={!isClickable}
              className={clsx(
                'w-full flex items-start gap-3 p-3 rounded-lg text-left transition-colors',
                isCurrent && 'bg-primary-50 border border-primary-200',
                !isCurrent && isClickable && 'hover:bg-gray-100',
                !isClickable && 'opacity-50 cursor-not-allowed'
              )}
            >
              <div className="flex-shrink-0 mt-0.5">
                {isComplete ? (
                  <CheckCircle className="w-5 h-5 text-green-500" />
                ) : (
                  <Circle
                    className={clsx(
                      'w-5 h-5',
                      isCurrent ? 'text-primary-600' : 'text-gray-300'
                    )}
                    fill={isCurrent ? 'currentColor' : 'none'}
                  />
                )}
              </div>
              <div>
                <div
                  className={clsx(
                    'text-sm font-medium',
                    isCurrent ? 'text-primary-700' : 'text-gray-700'
                  )}
                >
                  {step.title}
                </div>
                <div className="text-xs text-gray-500">{step.description}</div>
              </div>
            </button>
          );
        })}
      </nav>
    </div>
  );
}
