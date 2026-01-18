// frontend/src/components/wizard-v2/WizardLayout.tsx
import { ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { X, ChevronLeft, ChevronRight, Rocket } from 'lucide-react';
import clsx from 'clsx';
import { WizardSidebar } from './WizardSidebar';
import { useWizardStore } from '../../stores/wizardStore';

interface WizardLayoutProps {
  children: ReactNode;
  onDeploy: () => Promise<void>;
  isDeploying?: boolean;
}

export function WizardLayout({ children, onDeploy, isDeploying = false }: WizardLayoutProps) {
  const navigate = useNavigate();
  const { currentStep, nextStep, prevStep, isValid, reset } = useWizardStore();

  const handleCancel = () => {
    if (window.confirm('Are you sure you want to cancel? All progress will be lost.')) {
      reset();
      navigate('/ranges');
    }
  };

  const handleNext = async () => {
    if (currentStep === 5) {
      await onDeploy();
    } else {
      nextStep();
    }
  };

  return (
    <div className="h-screen flex flex-col bg-white">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
        <h1 className="text-xl font-semibold text-gray-900">Create New Range</h1>
        <button
          onClick={handleCancel}
          disabled={isDeploying}
          className="text-gray-400 hover:text-gray-500 disabled:opacity-50"
        >
          <X className="h-6 w-6" />
        </button>
      </div>

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        <WizardSidebar />
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Step content */}
          <div className="flex-1 overflow-y-auto p-6">
            {children}
          </div>

          {/* Footer navigation */}
          <div className="flex items-center justify-between px-6 py-4 border-t border-gray-200 bg-gray-50">
            <button
              onClick={prevStep}
              disabled={currentStep === 0 || isDeploying}
              className={clsx(
                'inline-flex items-center px-4 py-2 text-sm font-medium rounded-lg',
                currentStep === 0 || isDeploying
                  ? 'text-gray-400 cursor-not-allowed'
                  : 'text-gray-700 hover:bg-gray-100'
              )}
            >
              <ChevronLeft className="h-4 w-4 mr-1" />
              Back
            </button>

            <button
              onClick={handleNext}
              disabled={!isValid(currentStep) || isDeploying}
              className={clsx(
                'inline-flex items-center px-6 py-2 text-sm font-medium rounded-lg',
                !isValid(currentStep) || isDeploying
                  ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                  : currentStep === 5
                  ? 'bg-green-600 text-white hover:bg-green-700'
                  : 'bg-primary-600 text-white hover:bg-primary-700'
              )}
            >
              {isDeploying ? (
                <>
                  <span className="animate-spin mr-2">⏳</span>
                  Deploying...
                </>
              ) : currentStep === 5 ? (
                <>
                  <Rocket className="h-4 w-4 mr-2" />
                  Create & Deploy
                </>
              ) : (
                <>
                  Next
                  <ChevronRight className="h-4 w-4 ml-1" />
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
