# Range Wizard v2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a full-page Range Wizard at `/ranges/new` with 6 steps, React Flow network topology, and Zustand state management.

**Architecture:** Full-page wizard with sidebar navigation, Zustand store for wizard state, React Flow for interactive network topology (reusing existing `@xyflow/react` patterns), and API integration with existing `rangesApi`, `networksApi`, `vmsApi`.

**Tech Stack:** React 18, TypeScript, Zustand, @xyflow/react (v12), Tailwind CSS, existing CYROID API services.

---

## Task 1: Create Wizard Zustand Store

**Files:**
- Create: `frontend/src/stores/wizardStore.ts`

**Step 1: Create the store with initial state and types**

```typescript
// frontend/src/stores/wizardStore.ts
import { create } from 'zustand';

// Environment types
export type EnvironmentType = 'enterprise' | 'industrial' | 'cloud' | 'custom';
export type VulnPreset = 'none' | 'beginner' | 'intermediate' | 'advanced' | 'custom';

// Service definition
export interface ServiceConfig {
  id: string;
  name: string;
  templateName: string;
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
```

**Step 2: Verify store compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors related to wizardStore.ts

**Step 3: Commit**

```bash
git add frontend/src/stores/wizardStore.ts
git commit -m "feat(wizard): add Zustand store for Range Wizard v2 state management"
```

---

## Task 2: Create Wizard Layout Components

**Files:**
- Create: `frontend/src/components/wizard-v2/WizardLayout.tsx`
- Create: `frontend/src/components/wizard-v2/WizardSidebar.tsx`

**Step 1: Create WizardSidebar component**

```typescript
// frontend/src/components/wizard-v2/WizardSidebar.tsx
import { CheckCircle, Circle } from 'lucide-react';
import clsx from 'clsx';
import { useWizardStore } from '../../stores/wizardStore';

const STEPS = [
  { id: 0, title: 'Environment', description: 'Select environment type' },
  { id: 1, title: 'Services', description: 'Choose systems & services' },
  { id: 2, title: 'Networks', description: 'Design network topology' },
  { id: 3, title: 'Users', description: 'Configure user groups' },
  { id: 4, title: 'Vulnerabilities', description: 'Set attack surface' },
  { id: 5, title: 'Review', description: 'Review & deploy' },
];

export function WizardSidebar() {
  const { currentStep, setStep, isValid } = useWizardStore();

  return (
    <div className="w-64 bg-gray-50 border-r border-gray-200 p-4">
      <h2 className="text-lg font-semibold text-gray-900 mb-6">Range Wizard</h2>
      <nav className="space-y-2">
        {STEPS.map((step) => {
          const isComplete = step.id < currentStep && isValid(step.id);
          const isCurrent = step.id === currentStep;
          const isClickable = step.id <= currentStep || isValid(step.id - 1);

          return (
            <button
              key={step.id}
              onClick={() => isClickable && setStep(step.id)}
              disabled={!isClickable}
              className={clsx(
                'w-full flex items-start gap-3 p-3 rounded-lg text-left transition-colors',
                isCurrent && 'bg-primary-50 border border-primary-200',
                !isCurrent && isClickable && 'hover:bg-gray-100',
                !isClickable && 'opacity-50 cursor-not-allowed'
              )}
            >
              <div className="flex-shrink-0 mt-0.5">
                {isComplete ? (
                  <CheckCircle className="w-5 h-5 text-green-500" />
                ) : (
                  <Circle
                    className={clsx(
                      'w-5 h-5',
                      isCurrent ? 'text-primary-600' : 'text-gray-300'
                    )}
                    fill={isCurrent ? 'currentColor' : 'none'}
                  />
                )}
              </div>
              <div>
                <div
                  className={clsx(
                    'text-sm font-medium',
                    isCurrent ? 'text-primary-700' : 'text-gray-700'
                  )}
                >
                  {step.title}
                </div>
                <div className="text-xs text-gray-500">{step.description}</div>
              </div>
            </button>
          );
        })}
      </nav>
    </div>
  );
}
```

**Step 2: Create WizardLayout component**

```typescript
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
```

**Step 3: Create index export**

```typescript
// frontend/src/components/wizard-v2/index.ts
export { WizardLayout } from './WizardLayout';
export { WizardSidebar } from './WizardSidebar';
```

**Step 4: Verify components compile**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 5: Commit**

```bash
git add frontend/src/components/wizard-v2/
git commit -m "feat(wizard): add WizardLayout and WizardSidebar components"
```

---

## Task 3: Create Environment Step (Step 1)

**Files:**
- Create: `frontend/src/components/wizard-v2/steps/EnvironmentStep.tsx`

**Step 1: Create EnvironmentStep component**

```typescript
// frontend/src/components/wizard-v2/steps/EnvironmentStep.tsx
import { Building2, Factory, Cloud, Settings } from 'lucide-react';
import clsx from 'clsx';
import { useWizardStore, EnvironmentType } from '../../../stores/wizardStore';

interface EnvironmentOption {
  type: EnvironmentType;
  icon: typeof Building2;
  title: string;
  description: string;
  defaultNetworks: string[];
  suggestedServices: string[];
}

const ENVIRONMENT_OPTIONS: EnvironmentOption[] = [
  {
    type: 'enterprise',
    icon: Building2,
    title: 'Enterprise',
    description: 'Corporate network with DMZ, internal segments, Active Directory, and standard business services.',
    defaultNetworks: ['DMZ', 'Corporate', 'Management'],
    suggestedServices: ['Active Directory', 'DNS', 'Web Server', 'File Server'],
  },
  {
    type: 'industrial',
    icon: Factory,
    title: 'Industrial (OT/ICS)',
    description: 'Industrial control systems with SCADA, PLCs, and segmented IT/OT networks.',
    defaultNetworks: ['IT Network', 'OT Network', 'DMZ'],
    suggestedServices: ['HMI Workstation', 'Historian', 'Engineering Workstation', 'PLC Simulator'],
  },
  {
    type: 'cloud',
    icon: Cloud,
    title: 'Cloud',
    description: 'Cloud-native architecture with microservices, containers, and API gateways.',
    defaultNetworks: ['Public', 'Private', 'Database'],
    suggestedServices: ['API Gateway', 'Web App', 'Database', 'Cache'],
  },
  {
    type: 'custom',
    icon: Settings,
    title: 'Custom',
    description: 'Start with a blank canvas and build your own topology from scratch.',
    defaultNetworks: [],
    suggestedServices: [],
  },
];

export function EnvironmentStep() {
  const { environment, setEnvironment } = useWizardStore();

  const selectedOption = ENVIRONMENT_OPTIONS.find(o => o.type === environment.type);

  return (
    <div className="max-w-4xl mx-auto">
      <h2 className="text-2xl font-bold text-gray-900 mb-2">
        What type of environment are you building?
      </h2>
      <p className="text-gray-600 mb-8">
        Select an environment template to get started with pre-configured networks and suggested services.
      </p>

      {/* Environment type cards */}
      <div className="grid grid-cols-2 gap-4 mb-8">
        {ENVIRONMENT_OPTIONS.map((option) => {
          const Icon = option.icon;
          const isSelected = environment.type === option.type;

          return (
            <button
              key={option.type}
              onClick={() => setEnvironment({ type: option.type })}
              className={clsx(
                'flex flex-col items-center p-6 rounded-xl border-2 transition-all text-center',
                isSelected
                  ? 'border-primary-500 bg-primary-50 ring-2 ring-primary-200'
                  : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
              )}
            >
              <Icon
                className={clsx(
                  'w-12 h-12 mb-3',
                  isSelected ? 'text-primary-600' : 'text-gray-400'
                )}
              />
              <h3
                className={clsx(
                  'text-lg font-semibold mb-1',
                  isSelected ? 'text-primary-700' : 'text-gray-900'
                )}
              >
                {option.title}
              </h3>
              <div
                className={clsx(
                  'w-4 h-4 rounded-full border-2 mt-2',
                  isSelected
                    ? 'border-primary-500 bg-primary-500'
                    : 'border-gray-300'
                )}
              >
                {isSelected && (
                  <div className="w-full h-full flex items-center justify-center">
                    <div className="w-2 h-2 bg-white rounded-full" />
                  </div>
                )}
              </div>
            </button>
          );
        })}
      </div>

      {/* Selected environment details */}
      {selectedOption && (
        <div className="bg-gray-50 rounded-xl p-6 border border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            {selectedOption.title} Environment
          </h3>
          <p className="text-gray-600 mb-4">{selectedOption.description}</p>

          {selectedOption.defaultNetworks.length > 0 && (
            <div className="mb-3">
              <span className="text-sm font-medium text-gray-700">Default topology: </span>
              <span className="text-sm text-gray-600">
                {selectedOption.defaultNetworks.join(' → ')}
              </span>
            </div>
          )}

          {selectedOption.suggestedServices.length > 0 && (
            <div>
              <span className="text-sm font-medium text-gray-700">Suggested services: </span>
              <span className="text-sm text-gray-600">
                {selectedOption.suggestedServices.join(', ')}
              </span>
            </div>
          )}

          {selectedOption.type === 'custom' && (
            <p className="text-sm text-gray-500 italic">
              You'll configure everything manually in the next steps.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
```

