// frontend/src/stores/wizardStore.ts
import { create } from 'zustand';

// Environment types
export type EnvironmentType = 'enterprise' | 'industrial' | 'cloud' | 'custom';
export type VulnPreset = 'none' | 'beginner' | 'intermediate' | 'advanced' | 'custom';

// Service definition
export interface ServiceConfig {
  id: string;
  name: string;
  osFamily: string;          // e.g., 'windows-server', 'ubuntu-server'
  defaultVersion: string;    // e.g., '2022', '22.04'
  description: string;
  category: 'infrastructure' | 'security' | 'application' | 'database';
  defaultNetwork: string;
  cpu?: number;
  ramMb?: number;
  diskGb?: number;
}

// Network segment for topology
export interface NetworkSegment {
  id: string;
  name: string;
  subnet: string;
  gateway: string;
  dhcp: boolean;
  isolated: boolean;
  vlan?: number;
  position: { x: number; y: number };
}

// VM placement in topology
export interface VMPlacement {
  id: string;
  hostname: string;
  templateId: string;
  templateName: string;
  networkId: string;
  ip: string;
  cpu: number;
  ramMb: number;
  diskGb: number;
  position: { x: number; y: number };

  // OS family/version for template resolution
  osFamily?: string;         // e.g., 'windows-server', 'ubuntu-server'
  osVersion?: string;        // e.g., '2022', '22.04'

  // OS-specific configuration (all optional)
  // Credentials (all OS types)
  username?: string;
  password?: string;
  sudoEnabled?: boolean;

  // Network settings (Windows & Linux ISO only)
  useDhcp?: boolean;
  gateway?: string;
  dnsServers?: string;

  // Additional storage (Windows & Linux ISO only)
  disk2Gb?: number;
  disk3Gb?: number;

  // Shared folders (all OS types)
  enableSharedFolder?: boolean;
  enableGlobalShared?: boolean;

  // Display type (Windows & Linux ISO only)
  displayType?: 'desktop' | 'server';

  // Locale settings (Windows & Linux ISO only)
  language?: string;
  keyboard?: string;
  region?: string;
}

// Connection between network elements
export interface NetworkConnection {
  id: string;
  sourceId: string;
  targetId: string;
}

// User group for range
export interface UserGroup {
  id: string;
  name: string;
  role: 'red-team' | 'blue-team' | 'white-cell' | 'observer' | 'custom';
  count: number;
  accessLevel: 'full' | 'limited' | 'readonly';
}

// Individual user
export interface RangeUser {
  id: string;
  username: string;
  groupId: string;
  role: string;
}

// Access rule
export interface AccessRule {
  groupId: string;
  networkIds: string[];
  accessType: 'full' | 'limited' | 'none';
}

// Wizard state interface
export interface WizardState {
  // Navigation
  currentStep: number;

  // Step 1: Environment
  environment: {
    type: EnvironmentType;
    name: string;
    description: string;
  };

  // Step 2: Services
  services: {
    selected: string[];
    customVMs: VMPlacement[];
  };

  // Step 3: Networks
  networks: {
    segments: NetworkSegment[];
    connections: NetworkConnection[];
    vms: VMPlacement[];
  };

  // Step 4: Users
  users: {
    groups: UserGroup[];
    individuals: RangeUser[];
    accessRules: AccessRule[];
  };

  // Step 5: Vulnerabilities
  vulnerabilities: {
    preset: VulnPreset;
    perVm: Record<string, string[]>;
    narrative: string;
  };

  // Step 6: Review
  rangeName: string;
  saveAsBlueprint: boolean;

  // Validation
  isValid: (step: number) => boolean;

  // Actions
  setStep: (step: number) => void;
  nextStep: () => void;
  prevStep: () => void;

  // Environment actions
  setEnvironment: (env: Partial<WizardState['environment']>) => void;

  // Services actions
  toggleService: (serviceId: string) => void;
  addCustomVM: (vm: VMPlacement) => void;
  removeCustomVM: (vmId: string) => void;

  // Network actions
  addNetwork: (network: NetworkSegment) => void;
  updateNetwork: (id: string, data: Partial<NetworkSegment>) => void;
  removeNetwork: (id: string) => void;
  addVM: (vm: VMPlacement) => void;
  updateVM: (id: string, data: Partial<VMPlacement>) => void;
  removeVM: (id: string) => void;
  addConnection: (conn: NetworkConnection) => void;
  removeConnection: (id: string) => void;

  // User actions
  setGroupCount: (groupId: string, count: number) => void;
  addGroup: (group: UserGroup) => void;
  updateAccessRule: (rule: AccessRule) => void;

  // Vulnerability actions
  setVulnPreset: (preset: VulnPreset) => void;
  toggleVmVuln: (vmId: string, vulnId: string) => void;
  setNarrative: (text: string) => void;

  // Review actions
  setRangeName: (name: string) => void;
  setSaveAsBlueprint: (save: boolean) => void;

  // Reset
  reset: () => void;
}

