// frontend/src/components/wizard/presets/adEnterpriseLab.ts
import { ScenarioPreset } from './types';

export const adEnterpriseLab: ScenarioPreset = {
  id: 'ad-enterprise-lab',
  name: 'AD Enterprise Lab',
  description: 'Domain controller, workstations, and file server for blue team training',
  icon: 'Building',
  zones: [
    {
      id: 'internal',
      name: 'Internal Network',
      subnet: '10.100.0.0/24',
      gateway: '10.100.0.1',
      isIsolated: true,
      systems: [
        {
          id: 'dc1',
          name: 'Domain Controller',
          ipOffset: 10,
          templateName: 'Windows Server 2022',
          osType: 'windows',
          role: 'domain-controller',
          cpu: 4,
          ramMb: 4096,
          diskGb: 60,
        },
        {
          id: 'fs1',
          name: 'File Server',
          ipOffset: 20,
          templateName: 'Windows Server 2022',
          osType: 'windows',
          role: 'file-server',
          cpu: 2,
          ramMb: 2048,
          diskGb: 100,
        },
        {
          id: 'ws1',
          name: 'Workstation 1',
          ipOffset: 50,
          templateName: 'Windows 11',
          osType: 'windows',
          role: 'workstation',
          cpu: 2,
          ramMb: 4096,
          diskGb: 40,
        },
        {
          id: 'ws2',
          name: 'Workstation 2',
          ipOffset: 51,
          templateName: 'Windows 11',
          osType: 'windows',
          role: 'workstation',
          cpu: 2,
          ramMb: 4096,
          diskGb: 40,
        },
      ],
    },
  ],
  defaultConfig: {
    domainName: 'corp.local',
    userCount: 10,
    vulnerabilityLevel: 'none',
  },
};