**Step 2: Verify component compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 3: Commit**

```bash
git add frontend/src/components/wizard-v2/steps/EnvironmentStep.tsx
git commit -m "feat(wizard): add EnvironmentStep component for environment type selection"
```

---

## Task 4: Create Services Step (Step 2)

**Files:**
- Create: `frontend/src/components/wizard-v2/steps/ServicesStep.tsx`
- Create: `frontend/src/components/wizard-v2/data/servicePresets.ts`

**Step 1: Create service presets data**

```typescript
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
```

**Step 2: Create ServicesStep component**

```typescript
// frontend/src/components/wizard-v2/steps/ServicesStep.tsx
import { useEffect, useState } from 'react';
import { Plus, Cpu, HardDrive, MemoryStick, X } from 'lucide-react';
import clsx from 'clsx';
import { useWizardStore, VMPlacement } from '../../../stores/wizardStore';
import { SERVICE_CATALOG, getServicesForEnvironment } from '../data/servicePresets';
import { templatesApi } from '../../../services/api';
import type { VMTemplate } from '../../../types';

export function ServicesStep() {
  const { environment, services, toggleService, addCustomVM, removeCustomVM } = useWizardStore();
  const [templates, setTemplates] = useState<VMTemplate[]>([]);
  const [showTemplateModal, setShowTemplateModal] = useState(false);

  // Load templates on mount
  useEffect(() => {
    templatesApi.list().then(res => setTemplates(res.data));
  }, []);

  // Auto-select recommended services when environment changes
  useEffect(() => {
    const recommended = getServicesForEnvironment(environment.type);
    // Only auto-select if no services selected yet
    if (services.selected.length === 0 && recommended.length > 0) {
      recommended.forEach(id => {
        if (!services.selected.includes(id)) {
          toggleService(id);
        }
      });
    }
  }, [environment.type]);

  const recommended = getServicesForEnvironment(environment.type);
  const selectedServices = SERVICE_CATALOG.filter(s => services.selected.includes(s.id));

  // Calculate estimated resources
  const totalCpu = selectedServices.reduce((sum, s) => sum + (s.cpu || 2), 0) +
    services.customVMs.reduce((sum, v) => sum + v.cpu, 0);
  const totalRam = selectedServices.reduce((sum, s) => sum + (s.ramMb || 2048), 0) +
    services.customVMs.reduce((sum, v) => sum + v.ramMb, 0);

  const handleAddCustomVM = (template: VMTemplate) => {
    const vm: VMPlacement = {
      id: `custom-${Date.now()}`,
      hostname: template.name.toLowerCase().replace(/\s+/g, '-'),
      templateId: template.id,
      templateName: template.name,
      networkId: '',
      ip: '',
      cpu: template.default_cpu,
      ramMb: template.default_ram_mb,
      diskGb: template.default_disk_gb,
      position: { x: 0, y: 0 },
    };
    addCustomVM(vm);
    setShowTemplateModal(false);
  };

  return (
    <div className="max-w-5xl mx-auto">
      <h2 className="text-2xl font-bold text-gray-900 mb-2">
        Select Services & Systems
      </h2>
      <p className="text-gray-600 mb-8">
        Choose which services to include in your range. We'll auto-generate VMs based on your selections.
      </p>

      <div className="grid grid-cols-2 gap-8">
        {/* Service selection */}
        <div>
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            {environment.type === 'custom' ? 'Available Services' : `Recommended for ${environment.type}`}
          </h3>
          <div className="space-y-2">
            {SERVICE_CATALOG.map((service) => {
              const isSelected = services.selected.includes(service.id);
              const isRecommended = recommended.includes(service.id);

              return (
                <label
                  key={service.id}
                  className={clsx(
                    'flex items-center p-3 rounded-lg border cursor-pointer transition-colors',
                    isSelected
                      ? 'border-primary-300 bg-primary-50'
                      : 'border-gray-200 hover:bg-gray-50'
                  )}
                >
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => toggleService(service.id)}
                    className="h-4 w-4 text-primary-600 rounded border-gray-300"
                  />
                  <div className="ml-3 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-900">
                        {service.name}
                      </span>
                      {isRecommended && (
                        <span className="px-1.5 py-0.5 text-[10px] font-medium bg-green-100 text-green-700 rounded">
                          Recommended
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-gray-500">{service.description}</p>
                  </div>
                </label>
              );
            })}
          </div>

          <button
            onClick={() => setShowTemplateModal(true)}
            className="mt-4 w-full inline-flex items-center justify-center px-4 py-2 text-sm font-medium text-primary-600 bg-primary-50 rounded-lg hover:bg-primary-100"
          >
            <Plus className="h-4 w-4 mr-2" />
            Add Custom Service
          </button>
        </div>

        {/* Generated VMs preview */}
        <div>
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            Your Selections
          </h3>

          {selectedServices.length === 0 && services.customVMs.length === 0 ? (
            <div className="text-center py-8 bg-gray-50 rounded-lg border border-dashed border-gray-300">
              <p className="text-gray-500">Select services from the left to add VMs</p>
            </div>
          ) : (
            <div className="space-y-2 mb-4">
              {selectedServices.map((service) => (
                <div
                  key={service.id}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                >
                  <div>
                    <div className="text-sm font-medium text-gray-900">{service.name}</div>
                    <div className="text-xs text-gray-500">{service.templateName}</div>
                  </div>
                  <button
                    onClick={() => toggleService(service.id)}
                    className="text-gray-400 hover:text-red-500"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              ))}

              {services.customVMs.map((vm) => (
                <div
                  key={vm.id}
                  className="flex items-center justify-between p-3 bg-blue-50 rounded-lg"
                >
                  <div>
                    <div className="text-sm font-medium text-gray-900">{vm.hostname}</div>
                    <div className="text-xs text-gray-500">{vm.templateName} (Custom)</div>
                  </div>
                  <button
                    onClick={() => removeCustomVM(vm.id)}
                    className="text-gray-400 hover:text-red-500"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Resource summary */}
          <div className="bg-gray-100 rounded-lg p-4 mt-4">
            <div className="text-sm font-medium text-gray-700 mb-2">Estimated Resources</div>
            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <div className="flex items-center justify-center text-gray-400 mb-1">
                  <HardDrive className="h-4 w-4" />
                </div>
                <div className="text-lg font-semibold text-gray-900">
                  {selectedServices.length + services.customVMs.length}
                </div>
                <div className="text-xs text-gray-500">VMs</div>
              </div>
              <div>
                <div className="flex items-center justify-center text-gray-400 mb-1">
                  <Cpu className="h-4 w-4" />
                </div>
                <div className="text-lg font-semibold text-gray-900">{totalCpu}</div>
                <div className="text-xs text-gray-500">vCPUs</div>
              </div>
              <div>
                <div className="flex items-center justify-center text-gray-400 mb-1">
                  <MemoryStick className="h-4 w-4" />
                </div>
                <div className="text-lg font-semibold text-gray-900">
                  {(totalRam / 1024).toFixed(1)}
                </div>
                <div className="text-xs text-gray-500">GB RAM</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Template selection modal */}
      {showTemplateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md max-h-[80vh] overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3 border-b">
              <h3 className="text-lg font-semibold">Select Template</h3>
              <button onClick={() => setShowTemplateModal(false)}>
                <X className="h-5 w-5 text-gray-400 hover:text-gray-500" />
              </button>
            </div>
            <div className="p-4 overflow-y-auto max-h-[60vh]">
              {templates.length === 0 ? (
                <p className="text-gray-500 text-center py-4">Loading templates...</p>
              ) : (
                <div className="space-y-2">
                  {templates.map((template) => (
                    <button
                      key={template.id}
                      onClick={() => handleAddCustomVM(template)}
                      className="w-full text-left p-3 rounded-lg border border-gray-200 hover:bg-gray-50"
                    >
                      <div className="text-sm font-medium text-gray-900">{template.name}</div>
                      <div className="text-xs text-gray-500">
                        {template.os_type} | {template.default_cpu} CPU, {template.default_ram_mb}MB RAM
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
```

**Step 3: Verify components compile**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 4: Commit**

```bash
git add frontend/src/components/wizard-v2/steps/ServicesStep.tsx frontend/src/components/wizard-v2/data/servicePresets.ts
git commit -m "feat(wizard): add ServicesStep with service catalog and auto-generation"
```

---