const initialState = {
  currentStep: 0,
  environment: {
    type: 'enterprise' as EnvironmentType,
    name: '',
    description: '',
  },
  services: {
    selected: [],
    customVMs: [],
  },
  networks: {
    segments: [],
    connections: [],
    vms: [],
  },
  users: {
    groups: [
      { id: 'red-team', name: 'Red Team', role: 'red-team' as const, count: 0, accessLevel: 'full' as const },
      { id: 'blue-team', name: 'Blue Team', role: 'blue-team' as const, count: 0, accessLevel: 'limited' as const },
      { id: 'white-cell', name: 'White Cell', role: 'white-cell' as const, count: 0, accessLevel: 'full' as const },
      { id: 'observer', name: 'Observers', role: 'observer' as const, count: 0, accessLevel: 'readonly' as const },
    ],
    individuals: [],
    accessRules: [],
  },
  vulnerabilities: {
    preset: 'none' as VulnPreset,
    perVm: {},
    narrative: '',
  },
  rangeName: '',
  saveAsBlueprint: false,
};

export const useWizardStore = create<WizardState>((set, get) => ({
  ...initialState,

  isValid: (step: number) => {
    const state = get();
    switch (step) {
      case 0: return state.environment.type !== null;
      case 1: return state.services.selected.length > 0 || state.services.customVMs.length > 0;
      case 2: return state.networks.segments.length > 0 && state.networks.vms.length > 0;
      case 3: return true; // Users are optional
      case 4: return true; // Vulns are optional
      case 5: return state.rangeName.trim().length > 0;
      default: return false;
    }
  },

  setStep: (step) => set({ currentStep: step }),
  nextStep: () => set((s) => ({ currentStep: Math.min(s.currentStep + 1, 5) })),
  prevStep: () => set((s) => ({ currentStep: Math.max(s.currentStep - 1, 0) })),

  setEnvironment: (env) => set((s) => ({
    environment: { ...s.environment, ...env }
  })),

  toggleService: (serviceId) => set((s) => ({
    services: {
      ...s.services,
      selected: s.services.selected.includes(serviceId)
        ? s.services.selected.filter(id => id !== serviceId)
        : [...s.services.selected, serviceId],
    }
  })),

  addCustomVM: (vm) => set((s) => ({
    services: { ...s.services, customVMs: [...s.services.customVMs, vm] }
  })),

  removeCustomVM: (vmId) => set((s) => ({
    services: { ...s.services, customVMs: s.services.customVMs.filter(v => v.id !== vmId) }
  })),

  addNetwork: (network) => set((s) => ({
    networks: { ...s.networks, segments: [...s.networks.segments, network] }
  })),

  updateNetwork: (id, data) => set((s) => ({
    networks: {
      ...s.networks,
      segments: s.networks.segments.map(n => n.id === id ? { ...n, ...data } : n)
    }
  })),

  removeNetwork: (id) => set((s) => ({
    networks: {
      ...s.networks,
      segments: s.networks.segments.filter(n => n.id !== id),
      vms: s.networks.vms.filter(v => v.networkId !== id),
    }
  })),

  addVM: (vm) => set((s) => ({
    networks: { ...s.networks, vms: [...s.networks.vms, vm] }
  })),

  updateVM: (id, data) => set((s) => ({
    networks: {
      ...s.networks,
      vms: s.networks.vms.map(v => v.id === id ? { ...v, ...data } : v)
    }
  })),

  removeVM: (id) => set((s) => ({
    networks: { ...s.networks, vms: s.networks.vms.filter(v => v.id !== id) }
  })),

  addConnection: (conn) => set((s) => ({
    networks: { ...s.networks, connections: [...s.networks.connections, conn] }
  })),

  removeConnection: (id) => set((s) => ({
    networks: { ...s.networks, connections: s.networks.connections.filter(c => c.id !== id) }
  })),

  setGroupCount: (groupId, count) => set((s) => ({
    users: {
      ...s.users,
      groups: s.users.groups.map(g => g.id === groupId ? { ...g, count } : g),
    }
  })),

  addGroup: (group) => set((s) => ({
    users: { ...s.users, groups: [...s.users.groups, group] }
  })),

  updateAccessRule: (rule) => set((s) => ({
    users: {
      ...s.users,
      accessRules: [
        ...s.users.accessRules.filter(r => r.groupId !== rule.groupId),
        rule,
      ],
    }
  })),

  setVulnPreset: (preset) => set({ vulnerabilities: { ...get().vulnerabilities, preset } }),

  toggleVmVuln: (vmId, vulnId) => set((s) => {
    const current = s.vulnerabilities.perVm[vmId] || [];
    const updated = current.includes(vulnId)
      ? current.filter(v => v !== vulnId)
      : [...current, vulnId];
    return {
      vulnerabilities: {
        ...s.vulnerabilities,
        perVm: { ...s.vulnerabilities.perVm, [vmId]: updated }
      }
    };
  }),

  setNarrative: (text) => set((s) => ({
    vulnerabilities: { ...s.vulnerabilities, narrative: text }
  })),

  setRangeName: (name) => set({ rangeName: name }),
  setSaveAsBlueprint: (save) => set({ saveAsBlueprint: save }),

  reset: () => set(initialState),
}));
