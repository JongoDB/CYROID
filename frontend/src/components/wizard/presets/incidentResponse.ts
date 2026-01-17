// frontend/src/components/wizard/presets/incidentResponse.ts
import { ScenarioPreset } from './types';

export const incidentResponse: ScenarioPreset = {
  id: 'incident-response',
  name: 'Incident Response Lab',
  description: 'Pre-staged artifacts for forensics and investigation training',
  icon: 'Search',
  zones: [
    {
      id: 'internal',
      name: 'Corporate Network',
      subnet: '10.150.0.0/24',
      gateway: '10.150.0.1',
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
          id: 'compromised',
          name: 'Compromised Workstation',
          ipOffset: 50,
          templateName: 'Windows 11',
          osType: 'windows',
          role: 'victim',
          cpu: 2,
          ramMb: 4096,
          diskGb: 40,
        },
        {
          id: 'sift',
          name: 'SIFT Workstation',
          ipOffset: 100,
          templateName: 'Ubuntu 22.04',
          osType: 'linux',
          role: 'forensics',
          cpu: 4,
          ramMb: 8192,
          diskGb: 100,
        },
      ],
    },
  ],
  defaultConfig: {
    domainName: 'victim.local',
    userCount: 5,
    vulnerabilityLevel: 'many',
  },
};