## Task 5: Create Network Topology Step (Step 3) - React Flow Integration

**Files:**
- Create: `frontend/src/components/wizard-v2/steps/NetworkStep.tsx`
- Create: `frontend/src/components/wizard-v2/nodes/WizardNetworkNode.tsx`
- Create: `frontend/src/components/wizard-v2/nodes/WizardVMNode.tsx`
- Create: `frontend/src/components/wizard-v2/panels/NetworkPropertiesPanel.tsx`

**Step 1: Create WizardNetworkNode component**

```typescript
// frontend/src/components/wizard-v2/nodes/WizardNetworkNode.tsx
import { memo } from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import { Network, Shield } from 'lucide-react';
import clsx from 'clsx';
import { NetworkSegment } from '../../../stores/wizardStore';

interface WizardNetworkNodeData {
  segment: NetworkSegment;
  onSelect: (id: string) => void;
  isSelected: boolean;
}

export const WizardNetworkNode = memo(({ data }: NodeProps<WizardNetworkNodeData>) => {
  const { segment, onSelect, isSelected } = data;

  return (
    <div
      onClick={() => onSelect(segment.id)}
      className={clsx(
        'px-4 py-3 rounded-xl border-2 shadow-md min-w-[280px] cursor-pointer transition-all',
        isSelected && 'ring-2 ring-primary-400',
        segment.isolated
          ? 'border-blue-400 bg-blue-50'
          : 'border-green-400 bg-green-50'
      )}
    >
      <Handle type="target" position={Position.Top} className="w-3 h-3 !bg-gray-400" />

      <div className="flex items-center gap-2 mb-2">
        <Network className="w-5 h-5 text-gray-600" />
        <div className="flex-1">
          <div className="text-sm font-semibold text-gray-900">{segment.name}</div>
          <div className="text-xs text-gray-500">{segment.subnet}</div>
        </div>
        <span
          className={clsx(
            'flex items-center gap-1 px-2 py-0.5 text-[10px] font-medium rounded',
            segment.isolated ? 'bg-blue-100 text-blue-700' : 'bg-green-100 text-green-700'
          )}
        >
          <Shield className="w-3 h-3" />
          {segment.isolated ? 'Isolated' : 'Open'}
        </span>
      </div>

      <div className="text-[10px] text-gray-400">
        Gateway: {segment.gateway}
        {segment.dhcp && ' | DHCP'}
      </div>

      <Handle type="source" position={Position.Bottom} className="w-3 h-3 !bg-gray-400" />
    </div>
  );
});

WizardNetworkNode.displayName = 'WizardNetworkNode';
```

**Step 2: Create WizardVMNode component**

```typescript
// frontend/src/components/wizard-v2/nodes/WizardVMNode.tsx
import { memo } from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import { Server, Cpu, MemoryStick } from 'lucide-react';
import clsx from 'clsx';
import { VMPlacement } from '../../../stores/wizardStore';

interface WizardVMNodeData {
  vm: VMPlacement;
  onSelect: (id: string) => void;
  isSelected: boolean;
}

export const WizardVMNode = memo(({ data }: NodeProps<WizardVMNodeData>) => {
  const { vm, onSelect, isSelected } = data;

  return (
    <div
      onClick={(e) => {
        e.stopPropagation();
        onSelect(vm.id);
      }}
      className={clsx(
        'px-3 py-2 rounded-lg border-2 shadow-sm min-w-[160px] cursor-pointer transition-all bg-white',
        isSelected ? 'border-primary-500 ring-2 ring-primary-200' : 'border-gray-300 hover:border-gray-400'
      )}
    >
      <Handle type="target" position={Position.Top} className="w-2 h-2 !bg-gray-400" />

      <div className="flex items-center gap-2 mb-1">
        <Server className="w-4 h-4 text-gray-500" />
        <span className="text-sm font-medium text-gray-900 truncate">{vm.hostname}</span>
      </div>

      <div className="text-xs text-gray-500 mb-1">{vm.templateName}</div>

      <div className="flex items-center gap-2 text-[10px] text-gray-400">
        <span className="flex items-center gap-0.5">
          <Cpu className="w-3 h-3" />
          {vm.cpu}
        </span>
        <span className="flex items-center gap-0.5">
          <MemoryStick className="w-3 h-3" />
          {vm.ramMb}MB
        </span>
        {vm.ip && <span>IP: {vm.ip}</span>}
      </div>

      <Handle type="source" position={Position.Bottom} className="w-2 h-2 !bg-gray-400" />
    </div>
  );
});

WizardVMNode.displayName = 'WizardVMNode';
```

**Step 3: Create NetworkPropertiesPanel component**

```typescript
// frontend/src/components/wizard-v2/panels/NetworkPropertiesPanel.tsx
import { X, Trash2 } from 'lucide-react';
import { useWizardStore, NetworkSegment, VMPlacement } from '../../../stores/wizardStore';

interface Props {
  selectedNetworkId: string | null;
  selectedVmId: string | null;
  onClose: () => void;
}

export function NetworkPropertiesPanel({ selectedNetworkId, selectedVmId, onClose }: Props) {
  const { networks, updateNetwork, removeNetwork, updateVM, removeVM } = useWizardStore();

  const selectedNetwork = networks.segments.find(n => n.id === selectedNetworkId);
  const selectedVm = networks.vms.find(v => v.id === selectedVmId);

  if (!selectedNetwork && !selectedVm) {
    return null;
  }

  if (selectedNetwork) {
    return (
      <div className="absolute bottom-0 left-0 right-0 bg-white border-t border-gray-200 p-4 shadow-lg">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-gray-900">Network Properties</h3>
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                removeNetwork(selectedNetwork.id);
                onClose();
              }}
              className="text-red-500 hover:text-red-600"
            >
              <Trash2 className="w-4 h-4" />
            </button>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-500">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="grid grid-cols-4 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Name</label>
            <input
              type="text"
              value={selectedNetwork.name}
              onChange={(e) => updateNetwork(selectedNetwork.id, { name: e.target.value })}
              className="w-full px-2 py-1 text-sm border border-gray-300 rounded"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Subnet</label>
            <input
              type="text"
              value={selectedNetwork.subnet}
              onChange={(e) => updateNetwork(selectedNetwork.id, { subnet: e.target.value })}
              className="w-full px-2 py-1 text-sm border border-gray-300 rounded"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Gateway</label>
            <input
              type="text"
              value={selectedNetwork.gateway}
              onChange={(e) => updateNetwork(selectedNetwork.id, { gateway: e.target.value })}
              className="w-full px-2 py-1 text-sm border border-gray-300 rounded"
            />
          </div>
          <div className="flex items-end gap-4">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={selectedNetwork.dhcp}
                onChange={(e) => updateNetwork(selectedNetwork.id, { dhcp: e.target.checked })}
                className="rounded border-gray-300"
              />
              DHCP
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={selectedNetwork.isolated}
                onChange={(e) => updateNetwork(selectedNetwork.id, { isolated: e.target.checked })}
                className="rounded border-gray-300"
              />
              Isolated
            </label>
          </div>
        </div>
      </div>
    );
  }

  if (selectedVm) {
    return (
      <div className="absolute bottom-0 left-0 right-0 bg-white border-t border-gray-200 p-4 shadow-lg">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-gray-900">VM Properties</h3>
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                removeVM(selectedVm.id);
                onClose();
              }}
              className="text-red-500 hover:text-red-600"
            >
              <Trash2 className="w-4 h-4" />
            </button>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-500">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="grid grid-cols-5 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Hostname</label>
            <input
              type="text"
              value={selectedVm.hostname}
              onChange={(e) => updateVM(selectedVm.id, { hostname: e.target.value })}
              className="w-full px-2 py-1 text-sm border border-gray-300 rounded"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">IP Address</label>
            <input
              type="text"
              value={selectedVm.ip}
              onChange={(e) => updateVM(selectedVm.id, { ip: e.target.value })}
              className="w-full px-2 py-1 text-sm border border-gray-300 rounded"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">CPU</label>
            <input
              type="number"
              min={1}
              max={16}
              value={selectedVm.cpu}
              onChange={(e) => updateVM(selectedVm.id, { cpu: parseInt(e.target.value) || 1 })}
              className="w-full px-2 py-1 text-sm border border-gray-300 rounded"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">RAM (MB)</label>
            <input
              type="number"
              min={512}
              step={512}
              value={selectedVm.ramMb}
              onChange={(e) => updateVM(selectedVm.id, { ramMb: parseInt(e.target.value) || 1024 })}
              className="w-full px-2 py-1 text-sm border border-gray-300 rounded"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Disk (GB)</label>
            <input
              type="number"
              min={10}
              value={selectedVm.diskGb}
              onChange={(e) => updateVM(selectedVm.id, { diskGb: parseInt(e.target.value) || 20 })}
              className="w-full px-2 py-1 text-sm border border-gray-300 rounded"
            />
          </div>
        </div>
      </div>
    );
  }

  return null;
}
```

