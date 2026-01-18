// frontend/src/components/wizard/RangeWizard.tsx
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { X, Loader2, ChevronLeft, ChevronRight, Rocket } from 'lucide-react';
import clsx from 'clsx';
import { WizardProvider, useWizard } from './WizardContext';
import {
  ScenarioSelection,
  ZoneConfiguration,
  SystemSelection,
  ConfigurationOptions,
  ReviewAndDeploy,
} from './steps';
import { rangesApi, networksApi, vmsApi, templatesApi } from '../../services/api';
import { toast } from '../../stores/toastStore';
import type { VMTemplate } from '../../types';

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

const STEPS = [
  { title: 'Scenario', component: ScenarioSelection },
  { title: 'Zones', component: ZoneConfiguration },
  { title: 'Systems', component: SystemSelection },
  { title: 'Configure', component: ConfigurationOptions },
  { title: 'Deploy', component: ReviewAndDeploy },
];

function WizardContent({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate();
  const { state, nextStep, prevStep, canProceed } = useWizard();
  const [deploying, setDeploying] = useState(false);
  const [deployProgress, setDeployProgress] = useState('');

  const CurrentStep = STEPS[state.currentStep].component;

  const handleDeploy = async () => {
    setDeploying(true);
    try {
      // Fetch templates to map names to IDs
      setDeployProgress('Loading templates...');
      const templatesRes = await templatesApi.list();
      const templateMap: Record<string, VMTemplate> = {};
      templatesRes.data.forEach((t: VMTemplate) => {
        templateMap[t.name] = t;
      });

      // Create range
      setDeployProgress('Creating range...');
      const rangeRes = await rangesApi.create({
        name: state.rangeName,
        description: state.rangeDescription,
      });
      const rangeId = rangeRes.data.id;

      // Create networks
      const networkIdMap: Record<string, string> = {};
      for (const zone of state.zones.filter((z) => z.enabled)) {
        setDeployProgress(`Creating network: ${zone.name}...`);
        const networkRes = await networksApi.create({
          range_id: rangeId,
          name: zone.name,
          subnet: zone.subnet,
          gateway: zone.gateway,
          is_isolated: zone.isIsolated,
        });
        networkIdMap[zone.id] = networkRes.data.id;
      }

      // Create VMs
      for (const zone of state.zones.filter((z) => z.enabled)) {
        for (const system of zone.systems.filter((s) => s.enabled)) {
          setDeployProgress(`Creating VM: ${system.name}...`);

          const template = templateMap[system.templateName];
          if (!template) {
            toast.warning(`Template "${system.templateName}" not found, skipping ${system.name}`);
            continue;
          }

          await vmsApi.create({
            range_id: rangeId,
            network_id: networkIdMap[zone.id],
            template_id: template.id,
            hostname: system.name.toLowerCase().replace(/\s+/g, '-'),
            ip_address: system.ip,
            cpu: system.cpu || template.default_cpu,
            ram_mb: system.ramMb || template.default_ram_mb,
            disk_gb: system.diskGb || template.default_disk_gb,
            use_dhcp: false,
            gateway: zone.gateway,
          });
        }
      }

      // Deploy the range
      setDeployProgress('Deploying range...');
      await rangesApi.deploy(rangeId);

      toast.success('Range created and deployment started!');
      onClose();
      navigate(`/ranges/${rangeId}`);
    } catch (error: any) {
      console.error('Deployment error:', error);
      toast.error(error.response?.data?.detail || 'Failed to create range');
      setDeploying(false);
    }
  };

  const handleNext = () => {
    if (state.currentStep === 4) {
      handleDeploy();
    } else {
      nextStep();
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4 py-8">
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75" onClick={onClose} />

        <div className="relative bg-white rounded-xl shadow-xl w-full max-w-2xl">
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b">
            <h2 className="text-lg font-semibold text-gray-900">Range Wizard</h2>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-500"
              disabled={deploying}
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Progress Steps */}
          <div className="px-6 py-4 border-b bg-gray-50">
            <div className="flex items-center justify-between">
              {STEPS.map((step, index) => (
                <div key={step.title} className="flex items-center">
                  <div
                    className={clsx(
                      'flex items-center justify-center w-8 h-8 rounded-full text-sm font-medium',
                      index < state.currentStep
                        ? 'bg-primary-600 text-white'
                        : index === state.currentStep
                        ? 'bg-primary-100 text-primary-600 ring-2 ring-primary-600'
                        : 'bg-gray-200 text-gray-500'
                    )}
                  >
                    {index + 1}
                  </div>
                  <span
                    className={clsx(
                      'ml-2 text-sm',
                      index === state.currentStep ? 'text-primary-600 font-medium' : 'text-gray-500'
                    )}
                  >
                    {step.title}
                  </span>
                  {index < STEPS.length - 1 && (
                    <div className="mx-4 w-12 h-0.5 bg-gray-200" />
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Content */}
          <div className="px-6 py-6 max-h-[60vh] overflow-y-auto">
            {deploying ? (
              <div className="flex flex-col items-center justify-center py-12">
                <Loader2 className="h-12 w-12 animate-spin text-primary-600 mb-4" />
                <p className="text-gray-600">{deployProgress}</p>
              </div>
            ) : (
              <CurrentStep />
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between px-6 py-4 border-t bg-gray-50">
            <button
              onClick={prevStep}
              disabled={state.currentStep === 0 || deploying}
              className={clsx(
                'inline-flex items-center px-4 py-2 text-sm font-medium rounded-lg',
                state.currentStep === 0 || deploying
                  ? 'text-gray-400 cursor-not-allowed'
                  : 'text-gray-700 hover:bg-gray-100'
              )}
            >
              <ChevronLeft className="h-4 w-4 mr-1" />
              Back
            </button>

            <button
              onClick={handleNext}
              disabled={!canProceed() || deploying}
              className={clsx(
                'inline-flex items-center px-6 py-2 text-sm font-medium rounded-lg',
                !canProceed() || deploying
                  ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                  : state.currentStep === 4
                  ? 'bg-green-600 text-white hover:bg-green-700'
                  : 'bg-primary-600 text-white hover:bg-primary-700'
              )}
            >
              {state.currentStep === 4 ? (
                <>
                  <Rocket className="h-4 w-4 mr-2" />
                  Deploy Range
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

export function RangeWizard({ isOpen, onClose }: Props) {
  if (!isOpen) return null;

  return (
    <WizardProvider>
      <WizardContent onClose={onClose} />
    </WizardProvider>
  );
}
