// frontend/src/components/wizard-v2/data/servicePresets.ts
import { ServiceConfig, EnvironmentType } from '../../../stores/wizardStore';

export const SERVICE_CATALOG: ServiceConfig[] = [
  // Infrastructure
  { id: 'ad', name: 'Active Directory', templateName: 'Windows Server 2019', description: 'Domain controller', category: 'infrastructure', defaultNetwork: 'Corporate' },
  { id: 'dns', name: 'DNS Server', templateName: 'Ubuntu Server', description: 'DNS resolution', category: 'infrastructure', defaultNetwork: 'Corporate' },
  { id: 'dhcp', name: 'DHCP Server', templateName: 'Ubuntu Server', description: 'IP address management', category: 'infrastructure', defaultNetwork: 'Management' },
  { id: 'firewall', name: 'Firewall/Router', templateName: 'pfSense', description: 'Network perimeter', category: 'infrastructure', defaultNetwork: 'DMZ' },

  // Security
  { id: 'siem', name: 'SIEM/Log Collector', templateName: 'Ubuntu Server', description: 'Security monitoring', category: 'security', defaultNetwork: 'Management' },
  { id: 'ids', name: 'IDS/IPS', templateName: 'Security Onion', description: 'Intrusion detection', category: 'security', defaultNetwork: 'DMZ' },

  // Applications
  { id: 'web', name: 'Web Server', templateName: 'Ubuntu Server', description: 'HTTP/HTTPS services', category: 'application', defaultNetwork: 'DMZ' },
  { id: 'email', name: 'Email Server', templateName: 'Ubuntu Server', description: 'Mail services', category: 'application', defaultNetwork: 'Corporate' },
  { id: 'file', name: 'File Server', templateName: 'Windows Server 2019', description: 'Shared storage', category: 'application', defaultNetwork: 'Corporate' },

  // Databases
  { id: 'mysql', name: 'MySQL Database', templateName: 'Ubuntu Server', description: 'Relational database', category: 'database', defaultNetwork: 'Corporate' },
  { id: 'mssql', name: 'SQL Server', templateName: 'Windows Server 2019', description: 'Microsoft database', category: 'database', defaultNetwork: 'Corporate' },
];

export const ENVIRONMENT_DEFAULTS: Record<EnvironmentType, string[]> = {
  enterprise: ['ad', 'dns', 'firewall', 'web', 'file'],
  industrial: ['firewall', 'dns', 'web'],
  cloud: ['web', 'mysql', 'dns'],
  custom: [],
};

export function getServicesForEnvironment(envType: EnvironmentType): string[] {
  return ENVIRONMENT_DEFAULTS[envType] || [];
}