**Step 4: Create NetworkStep component with React Flow**

```typescript
// frontend/src/components/wizard-v2/steps/NetworkStep.tsx
import { useCallback, useMemo, useState, useEffect } from 'react';
import {
  ReactFlow,
  Controls,
  Background,
  BackgroundVariant,
  applyNodeChanges,
  applyEdgeChanges,
  addEdge,
  Node,
  Edge,
  OnNodesChange,
  OnEdgesChange,
  OnConnect,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Plus, Network, Server } from 'lucide-react';
import { useWizardStore, NetworkSegment, VMPlacement } from '../../../stores/wizardStore';
import { WizardNetworkNode } from '../nodes/WizardNetworkNode';
import { WizardVMNode } from '../nodes/WizardVMNode';
import { NetworkPropertiesPanel } from '../panels/NetworkPropertiesPanel';
import { SERVICE_CATALOG } from '../data/servicePresets';

export function NetworkStep() {
  const { environment, services, networks, addNetwork, addVM, updateVM, addConnection, removeConnection } = useWizardStore();
  const [selectedNetworkId, setSelectedNetworkId] = useState<string | null>(null);
  const [selectedVmId, setSelectedVmId] = useState<string | null>(null);

  // Initialize networks from environment preset if empty
  useEffect(() => {
    if (networks.segments.length === 0 && environment.type !== 'custom') {
      const presetNetworks = getPresetNetworks(environment.type);
      presetNetworks.forEach((net, i) => {
        addNetwork({
          ...net,
          id: `network-${Date.now()}-${i}`,
          position: { x: 100 + i * 400, y: 100 },
        });
      });
    }
  }, [environment.type]);

  // Initialize VMs from selected services if empty
  useEffect(() => {
    if (networks.vms.length === 0 && services.selected.length > 0 && networks.segments.length > 0) {
      services.selected.forEach((serviceId, i) => {
        const service = SERVICE_CATALOG.find(s => s.id === serviceId);
        if (service) {
          const targetNetwork = networks.segments.find(n =>
            n.name.toLowerCase().includes(service.defaultNetwork.toLowerCase())
          ) || networks.segments[0];

          if (targetNetwork) {
            const baseIp = targetNetwork.subnet.replace('.0/24', '');
            addVM({
              id: `vm-${Date.now()}-${i}`,
              hostname: service.name.toLowerCase().replace(/\s+/g, '-'),
              templateId: '',
              templateName: service.templateName,
              networkId: targetNetwork.id,
              ip: `${baseIp}.${10 + i}`,
              cpu: service.cpu || 2,
              ramMb: service.ramMb || 2048,
              diskGb: service.diskGb || 20,
              position: { x: targetNetwork.position.x + 50, y: targetNetwork.position.y + 150 + i * 80 },
            });
          }
        }
      });
    }
  }, [services.selected, networks.segments.length]);

  // Convert to React Flow nodes
  const nodes: Node[] = useMemo(() => {
    const networkNodes: Node[] = networks.segments.map((segment) => ({
      id: segment.id,
      type: 'wizardNetwork',
      position: segment.position,
      data: {
        segment,
        onSelect: (id: string) => {
          setSelectedNetworkId(id);
          setSelectedVmId(null);
        },
        isSelected: selectedNetworkId === segment.id,
      },
    }));

    const vmNodes: Node[] = networks.vms.map((vm) => ({
      id: vm.id,
      type: 'wizardVm',
      position: vm.position,
      data: {
        vm,
        onSelect: (id: string) => {
          setSelectedVmId(id);
          setSelectedNetworkId(null);
        },
        isSelected: selectedVmId === vm.id,
      },
    }));

    return [...networkNodes, ...vmNodes];
  }, [networks.segments, networks.vms, selectedNetworkId, selectedVmId]);

  // Convert to React Flow edges
  const edges: Edge[] = useMemo(() => {
    // VM to Network edges
    const vmEdges = networks.vms
      .filter(vm => vm.networkId)
      .map((vm) => ({
        id: `edge-vm-${vm.id}`,
        source: vm.networkId,
        target: vm.id,
        type: 'smoothstep',
        animated: true,
        style: { stroke: '#6b7280' },
      }));

    // Network to Network edges
    const netEdges = networks.connections.map((conn) => ({
      id: conn.id,
      source: conn.sourceId,
      target: conn.targetId,
      type: 'smoothstep',
      style: { stroke: '#3b82f6', strokeWidth: 2 },
    }));

    return [...vmEdges, ...netEdges];
  }, [networks.vms, networks.connections]);

  const nodeTypes = useMemo(() => ({
    wizardNetwork: WizardNetworkNode,
    wizardVm: WizardVMNode,
  }), []);

  const [flowNodes, setFlowNodes] = useState<Node[]>(nodes);
  const [flowEdges, setFlowEdges] = useState<Edge[]>(edges);

  // Sync with store changes
  useEffect(() => {
    setFlowNodes(nodes);
  }, [nodes]);

  useEffect(() => {
    setFlowEdges(edges);
  }, [edges]);

  const onNodesChange: OnNodesChange = useCallback((changes) => {
    setFlowNodes((nds) => applyNodeChanges(changes, nds));

    // Update positions in store
    changes.forEach((change) => {
      if (change.type === 'position' && change.position && !change.dragging) {
        const node = networks.segments.find(n => n.id === change.id);
        if (node) {
          // Network position update would go here
        } else {
          const vm = networks.vms.find(v => v.id === change.id);
          if (vm) {
            updateVM(change.id, { position: change.position });
          }
        }
      }
    });
  }, [networks.segments, networks.vms, updateVM]);

  const onEdgesChange: OnEdgesChange = useCallback((changes) => {
    setFlowEdges((eds) => applyEdgeChanges(changes, eds));
  }, []);

  const onConnect: OnConnect = useCallback((connection) => {
    if (connection.source && connection.target) {
      // Check if it's a network-to-network connection
      const sourceNetwork = networks.segments.find(n => n.id === connection.source);
      const targetNetwork = networks.segments.find(n => n.id === connection.target);

      if (sourceNetwork && targetNetwork) {
        addConnection({
          id: `conn-${Date.now()}`,
          sourceId: connection.source,
          targetId: connection.target,
        });
      } else {
        // VM to network connection - update VM's networkId
        const vm = networks.vms.find(v => v.id === connection.target);
        if (vm && sourceNetwork) {
          updateVM(vm.id, { networkId: connection.source });
        }
      }
    }
    setFlowEdges((eds) => addEdge(connection, eds));
  }, [networks.segments, networks.vms, addConnection, updateVM]);

  const handleAddNetwork = () => {
    const id = `network-${Date.now()}`;
    const num = networks.segments.length + 1;
    addNetwork({
      id,
      name: `Network ${num}`,
      subnet: `10.${num}.0.0/24`,
      gateway: `10.${num}.0.1`,
      dhcp: false,
      isolated: false,
      position: { x: 100 + (num - 1) * 400, y: 100 },
    });
  };

  const handleAddVM = () => {
    if (networks.segments.length === 0) return;

    const targetNetwork = networks.segments[0];
    const id = `vm-${Date.now()}`;
    const num = networks.vms.length + 1;
    const baseIp = targetNetwork.subnet.replace('.0/24', '');

    addVM({
      id,
      hostname: `vm-${num}`,
      templateId: '',
      templateName: 'Ubuntu Server',
      networkId: targetNetwork.id,
      ip: `${baseIp}.${10 + num}`,
      cpu: 2,
      ramMb: 2048,
      diskGb: 20,
      position: { x: targetNetwork.position.x + 50, y: targetNetwork.position.y + 150 + (num - 1) * 80 },
    });
  };

  return (
    <div className="h-[calc(100vh-280px)] flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Network Topology</h2>
          <p className="text-gray-600">Design your network layout. Drag nodes to reposition, click to configure.</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleAddNetwork}
            className="inline-flex items-center px-3 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
          >
            <Network className="w-4 h-4 mr-2" />
            Add Network
          </button>
          <button
            onClick={handleAddVM}
            disabled={networks.segments.length === 0}
            className="inline-flex items-center px-3 py-2 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
          >
            <Server className="w-4 h-4 mr-2" />
            Add VM
          </button>
        </div>
      </div>

      <div className="flex-1 border border-gray-200 rounded-lg overflow-hidden relative">
        <ReactFlow
          nodes={flowNodes}
          edges={flowEdges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          nodeTypes={nodeTypes}
          fitView
          snapToGrid
          snapGrid={[20, 20]}
          onClick={() => {
            setSelectedNetworkId(null);
            setSelectedVmId(null);
          }}
        >
          <Controls />
          <Background variant={BackgroundVariant.Dots} gap={20} size={1} />
        </ReactFlow>

        <NetworkPropertiesPanel
          selectedNetworkId={selectedNetworkId}
          selectedVmId={selectedVmId}
          onClose={() => {
            setSelectedNetworkId(null);
            setSelectedVmId(null);
          }}
        />
      </div>
    </div>
  );
}

function getPresetNetworks(envType: string): Omit<NetworkSegment, 'id' | 'position'>[] {
  switch (envType) {
    case 'enterprise':
      return [
        { name: 'DMZ', subnet: '10.1.0.0/24', gateway: '10.1.0.1', dhcp: false, isolated: false },
        { name: 'Corporate', subnet: '10.2.0.0/24', gateway: '10.2.0.1', dhcp: true, isolated: false },
        { name: 'Management', subnet: '10.3.0.0/24', gateway: '10.3.0.1', dhcp: false, isolated: true },
      ];
    case 'industrial':
      return [
        { name: 'IT Network', subnet: '10.1.0.0/24', gateway: '10.1.0.1', dhcp: true, isolated: false },
        { name: 'OT Network', subnet: '10.2.0.0/24', gateway: '10.2.0.1', dhcp: false, isolated: true },
        { name: 'DMZ', subnet: '10.3.0.0/24', gateway: '10.3.0.1', dhcp: false, isolated: false },
      ];
    case 'cloud':
      return [
        { name: 'Public', subnet: '10.1.0.0/24', gateway: '10.1.0.1', dhcp: false, isolated: false },
        { name: 'Private', subnet: '10.2.0.0/24', gateway: '10.2.0.1', dhcp: true, isolated: true },
        { name: 'Database', subnet: '10.3.0.0/24', gateway: '10.3.0.1', dhcp: false, isolated: true },
      ];
    default:
      return [];
  }
}
```

