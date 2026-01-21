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
import { rangesApi, networksApi, vmsApi, imagesApi, blueprintsApi } from '../services/api';
import { toast } from '../stores/toastStore';
import type { BaseImage } from '../types';

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
  const [baseImages, setBaseImages] = useState<BaseImage[]>([]);

  const {
    currentStep,
    rangeName,
    saveAsBlueprint,
    networks,
    reset,
  } = useWizardStore();

  // Load base images for mapping to VM creation
  useEffect(() => {
    const loadBaseImages = async () => {
      try {
        const response = await imagesApi.listBase();
        setBaseImages(response.data);
      } catch (error) {
        console.error('Failed to load base images:', error);
      }
    };
    loadBaseImages();
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
        // Find base image by ID or name
        let baseImage = baseImages.find((img) => img.id === vm.baseImageId);
        if (!baseImage) {
          baseImage = baseImages.find((img) => img.name === vm.templateName);
        }
        // Fallback: match by docker_image_tag for container images
        if (!baseImage && vm.templateName) {
          baseImage = baseImages.find((img) => img.docker_image_tag === vm.templateName);
        }
        if (!baseImage) {
          console.warn(`Base image not found for VM ${vm.hostname}: ${vm.templateName || vm.baseImageId}`);
          toast.error(`Base image not found: ${vm.templateName || 'Unknown'}. Please ensure the image is cached.`);
          continue;
        }

        const networkId = networkIdMap[vm.networkId];
        if (!networkId) {
          console.warn(`Network not found for VM ${vm.hostname}: ${vm.networkId}`);
          continue;
        }

        // Detect OS type for field mapping
        const isWindows = baseImage.os_type === 'windows';

        await vmsApi.create({
          range_id: rangeId,
          network_id: networkId,
          base_image_id: baseImage.id,
          hostname: vm.hostname,
          ip_address: vm.ip,
          cpu: vm.cpu || baseImage.default_cpu,
          ram_mb: vm.ramMb || baseImage.default_ram_mb,
          disk_gb: vm.diskGb || baseImage.default_disk_gb,
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
