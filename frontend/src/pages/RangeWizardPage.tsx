// frontend/src/pages/RangeWizardPage.tsx
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { WizardLayout } from '../components/wizard-v2/WizardLayout';
import {
  EnvironmentStep,
  ServicesStep,
  NetworkStep,
  UsersStep,
  VulnsStep,
  ReviewStep,
} from '../components/wizard-v2/steps';
import { useWizardStore } from '../stores/wizardStore';
import { rangesApi, networksApi, vmsApi, templatesApi, blueprintsApi } from '../services/api';
import { toast } from '../stores/toastStore';
import type { VMTemplate } from '../types';

const STEPS = [
  EnvironmentStep,
  ServicesStep,
  NetworkStep,
  UsersStep,
  VulnsStep,
  ReviewStep,
];

export default function RangeWizardPage() {
  const navigate = useNavigate();
  const [isDeploying, setIsDeploying] = useState(false);
  const [templates, setTemplates] = useState<VMTemplate[]>([]);

  const {
    currentStep,
    rangeName,
    saveAsBlueprint,
    networks,
    reset,
  } = useWizardStore();

  // Load templates for mapping templateName to templateId
  useEffect(() => {
    const loadTemplates = async () => {
      try {
        const response = await templatesApi.list();
        setTemplates(response.data);
      } catch (error) {
        console.error('Failed to load templates:', error);
      }
    };
    loadTemplates();
  }, []);

  const handleDeploy = async () => {
    setIsDeploying(true);

    try {
      // Step 1: Create the range
      const rangeResponse = await rangesApi.create({
        name: rangeName,
        description: `Created via Range Wizard - ${networks.segments.length} networks, ${networks.vms.length} VMs`,
      });
      const rangeId = rangeResponse.data.id;

      // Step 2: Create networks
      const networkIdMap: Record<string, string> = {};
      for (const segment of networks.segments) {
        const networkResponse = await networksApi.create({
          range_id: rangeId,
          name: segment.name,
          subnet: segment.subnet,
          gateway: segment.gateway,
          is_isolated: segment.isolated,
          dhcp_enabled: segment.dhcp,
        });
        networkIdMap[segment.id] = networkResponse.data.id;
      }

      // Step 3: Create VMs
      for (const vm of networks.vms) {
        // Find template by name or ID
        const template = templates.find((t) => t.id === vm.templateId || t.name === vm.templateName);
        if (!template) {
          console.warn(`Template not found for VM ${vm.hostname}: ${vm.templateName}`);
          continue;
        }

        const networkId = networkIdMap[vm.networkId];
        if (!networkId) {
          console.warn(`Network not found for VM ${vm.hostname}: ${vm.networkId}`);
          continue;
        }

        // Detect OS type for field mapping
        const isWindows = template.os_type === 'windows';

        await vmsApi.create({
          range_id: rangeId,
          network_id: networkId,
          template_id: template.id,
          hostname: vm.hostname,
          ip_address: vm.ip,
          cpu: vm.cpu,
          ram_mb: vm.ramMb,
          disk_gb: vm.diskGb,
          position_x: vm.position.x,
          position_y: vm.position.y,
          // Credentials - mapped to OS-specific fields
          ...(isWindows ? {
            windows_username: vm.username,
            windows_password: vm.password,
          } : {
            linux_username: vm.username,
            linux_password: vm.password,
            linux_user_sudo: vm.sudoEnabled,
          }),
          // Network settings
          use_dhcp: vm.useDhcp,
          gateway: vm.gateway,
          dns_servers: vm.dnsServers,
          // Storage
          disk2_gb: vm.disk2Gb || null,
          disk3_gb: vm.disk3Gb || null,
          // Shared folders
          enable_shared_folder: vm.enableSharedFolder,
          enable_global_shared: vm.enableGlobalShared,
          // Display and locale
          display_type: vm.displayType,
          language: vm.language || null,
          keyboard: vm.keyboard || null,
          region: vm.region || null,
        });
      }

      // Step 4: Optionally save as blueprint
      if (saveAsBlueprint) {
        try {
          await blueprintsApi.create({
            range_id: rangeId,
            name: `${rangeName} Blueprint`,
            description: `Blueprint created from Range Wizard`,
            base_subnet_prefix: '10.0',
          });
          toast.success('Blueprint created successfully');
        } catch (blueprintError) {
          console.error('Failed to create blueprint:', blueprintError);
          toast.error('Range created but blueprint creation failed');
        }
      }

      // Step 5: Deploy the range
      await rangesApi.deploy(rangeId);

      toast.success(`Range "${rangeName}" created and deployment started!`);
      reset();
      navigate(`/ranges/${rangeId}`);
    } catch (error) {
      console.error('Deployment failed:', error);
      toast.error('Failed to deploy range. Please check the console for details.');
    } finally {
      setIsDeploying(false);
    }
  };

  const CurrentStepComponent = STEPS[currentStep];

  return (
    <WizardLayout onDeploy={handleDeploy} isDeploying={isDeploying}>
      <CurrentStepComponent />
    </WizardLayout>
  );
}