**Step 5: Verify components compile**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 6: Commit**

```bash
git add frontend/src/components/wizard-v2/steps/NetworkStep.tsx frontend/src/components/wizard-v2/nodes/ frontend/src/components/wizard-v2/panels/
git commit -m "feat(wizard): add NetworkStep with React Flow topology editor"
```

---

## Task 6: Create Users Step (Step 4)

**Files:**
- Create: `frontend/src/components/wizard-v2/steps/UsersStep.tsx`

**Step 1: Create UsersStep component**

```typescript
// frontend/src/components/wizard-v2/steps/UsersStep.tsx
import { Users, UserPlus, Shield, Eye, Swords } from 'lucide-react';
import clsx from 'clsx';
import { useWizardStore } from '../../../stores/wizardStore';

const ROLE_ICONS = {
  'red-team': Swords,
  'blue-team': Shield,
  'white-cell': Users,
  'observer': Eye,
  'custom': UserPlus,
};

const ROLE_COLORS = {
  'red-team': 'text-red-600 bg-red-50 border-red-200',
  'blue-team': 'text-blue-600 bg-blue-50 border-blue-200',
  'white-cell': 'text-purple-600 bg-purple-50 border-purple-200',
  'observer': 'text-gray-600 bg-gray-50 border-gray-200',
  'custom': 'text-green-600 bg-green-50 border-green-200',
};

export function UsersStep() {
  const { users, setGroupCount, networks } = useWizardStore();

  // Generate usernames based on group counts
  const generatedUsers = users.groups.flatMap((group) =>
    Array.from({ length: group.count }, (_, i) => ({
      id: `${group.id}-${i + 1}`,
      username: `${group.role.split('-')[0]}-${String(i + 1).padStart(2, '0')}`,
      group: group.name,
      role: group.role,
      accessLevel: group.accessLevel,
    }))
  );

  const totalUsers = generatedUsers.length;

  return (
    <div className="max-w-5xl mx-auto">
      <h2 className="text-2xl font-bold text-gray-900 mb-2">Users & Groups</h2>
      <p className="text-gray-600 mb-8">
        Configure team sizes and access levels. Users will be auto-generated based on your settings.
      </p>

      <div className="grid grid-cols-2 gap-8">
        {/* Team segments */}
        <div>
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Team Segments</h3>
          <div className="space-y-3">
            {users.groups.map((group) => {
              const Icon = ROLE_ICONS[group.role] || Users;
              const colors = ROLE_COLORS[group.role] || ROLE_COLORS.custom;

              return (
                <div
                  key={group.id}
                  className={clsx('flex items-center justify-between p-4 rounded-lg border', colors)}
                >
                  <div className="flex items-center gap-3">
                    <Icon className="w-5 h-5" />
                    <div>
                      <div className="font-medium">{group.name}</div>
                      <div className="text-xs opacity-75">
                        {group.accessLevel === 'full'
                          ? 'Full access to all VMs'
                          : group.accessLevel === 'limited'
                          ? 'Limited access'
                          : 'Read-only access'}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setGroupCount(group.id, Math.max(0, group.count - 1))}
                      className="w-8 h-8 flex items-center justify-center rounded bg-white border border-current text-current hover:bg-opacity-50"
                    >
                      -
                    </button>
                    <span className="w-8 text-center font-semibold">{group.count}</span>
                    <button
                      onClick={() => setGroupCount(group.id, Math.min(10, group.count + 1))}
                      className="w-8 h-8 flex items-center justify-center rounded bg-white border border-current text-current hover:bg-opacity-50"
                    >
                      +
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="mt-6 p-4 bg-gray-50 rounded-lg">
            <div className="text-sm font-medium text-gray-700 mb-2">Naming Pattern</div>
            <code className="text-sm text-gray-600 bg-gray-100 px-2 py-1 rounded">
              [team]-[number]
            </code>
            <div className="text-xs text-gray-500 mt-1">
              Example: red-01, blue-02, white-01
            </div>
          </div>
        </div>

        {/* Generated users preview */}
        <div>
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            Generated Users ({totalUsers})
          </h3>

          {totalUsers === 0 ? (
            <div className="text-center py-12 bg-gray-50 rounded-lg border border-dashed border-gray-300">
              <Users className="w-12 h-12 text-gray-300 mx-auto mb-3" />
              <p className="text-gray-500">
                Adjust team sizes to generate users
              </p>
              <p className="text-xs text-gray-400 mt-1">
                Users are optional - you can skip this step
              </p>
            </div>
          ) : (
            <div className="max-h-[400px] overflow-y-auto border border-gray-200 rounded-lg">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 sticky top-0">
                  <tr>
                    <th className="text-left px-4 py-2 font-medium text-gray-700">Username</th>
                    <th className="text-left px-4 py-2 font-medium text-gray-700">Team</th>
                    <th className="text-left px-4 py-2 font-medium text-gray-700">Access</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {generatedUsers.map((user) => (
                    <tr key={user.id} className="hover:bg-gray-50">
                      <td className="px-4 py-2 font-mono text-gray-900">{user.username}</td>
                      <td className="px-4 py-2 text-gray-600">{user.group}</td>
                      <td className="px-4 py-2">
                        <span
                          className={clsx(
                            'px-2 py-0.5 text-xs font-medium rounded',
                            user.accessLevel === 'full'
                              ? 'bg-green-100 text-green-700'
                              : user.accessLevel === 'limited'
                              ? 'bg-yellow-100 text-yellow-700'
                              : 'bg-gray-100 text-gray-600'
                          )}
                        >
                          {user.accessLevel}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Access rules summary */}
          {totalUsers > 0 && networks.segments.length > 0 && (
            <div className="mt-4 p-4 bg-blue-50 rounded-lg border border-blue-200">
              <div className="text-sm font-medium text-blue-800 mb-2">Access Rules</div>
              <ul className="text-sm text-blue-700 space-y-1">
                <li>• Red Team → Full access to all VMs</li>
                <li>• Blue Team → Access to defender workstations only</li>
                <li>• White Cell → Full access + console override</li>
                <li>• Observers → Read-only monitoring</li>
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
```

**Step 2: Verify component compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 3: Commit**

```bash
git add frontend/src/components/wizard-v2/steps/UsersStep.tsx
git commit -m "feat(wizard): add UsersStep with team segment configuration"
```

---

## Task 7: Create Vulnerabilities Step (Step 5)

**Files:**
- Create: `frontend/src/components/wizard-v2/steps/VulnsStep.tsx`
- Create: `frontend/src/components/wizard-v2/data/vulnPresets.ts`

**Step 1: Create vulnerability presets data**

