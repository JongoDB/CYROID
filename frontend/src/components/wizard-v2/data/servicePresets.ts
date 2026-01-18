// frontend/src/components/wizard-v2/data/servicePresets.ts
import { ServiceConfig, EnvironmentType } from '../../../stores/wizardStore';

export const SERVICE_CATALOG: ServiceConfig[] = [
  // Infrastructure
  { id: 'ad', name: 'Active Directory', osFamily: 'windows-server', defaultVersion: '2022', description: 'Domain controller', category: 'infrastructure', defaultNetwork: 'Corporate' },
  { id: 'dns', name: 'DNS Server', osFamily: 'ubuntu-server', defaultVersion: '22.04', description: 'DNS resolution', category: 'infrastructure', defaultNetwork: 'Corporate' },
  { id: 'dhcp', name: 'DHCP Server', osFamily: 'ubuntu-server', defaultVersion: '22.04', description: 'IP address management', category: 'infrastructure', defaultNetwork: 'Management' },
  { id: 'firewall', name: 'Firewall/Router', osFamily: 'pfsense', defaultVersion: '2.7', description: 'Network perimeter', category: 'infrastructure', defaultNetwork: 'DMZ' },

  // Security
  { id: 'siem', name: 'SIEM/Log Collector', osFamily: 'security-onion', defaultVersion: '2.4', description: 'Security monitoring', category: 'security', defaultNetwork: 'Management' },
  { id: 'ids', name: 'IDS/IPS', osFamily: 'security-onion', defaultVersion: '2.4', description: 'Intrusion detection', category: 'security', defaultNetwork: 'DMZ' },

  // Applications
  { id: 'web', name: 'Web Server', osFamily: 'ubuntu-server', defaultVersion: '22.04', description: 'HTTP/HTTPS services', category: 'application', defaultNetwork: 'DMZ' },
  { id: 'email', name: 'Email Server', osFamily: 'ubuntu-server', defaultVersion: '22.04', description: 'Mail services', category: 'application', defaultNetwork: 'Corporate' },
  { id: 'file', name: 'File Server', osFamily: 'windows-server', defaultVersion: '2022', description: 'Shared storage', category: 'application', defaultNetwork: 'Corporate' },

  // Databases
  { id: 'mysql', name: 'MySQL Database', osFamily: 'ubuntu-server', defaultVersion: '22.04', description: 'Relational database', category: 'database', defaultNetwork: 'Corporate' },
  { id: 'mssql', name: 'SQL Server', osFamily: 'windows-server', defaultVersion: '2022', description: 'Microsoft database', category: 'database', defaultNetwork: 'Corporate' },
];

// Available versions for each OS family (fetched from backend, but defaults here)
export const OS_FAMILY_VERSIONS: Record<string, string[]> = {
  'windows-server': ['2019', '2022', '2025'],
  'ubuntu-server': ['22.04', '24.04'],
  'ubuntu-desktop': ['22.04'],
  'kali': ['latest', 'attack'],
  'pfsense': ['2.7'],
  'security-onion': ['2.4'],
  'vyos': ['1.2'],
  'samba-dc': ['latest'],
  'windows-dc': ['2022'],
};

// Human-readable names for OS families
export const OS_FAMILY_NAMES: Record<string, string> = {
  'windows-server': 'Windows Server',
  'ubuntu-server': 'Ubuntu Server',
  'ubuntu-desktop': 'Ubuntu Desktop',
  'kali': 'Kali Linux',
  'pfsense': 'pfSense',
  'security-onion': 'Security Onion',
  'vyos': 'VyOS Router',
  'samba-dc': 'Samba DC',
  'windows-dc': 'Windows DC',
};

export const ENVIRONMENT_DEFAULTS: Record<EnvironmentType, string[]> = {
  enterprise: ['ad', 'dns', 'firewall', 'web', 'file'],
  industrial: ['firewall', 'dns', 'web'],
  cloud: ['web', 'mysql', 'dns'],
  custom: [],
};

export function getServicesForEnvironment(envType: EnvironmentType): string[] {
  return ENVIRONMENT_DEFAULTS[envType] || [];
}

/**
 * Resolve OS family + version to template name
 * e.g., ('windows-server', '2022') => 'Windows Server 2022'
 */
export function resolveTemplateName(osFamily: string, osVersion: string): string {
  const familyName = OS_FAMILY_NAMES[osFamily] || osFamily;
  return `${familyName} ${osVersion}`;
}

/**
 * Get version overrides from session storage
 * Used by NetworkStep and deploy handlers
 */
export function getVersionOverrides(): Record<string, string> {
  const stored = sessionStorage.getItem('wizard-version-overrides');
  if (stored) {
    try {
      return JSON.parse(stored);
    } catch {
      return {};
    }
  }
  return {};
}

/**
 * Get the effective version for a service, considering overrides
 */
export function getEffectiveVersion(serviceId: string): string {
  const service = SERVICE_CATALOG.find(s => s.id === serviceId);
  if (!service) return '';

  const overrides = getVersionOverrides();
  return overrides[serviceId] || service.defaultVersion;
}

/**
 * Get the effective template name for a service
 */
export function getEffectiveTemplateName(serviceId: string): string {
  const service = SERVICE_CATALOG.find(s => s.id === serviceId);
  if (!service) return '';

  const version = getEffectiveVersion(serviceId);
  return resolveTemplateName(service.osFamily, version);
}
