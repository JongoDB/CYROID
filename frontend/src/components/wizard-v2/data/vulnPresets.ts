// frontend/src/components/wizard-v2/data/vulnPresets.ts
export interface VulnDefinition {
  id: string;
  name: string;
  description: string;
  category: 'network' | 'web' | 'credential' | 'misconfig';
  severity: 'low' | 'medium' | 'high' | 'critical';
  applicableTemplates: string[];
}

export const VULNERABILITY_CATALOG: VulnDefinition[] = [
  // Network Services
  {
    id: 'open-ssh',
    name: 'Open SSH (weak key)',
    description: 'SSH with weak or default keys',
    category: 'network',
    severity: 'high',
    applicableTemplates: ['Ubuntu Server', 'Kali Linux'],
  },
  {
    id: 'open-rdp',
    name: 'Open RDP',
    description: 'RDP exposed without NLA',
    category: 'network',
    severity: 'high',
    applicableTemplates: ['Windows Server 2019', 'Windows 10'],
  },
  {
    id: 'open-smb',
    name: 'Open SMB (EternalBlue)',
    description: 'SMBv1 vulnerable to MS17-010',
    category: 'network',
    severity: 'critical',
    applicableTemplates: ['Windows Server 2019', 'Windows 10'],
  },
  {
    id: 'open-telnet',
    name: 'Open Telnet',
    description: 'Telnet service exposed',
    category: 'network',
    severity: 'medium',
    applicableTemplates: ['Ubuntu Server'],
  },

  // Web Applications
  {
    id: 'sqli',
    name: 'SQL Injection',
    description: 'Web app vulnerable to SQLi',
    category: 'web',
    severity: 'critical',
    applicableTemplates: ['Ubuntu Server'],
  },
  {
    id: 'xss',
    name: 'Cross-Site Scripting',
    description: 'Reflected XSS in web app',
    category: 'web',
    severity: 'medium',
    applicableTemplates: ['Ubuntu Server'],
  },
  {
    id: 'lfi',
    name: 'Local File Inclusion',
    description: 'LFI vulnerability in web app',
    category: 'web',
    severity: 'high',
    applicableTemplates: ['Ubuntu Server'],
  },

  // Credentials
  {
    id: 'default-creds',
    name: 'Default Credentials',
    description: 'Service using default password',
    category: 'credential',
    severity: 'high',
    applicableTemplates: ['Ubuntu Server', 'Windows Server 2019'],
  },
  {
    id: 'weak-mysql',
    name: 'Weak MySQL Password',
    description: 'MySQL with root:root',
    category: 'credential',
    severity: 'high',
    applicableTemplates: ['Ubuntu Server'],
  },
  {
    id: 'password-reuse',
    name: 'Password Reuse',
    description: 'Same password across services',
    category: 'credential',
    severity: 'medium',
    applicableTemplates: ['Windows Server 2019', 'Ubuntu Server'],
  },

  // Misconfigurations
  {
    id: 'world-writable',
    name: 'World-Writable Dirs',
    description: 'Sensitive dirs with 777 perms',
    category: 'misconfig',
    severity: 'medium',
    applicableTemplates: ['Ubuntu Server'],
  },
  {
    id: 'sudo-nopass',
    name: 'SUDO No Password',
    description: 'User can sudo without password',
    category: 'misconfig',
    severity: 'high',
    applicableTemplates: ['Ubuntu Server', 'Kali Linux'],
  },
  {
    id: 'anonymous-ftp',
    name: 'Anonymous FTP',
    description: 'FTP allows anonymous login',
    category: 'misconfig',
    severity: 'medium',
    applicableTemplates: ['Ubuntu Server'],
  },
];

export interface VulnPresetConfig {
  name: string;
  description: string;
  vulnIds: string[];
}

export const VULN_PRESETS: Record<string, VulnPresetConfig> = {
  none: {
    name: 'None (Hardened)',
    description: 'No vulnerabilities - fully hardened systems for defensive training',
    vulnIds: [],
  },
  beginner: {
    name: 'Beginner (5 vulns)',
    description: 'Basic vulnerabilities suitable for introductory training',
    vulnIds: ['default-creds', 'open-ssh', 'xss', 'world-writable', 'anonymous-ftp'],
  },
  intermediate: {
    name: 'Intermediate (12 vulns)',
    description: 'Moderate challenge with common attack vectors',
    vulnIds: [
      'default-creds',
      'open-ssh',
      'open-rdp',
      'sqli',
      'xss',
      'lfi',
      'weak-mysql',
      'password-reuse',
      'world-writable',
      'sudo-nopass',
      'anonymous-ftp',
      'open-telnet',
    ],
  },
  advanced: {
    name: 'Advanced (20+ vulns)',
    description: 'Complex attack chains requiring advanced techniques',
    vulnIds: VULNERABILITY_CATALOG.map((v) => v.id),
  },
  custom: {
    name: 'Custom',
    description: 'Select individual vulnerabilities per VM',
    vulnIds: [],
  },
};