```typescript
// frontend/src/components/wizard-v2/data/vulnPresets.ts
export interface VulnDefinition {
  id: string;
  name: string;
  description: string;
  category: 'network' | 'web' | 'credential' | 'misconfig';
  severity: 'low' | 'medium' | 'high' | 'critical';
  applicableTemplates: string[]; // Template names this vuln applies to
}

export const VULNERABILITY_CATALOG: VulnDefinition[] = [
  // Network Services
  { id: 'open-ssh', name: 'Open SSH (weak key)', description: 'SSH with weak or default keys', category: 'network', severity: 'high', applicableTemplates: ['Ubuntu Server', 'Kali Linux'] },
  { id: 'open-rdp', name: 'Open RDP', description: 'RDP exposed without NLA', category: 'network', severity: 'high', applicableTemplates: ['Windows Server 2019', 'Windows 10'] },
  { id: 'open-smb', name: 'Open SMB (EternalBlue)', description: 'SMBv1 vulnerable to MS17-010', category: 'network', severity: 'critical', applicableTemplates: ['Windows Server 2019', 'Windows 10'] },
  { id: 'open-telnet', name: 'Open Telnet', description: 'Telnet service exposed', category: 'network', severity: 'medium', applicableTemplates: ['Ubuntu Server'] },

  // Web Applications
  { id: 'sqli', name: 'SQL Injection', description: 'Web app vulnerable to SQLi', category: 'web', severity: 'critical', applicableTemplates: ['Ubuntu Server'] },
  { id: 'xss', name: 'Cross-Site Scripting', description: 'Reflected XSS in web app', category: 'web', severity: 'medium', applicableTemplates: ['Ubuntu Server'] },
  { id: 'lfi', name: 'Local File Inclusion', description: 'LFI vulnerability in web app', category: 'web', severity: 'high', applicableTemplates: ['Ubuntu Server'] },

  // Credentials
  { id: 'default-creds', name: 'Default Credentials', description: 'Service using default password', category: 'credential', severity: 'high', applicableTemplates: ['Ubuntu Server', 'Windows Server 2019'] },
  { id: 'weak-mysql', name: 'Weak MySQL Password', description: 'MySQL with root:root', category: 'credential', severity: 'high', applicableTemplates: ['Ubuntu Server'] },
  { id: 'password-reuse', name: 'Password Reuse', description: 'Same password across services', category: 'credential', severity: 'medium', applicableTemplates: ['Windows Server 2019', 'Ubuntu Server'] },

  // Misconfigurations
  { id: 'world-writable', name: 'World-Writable Dirs', description: 'Sensitive dirs with 777 perms', category: 'misconfig', severity: 'medium', applicableTemplates: ['Ubuntu Server'] },
  { id: 'sudo-nopass', name: 'SUDO No Password', description: 'User can sudo without password', category: 'misconfig', severity: 'high', applicableTemplates: ['Ubuntu Server', 'Kali Linux'] },
  { id: 'anonymous-ftp', name: 'Anonymous FTP', description: 'FTP allows anonymous login', category: 'misconfig', severity: 'medium', applicableTemplates: ['Ubuntu Server'] },
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
    vulnIds: ['default-creds', 'open-ssh', 'open-rdp', 'sqli', 'xss', 'lfi', 'weak-mysql', 'password-reuse', 'world-writable', 'sudo-nopass', 'anonymous-ftp', 'open-telnet'],
  },
  advanced: {
    name: 'Advanced (20+ vulns)',
    description: 'Complex attack chains requiring advanced techniques',
    vulnIds: VULNERABILITY_CATALOG.map(v => v.id),
  },
  custom: {
    name: 'Custom',
    description: 'Select individual vulnerabilities per VM',
    vulnIds: [],
  },
};
```

**Step 2: Create VulnsStep component**

```typescript
// frontend/src/components/wizard-v2/steps/VulnsStep.tsx
import { ShieldAlert, ShieldCheck, AlertTriangle, Bug, Key, Settings } from 'lucide-react';
import clsx from 'clsx';
import { useWizardStore, VulnPreset } from '../../../stores/wizardStore';
import { VULNERABILITY_CATALOG, VULN_PRESETS } from '../data/vulnPresets';

const CATEGORY_ICONS = {
  network: ShieldAlert,
  web: Bug,
  credential: Key,
  misconfig: Settings,
};

const SEVERITY_COLORS = {
  low: 'bg-green-100 text-green-700',
  medium: 'bg-yellow-100 text-yellow-700',
  high: 'bg-orange-100 text-orange-700',
  critical: 'bg-red-100 text-red-700',
};

export function VulnsStep() {
  const { networks, vulnerabilities, setVulnPreset, toggleVmVuln, setNarrative } = useWizardStore();

  const presetConfig = VULN_PRESETS[vulnerabilities.preset];

  // Get applicable vulns for each VM based on template
  const getApplicableVulns = (templateName: string) => {
    return VULNERABILITY_CATALOG.filter(v =>
      v.applicableTemplates.some(t =>
        templateName.toLowerCase().includes(t.toLowerCase())
      )
    );
  };

  return (
    <div className="max-w-5xl mx-auto">
      <h2 className="text-2xl font-bold text-gray-900 mb-2">Vulnerability Configuration</h2>
      <p className="text-gray-600 mb-8">
        Configure the attack surface for your training scenario. Select a preset or customize per VM.
      </p>

      <div className="grid grid-cols-2 gap-8">
        {/* Preset selection */}
        <div>
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Preset Profiles</h3>
          <div className="space-y-2">
            {(Object.entries(VULN_PRESETS) as [VulnPreset, typeof presetConfig][]).map(([key, preset]) => (
              <button
                key={key}
                onClick={() => setVulnPreset(key as VulnPreset)}
                className={clsx(
                  'w-full text-left p-4 rounded-lg border-2 transition-all',
                  vulnerabilities.preset === key
                    ? 'border-primary-500 bg-primary-50'
                    : 'border-gray-200 hover:border-gray-300'
                )}
              >
                <div className="flex items-center gap-3">
                  <div
                    className={clsx(
                      'w-4 h-4 rounded-full border-2',
                      vulnerabilities.preset === key
                        ? 'border-primary-500 bg-primary-500'
                        : 'border-gray-300'
                    )}
                  >
                    {vulnerabilities.preset === key && (
                      <div className="w-full h-full flex items-center justify-center">
                        <div className="w-2 h-2 bg-white rounded-full" />
                      </div>
                    )}
                  </div>
                  <div className="flex-1">
                    <div className="font-medium text-gray-900">{preset.name}</div>
                    <div className="text-sm text-gray-500">{preset.description}</div>
                  </div>
                  {key !== 'none' && key !== 'custom' && (
                    <span className="text-xs font-medium text-gray-400">
                      {preset.vulnIds.length} vulns
                    </span>
                  )}
                </div>
              </button>
            ))}
          </div>

          {/* Attack Narrative */}
          <div className="mt-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Attack Narrative (Optional)
            </label>
            <textarea
              value={vulnerabilities.narrative}
              onChange={(e) => setNarrative(e.target.value)}
              placeholder="Describe the intended attack path for this scenario..."
              rows={4}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-primary-500 focus:border-primary-500"
            />
            <p className="text-xs text-gray-500 mt-1">
              This helps with MSEL generation and scenario documentation
            </p>
          </div>
        </div>

        {/* Per-VM configuration */}
        <div>
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Per-VM Settings</h3>

          {networks.vms.length === 0 ? (
            <div className="text-center py-12 bg-gray-50 rounded-lg border border-dashed border-gray-300">
              <ShieldCheck className="w-12 h-12 text-gray-300 mx-auto mb-3" />
              <p className="text-gray-500">No VMs configured yet</p>
              <p className="text-xs text-gray-400">Add VMs in the Network step first</p>
            </div>
          ) : (
            <div className="space-y-4 max-h-[500px] overflow-y-auto">
              {networks.vms.map((vm) => {
                const applicableVulns = getApplicableVulns(vm.templateName);
                const enabledVulns = vulnerabilities.perVm[vm.id] ||
                  (vulnerabilities.preset !== 'custom'
                    ? presetConfig.vulnIds.filter(id =>
                        applicableVulns.some(v => v.id === id)
                      )
                    : []);

                return (
                  <div key={vm.id} className="border border-gray-200 rounded-lg overflow-hidden">
                    <div className="flex items-center justify-between px-4 py-2 bg-gray-50 border-b">
                      <div>
                        <div className="font-medium text-gray-900">{vm.hostname}</div>
                        <div className="text-xs text-gray-500">{vm.templateName}</div>
                      </div>
                      <span className="text-xs text-gray-500">
                        {enabledVulns.length} vulns enabled
                      </span>
                    </div>

                    {applicableVulns.length === 0 ? (
                      <div className="p-3 text-sm text-gray-500">
                        No vulnerabilities available for this template
                      </div>
                    ) : (
                      <div className="p-3 space-y-2">
                        {applicableVulns.map((vuln) => {
                          const Icon = CATEGORY_ICONS[vuln.category];
                          const isEnabled = enabledVulns.includes(vuln.id);

                          return (
                            <label
                              key={vuln.id}
                              className={clsx(
                                'flex items-center gap-2 p-2 rounded cursor-pointer transition-colors',
                                isEnabled ? 'bg-orange-50' : 'hover:bg-gray-50'
                              )}
                            >
                              <input
                                type="checkbox"
                                checked={isEnabled}
                                onChange={() => toggleVmVuln(vm.id, vuln.id)}
                                disabled={vulnerabilities.preset !== 'custom'}
                                className="rounded border-gray-300 text-primary-600"
                              />
                              <Icon className="w-4 h-4 text-gray-400" />
                              <span className="flex-1 text-sm text-gray-700">{vuln.name}</span>
                              <span className={clsx('px-1.5 py-0.5 text-[10px] font-medium rounded', SEVERITY_COLORS[vuln.severity])}>
                                {vuln.severity}
                              </span>
                            </label>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {vulnerabilities.preset !== 'custom' && networks.vms.length > 0 && (
            <p className="text-xs text-gray-500 mt-2 flex items-center gap-1">
              <AlertTriangle className="w-3 h-3" />
              Select "Custom" preset to modify individual VM vulnerabilities
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
```

**Step 3: Verify component compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 4: Commit**

```bash
git add frontend/src/components/wizard-v2/steps/VulnsStep.tsx frontend/src/components/wizard-v2/data/vulnPresets.ts
git commit -m "feat(wizard): add VulnsStep with preset profiles and per-VM configuration"
```

---

## Task 8: Create Review Step (Step 6)

**Files:**
- Create: `frontend/src/components/wizard-v2/steps/ReviewStep.tsx`

**Step 1: Create ReviewStep component**

```typescript
// frontend/src/components/wizard-v2/steps/ReviewStep.tsx
import { useState, useMemo } from 'react';
import {
  ReactFlow,
  Controls,
  Background,
  BackgroundVariant,
  Node,
  Edge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { ChevronDown, ChevronRight, Network, Server, Users, ShieldAlert, Check } from 'lucide-react';
import clsx from 'clsx';
import { useWizardStore } from '../../../stores/wizardStore';
import { WizardNetworkNode } from '../nodes/WizardNetworkNode';
import { WizardVMNode } from '../nodes/WizardVMNode';
import { VULN_PRESETS } from '../data/vulnPresets';

interface CollapsibleSectionProps {
  title: string;
  icon: typeof Network;
  count: number;
  children: React.ReactNode;
  defaultOpen?: boolean;
}

function CollapsibleSection({ title, icon: Icon, count, children, defaultOpen = false }: CollapsibleSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Icon className="w-4 h-4 text-gray-500" />
          <span className="font-medium text-gray-900">{title}</span>
          <span className="text-sm text-gray-500">({count})</span>
        </div>
        {isOpen ? (
          <ChevronDown className="w-4 h-4 text-gray-400" />
        ) : (
          <ChevronRight className="w-4 h-4 text-gray-400" />
        )}
      </button>
      {isOpen && <div className="p-4 border-t">{children}</div>}
    </div>
  );
}

export function ReviewStep() {
  const { environment, services, networks, users, vulnerabilities, rangeName, saveAsBlueprint, setRangeName, setSaveAsBlueprint } = useWizardStore();

  // Calculate totals
  const totalVms = networks.vms.length;
  const totalNetworks = networks.segments.length;
  const totalUsers = users.groups.reduce((sum, g) => sum + g.count, 0);
  const vulnPreset = VULN_PRESETS[vulnerabilities.preset];

  // Read-only React Flow nodes
  const nodes: Node[] = useMemo(() => {
    const networkNodes: Node[] = networks.segments.map((segment) => ({
      id: segment.id,
      type: 'wizardNetwork',
      position: segment.position,
      data: { segment, onSelect: () => {}, isSelected: false },
      draggable: false,
      selectable: false,
    }));

    const vmNodes: Node[] = networks.vms.map((vm) => ({
      id: vm.id,
      type: 'wizardVm',
      position: vm.position,
      data: { vm, onSelect: () => {}, isSelected: false },
      draggable: false,
      selectable: false,
    }));

    return [...networkNodes, ...vmNodes];
  }, [networks.segments, networks.vms]);

  const edges: Edge[] = useMemo(() => {
    return networks.vms
      .filter(vm => vm.networkId)
      .map((vm) => ({
        id: `edge-${vm.id}`,
        source: vm.networkId,
        target: vm.id,
        type: 'smoothstep',
        style: { stroke: '#6b7280' },
      }));
  }, [networks.vms]);

  const nodeTypes = useMemo(() => ({
    wizardNetwork: WizardNetworkNode,
    wizardVm: WizardVMNode,
  }), []);

  return (
    <div className="max-w-5xl mx-auto">
      <h2 className="text-2xl font-bold text-gray-900 mb-2">Review & Deploy</h2>
      <p className="text-gray-600 mb-6">
        Review your configuration before creating the range.
      </p>

      {/* Topology preview */}
      <div className="h-[300px] border border-gray-200 rounded-lg overflow-hidden mb-6">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          panOnDrag={false}
          zoomOnScroll={false}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
        >
          <Controls showInteractive={false} />
          <Background variant={BackgroundVariant.Dots} gap={20} size={1} />
        </ReactFlow>
      </div>

      {/* Configuration summary */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        {/* Environment summary */}
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="text-sm font-medium text-gray-500 mb-1">Environment</div>
          <div className="text-lg font-semibold text-gray-900 capitalize">{environment.type}</div>
          <div className="text-sm text-gray-500">{services.selected.length} services selected</div>
        </div>

        {/* Resource summary */}
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="text-sm font-medium text-gray-500 mb-1">Resources</div>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div>
              <div className="text-lg font-semibold text-gray-900">{totalNetworks}</div>
              <div className="text-xs text-gray-500">Networks</div>
            </div>
            <div>
              <div className="text-lg font-semibold text-gray-900">{totalVms}</div>
              <div className="text-xs text-gray-500">VMs</div>
            </div>
            <div>
              <div className="text-lg font-semibold text-gray-900">{totalUsers}</div>
              <div className="text-xs text-gray-500">Users</div>
            </div>
          </div>
        </div>
      </div>

      {/* Collapsible details */}
      <div className="space-y-3 mb-6">
        <CollapsibleSection title="Networks" icon={Network} count={totalNetworks}>
          <table className="w-full text-sm">
            <thead className="text-left text-gray-500">
              <tr>
                <th className="pb-2">Name</th>
                <th className="pb-2">Subnet</th>
                <th className="pb-2">Gateway</th>
                <th className="pb-2">Options</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {networks.segments.map((net) => (
                <tr key={net.id}>
                  <td className="py-2 font-medium text-gray-900">{net.name}</td>
                  <td className="py-2 text-gray-600">{net.subnet}</td>
                  <td className="py-2 text-gray-600">{net.gateway}</td>
                  <td className="py-2">
                    {net.dhcp && <span className="px-1.5 py-0.5 text-xs bg-blue-100 text-blue-700 rounded mr-1">DHCP</span>}
                    {net.isolated && <span className="px-1.5 py-0.5 text-xs bg-orange-100 text-orange-700 rounded">Isolated</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CollapsibleSection>

        <CollapsibleSection title="Virtual Machines" icon={Server} count={totalVms}>
          <table className="w-full text-sm">
            <thead className="text-left text-gray-500">
              <tr>
                <th className="pb-2">Hostname</th>
                <th className="pb-2">Template</th>
                <th className="pb-2">Network</th>
                <th className="pb-2">IP</th>
                <th className="pb-2">Resources</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {networks.vms.map((vm) => {
                const network = networks.segments.find(n => n.id === vm.networkId);
                return (
                  <tr key={vm.id}>
                    <td className="py-2 font-medium text-gray-900">{vm.hostname}</td>
                    <td className="py-2 text-gray-600">{vm.templateName}</td>
                    <td className="py-2 text-gray-600">{network?.name || '-'}</td>
                    <td className="py-2 text-gray-600 font-mono text-xs">{vm.ip}</td>
                    <td className="py-2 text-gray-500 text-xs">{vm.cpu} CPU, {vm.ramMb}MB, {vm.diskGb}GB</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </CollapsibleSection>

        <CollapsibleSection title="Users" icon={Users} count={totalUsers}>
          {totalUsers === 0 ? (
            <p className="text-gray-500 text-sm">No users configured</p>
          ) : (
            <div className="grid grid-cols-4 gap-4">
              {users.groups.filter(g => g.count > 0).map((group) => (
                <div key={group.id} className="text-center p-3 bg-gray-50 rounded-lg">
                  <div className="text-2xl font-bold text-gray-900">{group.count}</div>
                  <div className="text-sm text-gray-600">{group.name}</div>
                </div>
              ))}
            </div>
          )}
        </CollapsibleSection>

        <CollapsibleSection title="Vulnerabilities" icon={ShieldAlert} count={vulnPreset.vulnIds.length}>
          <div className="flex items-center gap-4">
            <div>
              <span className="font-medium text-gray-900">{vulnPreset.name}</span>
              <p className="text-sm text-gray-500">{vulnPreset.description}</p>
            </div>
          </div>
          {vulnerabilities.narrative && (
            <div className="mt-3 p-3 bg-gray-50 rounded-lg">
              <div className="text-xs font-medium text-gray-500 mb-1">Attack Narrative</div>
              <p className="text-sm text-gray-700">{vulnerabilities.narrative}</p>
            </div>
          )}
        </CollapsibleSection>
      </div>

      {/* Range name and options */}
      <div className="bg-primary-50 rounded-lg p-4 border border-primary-200">
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-2">Range Name</label>
          <input
            type="text"
            value={rangeName}
            onChange={(e) => setRangeName(e.target.value)}
            placeholder="Enter a name for your range..."
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-primary-500 focus:border-primary-500"
          />
        </div>

        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={saveAsBlueprint}
            onChange={(e) => setSaveAsBlueprint(e.target.checked)}
            className="w-5 h-5 rounded border-gray-300 text-primary-600"
          />
          <div>
            <span className="font-medium text-gray-900">Save as Blueprint</span>
            <p className="text-sm text-gray-500">Create a reusable template from this configuration</p>
          </div>
        </label>
      </div>
    </div>
  );
}
```

**Step 2: Verify component compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 3: Commit**

```bash
git add frontend/src/components/wizard-v2/steps/ReviewStep.tsx
git commit -m "feat(wizard): add ReviewStep with topology preview and configuration summary"
```

---

## Task 9: Create Main RangeWizardPage and Route

**Files:**
- Create: `frontend/src/pages/RangeWizardPage.tsx`
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/components/wizard-v2/steps/index.ts`

**Step 1: Create steps index export**

```typescript
// frontend/src/components/wizard-v2/steps/index.ts
export { EnvironmentStep } from './EnvironmentStep';
export { ServicesStep } from './ServicesStep';
export { NetworkStep } from './NetworkStep';
export { UsersStep } from './UsersStep';
export { VulnsStep } from './VulnsStep';
export { ReviewStep } from './ReviewStep';
```

**Step 2: Create RangeWizardPage**

```typescript
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
  const { currentStep, networks, rangeName, saveAsBlueprint, reset } = useWizardStore();
  const [isDeploying, setIsDeploying] = useState(false);
  const [templates, setTemplates] = useState<VMTemplate[]>([]);

  // Load templates on mount
  useEffect(() => {
    templatesApi.list().then(res => setTemplates(res.data));
  }, []);

  // Reset wizard state on unmount
  useEffect(() => {
    return () => {
      // Don't reset if navigating to a range detail page (deployment successful)
    };
  }, []);

  const handleDeploy = async () => {
    setIsDeploying(true);

    try {
      // Create template lookup
      const templateMap: Record<string, VMTemplate> = {};
      templates.forEach(t => {
        templateMap[t.name] = t;
      });

      // 1. Create range
      const rangeRes = await rangesApi.create({
        name: rangeName,
        description: `Created via Range Wizard - ${new Date().toLocaleDateString()}`,
      });
      const rangeId = rangeRes.data.id;

      // 2. Create networks
      const networkIdMap: Record<string, string> = {};
      for (const segment of networks.segments) {
        const netRes = await networksApi.create({
          range_id: rangeId,
          name: segment.name,
          subnet: segment.subnet,
          gateway: segment.gateway,
          is_isolated: segment.isolated,
          dhcp_enabled: segment.dhcp,
        });
        networkIdMap[segment.id] = netRes.data.id;
      }

      // 3. Create VMs
      for (const vm of networks.vms) {
        const template = templateMap[vm.templateName];
        if (!template) {
          toast.warning(`Template "${vm.templateName}" not found, skipping ${vm.hostname}`);
          continue;
        }

        const networkId = networkIdMap[vm.networkId];
        if (!networkId) {
          toast.warning(`Network not found for ${vm.hostname}`);
          continue;
        }

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
        });
      }

      // 4. Optionally save as blueprint
      if (saveAsBlueprint) {
        try {
          await blueprintsApi.create({
            range_id: rangeId,
            name: `${rangeName} Blueprint`,
            description: `Blueprint created from ${rangeName}`,
            base_subnet_prefix: '10',
          });
          toast.success('Blueprint created successfully');
        } catch (err) {
          toast.warning('Range created but blueprint creation failed');
        }
      }

      // 5. Deploy the range
      await rangesApi.deploy(rangeId);

      toast.success('Range created and deployment started!');
      reset();
      navigate(`/ranges/${rangeId}`);
    } catch (error: any) {
      console.error('Deployment error:', error);
      toast.error(error.response?.data?.detail || 'Failed to create range');
      setIsDeploying(false);
    }
  };

  const CurrentStep = STEPS[currentStep];

  return (
    <WizardLayout onDeploy={handleDeploy} isDeploying={isDeploying}>
      <CurrentStep />
    </WizardLayout>
  );
}
```

**Step 3: Update App.tsx to add the route**

In `frontend/src/App.tsx`, add the import and route:

```typescript
// Add import at top
import RangeWizardPage from './pages/RangeWizardPage'

// Add route inside the Layout routes, after "/ranges/:id"
<Route path="/ranges/new" element={<RangeWizardPage />} />
```

**Step 4: Verify everything compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 5: Commit**

```bash
git add frontend/src/pages/RangeWizardPage.tsx frontend/src/components/wizard-v2/steps/index.ts frontend/src/App.tsx
git commit -m "feat(wizard): add RangeWizardPage and route at /ranges/new"
```

---

## Task 10: Add Navigation to Wizard from Ranges Page

**Files:**
- Modify: `frontend/src/pages/Ranges.tsx`

**Step 1: Update Ranges.tsx to add wizard button**

Find the button that opens the current modal wizard and add/modify to link to `/ranges/new`:

```typescript
// In the header actions section, add/update button:
<Link
  to="/ranges/new"
  className="inline-flex items-center px-4 py-2 bg-primary-600 text-white text-sm font-medium rounded-lg hover:bg-primary-700"
>
  <Plus className="w-4 h-4 mr-2" />
  New Range
</Link>
```

**Step 2: Add Link import if not present**

```typescript
import { Link } from 'react-router-dom';
```

**Step 3: Test the navigation**

Run: `cd frontend && npm run dev`
Navigate to `/ranges` and click "New Range" - should go to `/ranges/new`

**Step 4: Commit**

```bash
git add frontend/src/pages/Ranges.tsx
git commit -m "feat(wizard): add navigation to Range Wizard from Ranges page"
```

---

## Task 11: Final Integration Testing

**Step 1: Build and type-check**

Run: `cd frontend && npm run build`
Expected: Build successful

**Step 2: Manual testing checklist**

- [ ] Navigate to `/ranges/new`
- [ ] Step 1: Select environment type
- [ ] Step 2: Toggle services, see VM preview
- [ ] Step 3: View network topology, add/edit networks and VMs
- [ ] Step 4: Configure user groups
- [ ] Step 5: Select vulnerability preset
- [ ] Step 6: Review configuration, enter name
- [ ] Deploy creates range and redirects

**Step 3: Fix any issues found**

Address any bugs or UI issues discovered during testing.

**Step 4: Final commit**

```bash
git add .
git commit -m "feat(wizard): complete Range Wizard v2 implementation

- Full-page wizard at /ranges/new with 6 steps
- Zustand state management for wizard state
- React Flow network topology editor
- Environment presets with auto-generated defaults
- Service selection with VM auto-generation
- User group configuration with access rules
- Vulnerability presets with per-VM customization
- Review step with topology preview
- Blueprint save option on deploy

Closes #34"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Zustand store | `stores/wizardStore.ts` |
| 2 | Layout components | `wizard-v2/WizardLayout.tsx`, `WizardSidebar.tsx` |
| 3 | Environment step | `steps/EnvironmentStep.tsx` |
| 4 | Services step | `steps/ServicesStep.tsx`, `data/servicePresets.ts` |
| 5 | Network step | `steps/NetworkStep.tsx`, `nodes/*`, `panels/*` |
| 6 | Users step | `steps/UsersStep.tsx` |
| 7 | Vulnerabilities step | `steps/VulnsStep.tsx`, `data/vulnPresets.ts` |
| 8 | Review step | `steps/ReviewStep.tsx` |
| 9 | Main page & route | `pages/RangeWizardPage.tsx`, `App.tsx` |
| 10 | Navigation | `pages/Ranges.tsx` |
| 11 | Integration testing | - |

**Total estimated tasks:** 11 tasks
**New files:** ~15 files
**Modified files:** 2 files (App.tsx, Ranges.tsx)
