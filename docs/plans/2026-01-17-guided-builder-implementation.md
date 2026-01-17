# Guided Range Builder Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a wizard-style Guided Builder that creates complete cyber training environments from scenario presets.

**Architecture:** Frontend-only implementation using existing CYROID APIs. A 5-step modal wizard collects configuration, then sequentially creates range, networks, and VMs via API calls.

**Tech Stack:** React, TypeScript, Tailwind CSS, existing CYROID API client

---

## Task 1: Create Wizard Types and Preset Interfaces

**Files:**
- Create: `frontend/src/components/wizard/presets/types.ts`

**Step 1: Create the types file**

```typescript
// frontend/src/components/wizard/presets/types.ts

export interface ScenarioPreset {
  id: string;
  name: string;
  description: string;
  icon: 'Building' | 'Shield' | 'Search' | 'Target';
  zones: PresetZone[];
  defaultConfig: Partial<ConfigState>;
}

export interface PresetZone {
  id: string;
  name: string;
  subnet: string;
  gateway: string;
  isIsolated: boolean;
  systems: PresetSystem[];
}

export interface PresetSystem {
  id: string;
  name: string;
  ipOffset: number;
  templateName: string;
  osType: 'windows' | 'linux';
  role?: string;
  cpu?: number;
  ramMb?: number;
  diskGb?: number;
}

export interface ZoneState extends PresetZone {
  enabled: boolean;
  systems: SystemState[];
}

export interface SystemState extends PresetSystem {
  enabled: boolean;
  ip: string;
}

export interface ConfigState {
  domainName: string;
  adminPassword: string;
  userCount: number;
  vulnerabilityLevel: 'none' | 'some' | 'many';
}

export interface WizardState {
  currentStep: number;
  scenario: ScenarioPreset | null;
  zones: ZoneState[];
  config: ConfigState;
  rangeName: string;
  rangeDescription: string;
}

export const DEFAULT_CONFIG: ConfigState = {
  domainName: 'lab.local',
  adminPassword: '',
  userCount: 10,
  vulnerabilityLevel: 'none',
};
```

**Step 2: Verify file was created**

Run: `ls frontend/src/components/wizard/presets/`
Expected: types.ts

**Step 3: Commit**

```bash
git add frontend/src/components/wizard/presets/types.ts
git commit -m "feat(wizard): add TypeScript interfaces for guided builder"
```

---

## Task 2: Create Scenario Presets

**Files:**
- Create: `frontend/src/components/wizard/presets/adEnterpriseLab.ts`
- Create: `frontend/src/components/wizard/presets/segmentedNetwork.ts`
- Create: `frontend/src/components/wizard/presets/incidentResponse.ts`
- Create: `frontend/src/components/wizard/presets/pentestTarget.ts`
- Create: `frontend/src/components/wizard/presets/index.ts`

**Step 1: Create AD Enterprise Lab preset**

```typescript
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
```

**Step 2: Create Segmented Network preset**

```typescript
// frontend/src/components/wizard/presets/segmentedNetwork.ts
import { ScenarioPreset } from './types';

export const segmentedNetwork: ScenarioPreset = {
  id: 'segmented-network',
  name: 'Segmented Network (DMZ)',
  description: 'Multi-zone architecture with external, DMZ, and internal networks',
  icon: 'Shield',
  zones: [
    {
      id: 'external',
      name: 'External Network',
      subnet: '10.200.0.0/24',
      gateway: '10.200.0.1',
      isIsolated: true,
      systems: [
        {
          id: 'kali',
          name: 'Kali Linux',
          ipOffset: 100,
          templateName: 'Kali Linux',
          osType: 'linux',
          role: 'attacker',
          cpu: 2,
          ramMb: 4096,
          diskGb: 40,
        },
      ],
    },
    {
      id: 'dmz',
      name: 'DMZ',
      subnet: '10.201.0.0/24',
      gateway: '10.201.0.1',
      isIsolated: true,
      systems: [
        {
          id: 'web',
          name: 'Web Server',
          ipOffset: 10,
          templateName: 'Ubuntu 22.04',
          osType: 'linux',
          role: 'web-server',
          cpu: 2,
          ramMb: 2048,
          diskGb: 20,
        },
        {
          id: 'mail',
          name: 'Mail Server',
          ipOffset: 20,
          templateName: 'Ubuntu 22.04',
          osType: 'linux',
          role: 'mail-server',
          cpu: 2,
          ramMb: 2048,
          diskGb: 20,
        },
      ],
    },
    {
      id: 'internal',
      name: 'Internal Network',
      subnet: '10.202.0.0/24',
      gateway: '10.202.0.1',
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
          id: 'ws1',
          name: 'Workstation',
          ipOffset: 50,
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
    domainName: 'internal.local',
    userCount: 10,
    vulnerabilityLevel: 'some',
  },
};
```

**Step 3: Create Incident Response preset**

```typescript
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
```

**Step 4: Create Pentest Target preset**

```typescript
// frontend/src/components/wizard/presets/pentestTarget.ts
import { ScenarioPreset } from './types';

export const pentestTarget: ScenarioPreset = {
  id: 'pentest-target',
  name: 'Penetration Testing Target',
  description: 'Kali attacker with vulnerable targets for red team practice',
  icon: 'Target',
  zones: [
    {
      id: 'lab',
      name: 'Lab Network',
      subnet: '10.50.0.0/24',
      gateway: '10.50.0.1',
      isIsolated: true,
      systems: [
        {
          id: 'kali',
          name: 'Kali Linux',
          ipOffset: 100,
          templateName: 'Kali Linux',
          osType: 'linux',
          role: 'attacker',
          cpu: 2,
          ramMb: 4096,
          diskGb: 40,
        },
        {
          id: 'vuln-linux',
          name: 'Vulnerable Linux',
          ipOffset: 10,
          templateName: 'Ubuntu 22.04',
          osType: 'linux',
          role: 'target',
          cpu: 1,
          ramMb: 1024,
          diskGb: 20,
        },
        {
          id: 'vuln-web',
          name: 'DVWA Server',
          ipOffset: 20,
          templateName: 'Ubuntu 22.04',
          osType: 'linux',
          role: 'web-target',
          cpu: 1,
          ramMb: 1024,
          diskGb: 20,
        },
        {
          id: 'vuln-windows',
          name: 'Windows Target',
          ipOffset: 30,
          templateName: 'Windows 10',
          osType: 'windows',
          role: 'windows-target',
          cpu: 2,
          ramMb: 4096,
          diskGb: 40,
        },
      ],
    },
  ],
  defaultConfig: {
    vulnerabilityLevel: 'many',
  },
};
```

**Step 5: Create index file**

```typescript
// frontend/src/components/wizard/presets/index.ts
export * from './types';
export { adEnterpriseLab } from './adEnterpriseLab';
export { segmentedNetwork } from './segmentedNetwork';
export { incidentResponse } from './incidentResponse';
export { pentestTarget } from './pentestTarget';

import { ScenarioPreset } from './types';
import { adEnterpriseLab } from './adEnterpriseLab';
import { segmentedNetwork } from './segmentedNetwork';
import { incidentResponse } from './incidentResponse';
import { pentestTarget } from './pentestTarget';

export const ALL_PRESETS: ScenarioPreset[] = [
  adEnterpriseLab,
  segmentedNetwork,
  incidentResponse,
  pentestTarget,
];
```

**Step 6: Commit**

```bash
git add frontend/src/components/wizard/presets/
git commit -m "feat(wizard): add 4 scenario presets for guided builder"
```

---

## Task 3: Create Wizard Context for State Management

**Files:**
- Create: `frontend/src/components/wizard/WizardContext.tsx`

**Step 1: Create the context provider**

```typescript
// frontend/src/components/wizard/WizardContext.tsx
import React, { createContext, useContext, useReducer, ReactNode } from 'react';
import {
  WizardState,
  ScenarioPreset,
  ZoneState,
  SystemState,
  ConfigState,
  DEFAULT_CONFIG,
} from './presets/types';

type WizardAction =
  | { type: 'SET_STEP'; step: number }
  | { type: 'SELECT_SCENARIO'; scenario: ScenarioPreset }
  | { type: 'TOGGLE_ZONE'; zoneId: string }
  | { type: 'TOGGLE_SYSTEM'; zoneId: string; systemId: string }
  | { type: 'UPDATE_CONFIG'; config: Partial<ConfigState> }
  | { type: 'SET_RANGE_NAME'; name: string }
  | { type: 'SET_RANGE_DESCRIPTION'; description: string }
  | { type: 'RESET' };

const initialState: WizardState = {
  currentStep: 0,
  scenario: null,
  zones: [],
  config: DEFAULT_CONFIG,
  rangeName: '',
  rangeDescription: '',
};

function generatePassword(length: number = 16): string {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789!@#$%';
  return Array.from({ length }, () => chars[Math.floor(Math.random() * chars.length)]).join('');
}

function computeIp(subnet: string, offset: number): string {
  const base = subnet.split('/')[0].split('.').slice(0, 3).join('.');
  return `${base}.${offset}`;
}

function initializeZonesFromPreset(preset: ScenarioPreset): ZoneState[] {
  return preset.zones.map((zone) => ({
    ...zone,
    enabled: true,
    systems: zone.systems.map((sys) => ({
      ...sys,
      enabled: true,
      ip: computeIp(zone.subnet, sys.ipOffset),
    })),
  }));
}

function wizardReducer(state: WizardState, action: WizardAction): WizardState {
  switch (action.type) {
    case 'SET_STEP':
      return { ...state, currentStep: action.step };

    case 'SELECT_SCENARIO':
      return {
        ...state,
        scenario: action.scenario,
        zones: initializeZonesFromPreset(action.scenario),
        config: {
          ...DEFAULT_CONFIG,
          ...action.scenario.defaultConfig,
          adminPassword: generatePassword(),
        },
        rangeName: action.scenario.name,
        rangeDescription: action.scenario.description,
        currentStep: 1,
      };

    case 'TOGGLE_ZONE':
      return {
        ...state,
        zones: state.zones.map((z) =>
          z.id === action.zoneId ? { ...z, enabled: !z.enabled } : z
        ),
      };

    case 'TOGGLE_SYSTEM':
      return {
        ...state,
        zones: state.zones.map((z) =>
          z.id === action.zoneId
            ? {
                ...z,
                systems: z.systems.map((s) =>
                  s.id === action.systemId ? { ...s, enabled: !s.enabled } : s
                ),
              }
            : z
        ),
      };

    case 'UPDATE_CONFIG':
      return {
        ...state,
        config: { ...state.config, ...action.config },
      };

    case 'SET_RANGE_NAME':
      return { ...state, rangeName: action.name };

    case 'SET_RANGE_DESCRIPTION':
      return { ...state, rangeDescription: action.description };

    case 'RESET':
      return initialState;

    default:
      return state;
  }
}

interface WizardContextValue {
  state: WizardState;
  dispatch: React.Dispatch<WizardAction>;
  nextStep: () => void;
  prevStep: () => void;
  canProceed: () => boolean;
}

const WizardContext = createContext<WizardContextValue | null>(null);

export function WizardProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(wizardReducer, initialState);

  const nextStep = () => {
    if (state.currentStep < 4) {
      dispatch({ type: 'SET_STEP', step: state.currentStep + 1 });
    }
  };

  const prevStep = () => {
    if (state.currentStep > 0) {
      dispatch({ type: 'SET_STEP', step: state.currentStep - 1 });
    }
  };

  const canProceed = (): boolean => {
    switch (state.currentStep) {
      case 0:
        return state.scenario !== null;
      case 1:
        return state.zones.some((z) => z.enabled);
      case 2:
        return state.zones.some((z) => z.enabled && z.systems.some((s) => s.enabled));
      case 3:
        return state.rangeName.trim().length > 0;
      case 4:
        return true;
      default:
        return false;
    }
  };

  return (
    <WizardContext.Provider value={{ state, dispatch, nextStep, prevStep, canProceed }}>
      {children}
    </WizardContext.Provider>
  );
}

export function useWizard() {
  const context = useContext(WizardContext);
  if (!context) {
    throw new Error('useWizard must be used within a WizardProvider');
  }
  return context;
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/wizard/WizardContext.tsx
git commit -m "feat(wizard): add state management context with reducer"
```

---

## Task 4: Create Step 0 - Scenario Selection

**Files:**
- Create: `frontend/src/components/wizard/steps/ScenarioSelection.tsx`

**Step 1: Create the component**

```typescript
// frontend/src/components/wizard/steps/ScenarioSelection.tsx
import { Building, Shield, Search, Target } from 'lucide-react';
import clsx from 'clsx';
import { useWizard } from '../WizardContext';
import { ALL_PRESETS, ScenarioPreset } from '../presets';

const iconMap = {
  Building,
  Shield,
  Search,
  Target,
};

export function ScenarioSelection() {
  const { state, dispatch } = useWizard();

  const handleSelect = (preset: ScenarioPreset) => {
    dispatch({ type: 'SELECT_SCENARIO', scenario: preset });
  };

  return (
    <div className="space-y-6">
      <div className="text-center">
        <h2 className="text-xl font-semibold text-gray-900">Choose a Scenario</h2>
        <p className="mt-1 text-sm text-gray-500">
          Select a starting point for your cyber range environment
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {ALL_PRESETS.map((preset) => {
          const Icon = iconMap[preset.icon];
          const vmCount = preset.zones.reduce((acc, z) => acc + z.systems.length, 0);
          const networkCount = preset.zones.length;
          const isSelected = state.scenario?.id === preset.id;

          return (
            <button
              key={preset.id}
              onClick={() => handleSelect(preset)}
              className={clsx(
                'relative p-6 text-left rounded-lg border-2 transition-all',
                isSelected
                  ? 'border-primary-500 bg-primary-50 ring-2 ring-primary-500'
                  : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
              )}
            >
              <div className="flex items-start space-x-4">
                <div
                  className={clsx(
                    'flex-shrink-0 p-3 rounded-lg',
                    isSelected ? 'bg-primary-100 text-primary-600' : 'bg-gray-100 text-gray-600'
                  )}
                >
                  <Icon className="h-6 w-6" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="text-lg font-medium text-gray-900">{preset.name}</h3>
                  <p className="mt-1 text-sm text-gray-500">{preset.description}</p>
                  <div className="mt-3 flex items-center space-x-4 text-xs text-gray-400">
                    <span>{vmCount} VMs</span>
                    <span>{networkCount} {networkCount === 1 ? 'network' : 'networks'}</span>
                  </div>
                </div>
              </div>
              {isSelected && (
                <div className="absolute top-3 right-3">
                  <div className="h-6 w-6 rounded-full bg-primary-500 flex items-center justify-center">
                    <svg className="h-4 w-4 text-white" fill="currentColor" viewBox="0 0 20 20">
                      <path
                        fillRule="evenodd"
                        d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                        clipRule="evenodd"
                      />
                    </svg>
                  </div>
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/wizard/steps/ScenarioSelection.tsx
git commit -m "feat(wizard): add scenario selection step"
```

---

## Task 5: Create Step 1 - Zone Configuration

**Files:**
- Create: `frontend/src/components/wizard/steps/ZoneConfiguration.tsx`

**Step 1: Create the component**

```typescript
// frontend/src/components/wizard/steps/ZoneConfiguration.tsx
import { Network, Server } from 'lucide-react';
import clsx from 'clsx';
import { useWizard } from '../WizardContext';

export function ZoneConfiguration() {
  const { state, dispatch } = useWizard();

  const handleToggleZone = (zoneId: string) => {
    dispatch({ type: 'TOGGLE_ZONE', zoneId });
  };

  return (
    <div className="space-y-6">
      <div className="text-center">
        <h2 className="text-xl font-semibold text-gray-900">Configure Network Zones</h2>
        <p className="mt-1 text-sm text-gray-500">
          Enable or disable network zones for your environment
        </p>
      </div>

      <div className="space-y-4">
        {state.zones.map((zone) => {
          const enabledSystems = zone.systems.filter((s) => s.enabled).length;

          return (
            <div
              key={zone.id}
              className={clsx(
                'rounded-lg border-2 p-4 transition-all',
                zone.enabled
                  ? 'border-primary-200 bg-white'
                  : 'border-gray-200 bg-gray-50 opacity-60'
              )}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={zone.enabled}
                      onChange={() => handleToggleZone(zone.id)}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"></div>
                  </label>
                  <div className="flex items-center space-x-2">
                    <Network className="h-5 w-5 text-gray-400" />
                    <span className="font-medium text-gray-900">{zone.name}</span>
                  </div>
                </div>
                <div className="text-sm text-gray-500">
                  {zone.subnet}
                </div>
              </div>

              {zone.enabled && (
                <div className="mt-4 pl-14">
                  <div className="flex items-center space-x-2 text-sm text-gray-600">
                    <Server className="h-4 w-4" />
                    <span>
                      {enabledSystems} {enabledSystems === 1 ? 'system' : 'systems'}
                    </span>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {zone.systems.map((sys) => (
                      <span
                        key={sys.id}
                        className={clsx(
                          'px-2 py-1 text-xs rounded-full',
                          sys.enabled
                            ? 'bg-primary-100 text-primary-700'
                            : 'bg-gray-100 text-gray-500'
                        )}
                      >
                        {sys.name}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {!state.zones.some((z) => z.enabled) && (
        <div className="text-center p-4 bg-yellow-50 rounded-lg">
          <p className="text-sm text-yellow-700">
            Please enable at least one network zone to continue.
          </p>
        </div>
      )}
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/wizard/steps/ZoneConfiguration.tsx
git commit -m "feat(wizard): add zone configuration step"
```

---

## Task 6: Create Step 2 - System Selection

**Files:**
- Create: `frontend/src/components/wizard/steps/SystemSelection.tsx`

**Step 1: Create the component**

```typescript
// frontend/src/components/wizard/steps/SystemSelection.tsx
import { Monitor, Server } from 'lucide-react';
import clsx from 'clsx';
import { useWizard } from '../WizardContext';

export function SystemSelection() {
  const { state, dispatch } = useWizard();

  const handleToggleSystem = (zoneId: string, systemId: string) => {
    dispatch({ type: 'TOGGLE_SYSTEM', zoneId, systemId });
  };

  const enabledZones = state.zones.filter((z) => z.enabled);

  return (
    <div className="space-y-6">
      <div className="text-center">
        <h2 className="text-xl font-semibold text-gray-900">Select Systems</h2>
        <p className="mt-1 text-sm text-gray-500">
          Choose which systems to include in each network zone
        </p>
      </div>

      <div className="space-y-6">
        {enabledZones.map((zone) => (
          <div key={zone.id} className="rounded-lg border border-gray-200 overflow-hidden">
            <div className="bg-gray-50 px-4 py-3 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Server className="h-5 w-5 text-gray-400" />
                  <span className="font-medium text-gray-900">{zone.name}</span>
                </div>
                <span className="text-sm text-gray-500">{zone.subnet}</span>
              </div>
            </div>

            <div className="p-4 space-y-3">
              {zone.systems.map((system) => (
                <label
                  key={system.id}
                  className={clsx(
                    'flex items-center justify-between p-3 rounded-lg border cursor-pointer transition-all',
                    system.enabled
                      ? 'border-primary-200 bg-primary-50'
                      : 'border-gray-200 bg-white hover:bg-gray-50'
                  )}
                >
                  <div className="flex items-center space-x-3">
                    <input
                      type="checkbox"
                      checked={system.enabled}
                      onChange={() => handleToggleSystem(zone.id, system.id)}
                      className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                    />
                    <div className="flex items-center space-x-2">
                      <Monitor
                        className={clsx(
                          'h-5 w-5',
                          system.osType === 'windows' ? 'text-blue-500' : 'text-orange-500'
                        )}
                      />
                      <div>
                        <span className="font-medium text-gray-900">{system.name}</span>
                        <span className="ml-2 text-sm text-gray-500">({system.templateName})</span>
                      </div>
                    </div>
                  </div>
                  <div className="text-sm text-gray-500 font-mono">{system.ip}</div>
                </label>
              ))}
            </div>
          </div>
        ))}
      </div>

      {enabledZones.every((z) => !z.systems.some((s) => s.enabled)) && (
        <div className="text-center p-4 bg-yellow-50 rounded-lg">
          <p className="text-sm text-yellow-700">
            Please select at least one system to continue.
          </p>
        </div>
      )}
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/wizard/steps/SystemSelection.tsx
git commit -m "feat(wizard): add system selection step"
```

---

## Task 7: Create Step 3 - Configuration Options

**Files:**
- Create: `frontend/src/components/wizard/steps/ConfigurationOptions.tsx`

**Step 1: Create the component**

```typescript
// frontend/src/components/wizard/steps/ConfigurationOptions.tsx
import { useState } from 'react';
import { Eye, EyeOff, RefreshCw } from 'lucide-react';
import { useWizard } from '../WizardContext';

function generatePassword(length: number = 16): string {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789!@#$%';
  return Array.from({ length }, () => chars[Math.floor(Math.random() * chars.length)]).join('');
}

export function ConfigurationOptions() {
  const { state, dispatch } = useWizard();
  const [showPassword, setShowPassword] = useState(false);

  const hasWindowsDC = state.zones.some(
    (z) => z.enabled && z.systems.some((s) => s.enabled && s.role === 'domain-controller')
  );

  const handleConfigChange = (key: string, value: string | number) => {
    dispatch({ type: 'UPDATE_CONFIG', config: { [key]: value } });
  };

  const regeneratePassword = () => {
    dispatch({ type: 'UPDATE_CONFIG', config: { adminPassword: generatePassword() } });
  };

  return (
    <div className="space-y-6">
      <div className="text-center">
        <h2 className="text-xl font-semibold text-gray-900">Configuration</h2>
        <p className="mt-1 text-sm text-gray-500">
          Set up your range name and environment options
        </p>
      </div>

      <div className="space-y-6">
        {/* Range Name */}
        <div>
          <label className="block text-sm font-medium text-gray-700">Range Name</label>
          <input
            type="text"
            value={state.rangeName}
            onChange={(e) => dispatch({ type: 'SET_RANGE_NAME', name: e.target.value })}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
            placeholder="My Cyber Range"
          />
        </div>

        {/* Range Description */}
        <div>
          <label className="block text-sm font-medium text-gray-700">Description</label>
          <textarea
            value={state.rangeDescription}
            onChange={(e) => dispatch({ type: 'SET_RANGE_DESCRIPTION', description: e.target.value })}
            rows={2}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
            placeholder="Optional description..."
          />
        </div>

        {/* AD Configuration - only show if DC present */}
        {hasWindowsDC && (
          <div className="border-t pt-6">
            <h3 className="text-sm font-medium text-gray-900 mb-4">Active Directory Settings</h3>

            {/* Domain Name */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700">Domain Name</label>
              <input
                type="text"
                value={state.config.domainName}
                onChange={(e) => handleConfigChange('domainName', e.target.value)}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                placeholder="lab.local"
              />
            </div>

            {/* Admin Password */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700">Admin Password</label>
              <div className="mt-1 flex rounded-md shadow-sm">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={state.config.adminPassword}
                  onChange={(e) => handleConfigChange('adminPassword', e.target.value)}
                  className="flex-1 block w-full rounded-l-md border-gray-300 focus:border-primary-500 focus:ring-primary-500 sm:text-sm font-mono"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="inline-flex items-center px-3 border border-l-0 border-gray-300 bg-gray-50 text-gray-500 hover:bg-gray-100"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
                <button
                  type="button"
                  onClick={regeneratePassword}
                  className="inline-flex items-center px-3 rounded-r-md border border-l-0 border-gray-300 bg-gray-50 text-gray-500 hover:bg-gray-100"
                >
                  <RefreshCw className="h-4 w-4" />
                </button>
              </div>
            </div>

            {/* User Count */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700">Number of Domain Users</label>
              <select
                value={state.config.userCount}
                onChange={(e) => handleConfigChange('userCount', parseInt(e.target.value))}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
              >
                <option value={5}>5 users</option>
                <option value={10}>10 users</option>
                <option value={25}>25 users</option>
                <option value={50}>50 users</option>
              </select>
            </div>
          </div>
        )}

        {/* Vulnerability Level */}
        <div className={hasWindowsDC ? '' : 'border-t pt-6'}>
          <label className="block text-sm font-medium text-gray-700">Vulnerability Level</label>
          <p className="text-xs text-gray-500 mb-2">
            Controls the security posture of deployed systems
          </p>
          <div className="grid grid-cols-3 gap-3">
            {(['none', 'some', 'many'] as const).map((level) => (
              <button
                key={level}
                type="button"
                onClick={() => handleConfigChange('vulnerabilityLevel', level)}
                className={`px-4 py-3 rounded-lg border-2 text-sm font-medium transition-all ${
                  state.config.vulnerabilityLevel === level
                    ? 'border-primary-500 bg-primary-50 text-primary-700'
                    : 'border-gray-200 text-gray-700 hover:border-gray-300'
                }`}
              >
                {level === 'none' && 'Hardened'}
                {level === 'some' && 'Realistic'}
                {level === 'many' && 'Vulnerable'}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/wizard/steps/ConfigurationOptions.tsx
git commit -m "feat(wizard): add configuration options step"
```

---

## Task 8: Create Step 4 - Review and Deploy

**Files:**
- Create: `frontend/src/components/wizard/steps/ReviewAndDeploy.tsx`

**Step 1: Create the component**

```typescript
// frontend/src/components/wizard/steps/ReviewAndDeploy.tsx
import { Network, Server, Settings, Shield } from 'lucide-react';
import clsx from 'clsx';
import { useWizard } from '../WizardContext';

export function ReviewAndDeploy() {
  const { state } = useWizard();

  const enabledZones = state.zones.filter((z) => z.enabled);
  const totalSystems = enabledZones.reduce(
    (acc, z) => acc + z.systems.filter((s) => s.enabled).length,
    0
  );
  const totalCpu = enabledZones.reduce(
    (acc, z) => acc + z.systems.filter((s) => s.enabled).reduce((a, s) => a + (s.cpu || 2), 0),
    0
  );
  const totalRam = enabledZones.reduce(
    (acc, z) => acc + z.systems.filter((s) => s.enabled).reduce((a, s) => a + (s.ramMb || 2048), 0),
    0
  );
  const totalDisk = enabledZones.reduce(
    (acc, z) => acc + z.systems.filter((s) => s.enabled).reduce((a, s) => a + (s.diskGb || 20), 0),
    0
  );

  const hasWindowsDC = enabledZones.some(
    (z) => z.systems.some((s) => s.enabled && s.role === 'domain-controller')
  );

  return (
    <div className="space-y-6">
      <div className="text-center">
        <h2 className="text-xl font-semibold text-gray-900">Review & Deploy</h2>
        <p className="mt-1 text-sm text-gray-500">
          Confirm your configuration before deploying the range
        </p>
      </div>

      {/* Range Info */}
      <div className="bg-gray-50 rounded-lg p-4">
        <h3 className="font-medium text-gray-900 mb-2">{state.rangeName}</h3>
        {state.rangeDescription && (
          <p className="text-sm text-gray-600">{state.rangeDescription}</p>
        )}
      </div>

      {/* Resource Summary */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-blue-50 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-blue-700">{enabledZones.length}</div>
          <div className="text-xs text-blue-600">Networks</div>
        </div>
        <div className="bg-green-50 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-green-700">{totalSystems}</div>
          <div className="text-xs text-green-600">VMs</div>
        </div>
        <div className="bg-purple-50 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-purple-700">{totalCpu}</div>
          <div className="text-xs text-purple-600">CPU Cores</div>
        </div>
        <div className="bg-orange-50 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-orange-700">{Math.round(totalRam / 1024)}</div>
          <div className="text-xs text-orange-600">GB RAM</div>
        </div>
      </div>

      {/* Networks and Systems */}
      <div className="space-y-4">
        {enabledZones.map((zone) => (
          <div key={zone.id} className="border border-gray-200 rounded-lg overflow-hidden">
            <div className="bg-gray-50 px-4 py-2 border-b flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Network className="h-4 w-4 text-gray-400" />
                <span className="font-medium text-gray-900">{zone.name}</span>
              </div>
              <span className="text-sm font-mono text-gray-500">{zone.subnet}</span>
            </div>
            <div className="divide-y divide-gray-100">
              {zone.systems.filter((s) => s.enabled).map((system) => (
                <div key={system.id} className="px-4 py-2 flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Server
                      className={clsx(
                        'h-4 w-4',
                        system.osType === 'windows' ? 'text-blue-500' : 'text-orange-500'
                      )}
                    />
                    <span className="text-sm text-gray-900">{system.name}</span>
                    <span className="text-xs text-gray-400">({system.templateName})</span>
                  </div>
                  <span className="text-sm font-mono text-gray-500">{system.ip}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Configuration Summary */}
      {hasWindowsDC && (
        <div className="border border-gray-200 rounded-lg p-4">
          <div className="flex items-center space-x-2 mb-3">
            <Settings className="h-4 w-4 text-gray-400" />
            <span className="font-medium text-gray-900">Active Directory Configuration</span>
          </div>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-500">Domain:</span>
              <span className="ml-2 font-mono text-gray-900">{state.config.domainName}</span>
            </div>
            <div>
              <span className="text-gray-500">Users:</span>
              <span className="ml-2 text-gray-900">{state.config.userCount}</span>
            </div>
          </div>
        </div>
      )}

      {/* Security Level */}
      <div className="flex items-center justify-center space-x-2 py-2">
        <Shield
          className={clsx(
            'h-5 w-5',
            state.config.vulnerabilityLevel === 'none' && 'text-green-500',
            state.config.vulnerabilityLevel === 'some' && 'text-yellow-500',
            state.config.vulnerabilityLevel === 'many' && 'text-red-500'
          )}
        />
        <span className="text-sm text-gray-600">
          Security Level:{' '}
          <span className="font-medium">
            {state.config.vulnerabilityLevel === 'none' && 'Hardened'}
            {state.config.vulnerabilityLevel === 'some' && 'Realistic'}
            {state.config.vulnerabilityLevel === 'many' && 'Vulnerable'}
          </span>
        </span>
      </div>

      {/* Disk Space Notice */}
      <div className="bg-gray-50 rounded-lg p-3 text-center text-sm text-gray-600">
        Estimated disk usage: <span className="font-medium">{totalDisk} GB</span>
      </div>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/wizard/steps/ReviewAndDeploy.tsx
git commit -m "feat(wizard): add review and deploy step"
```

---

## Task 9: Create Steps Index

**Files:**
- Create: `frontend/src/components/wizard/steps/index.ts`

**Step 1: Create the index file**

```typescript
// frontend/src/components/wizard/steps/index.ts
export { ScenarioSelection } from './ScenarioSelection';
export { ZoneConfiguration } from './ZoneConfiguration';
export { SystemSelection } from './SystemSelection';
export { ConfigurationOptions } from './ConfigurationOptions';
export { ReviewAndDeploy } from './ReviewAndDeploy';
```

**Step 2: Commit**

```bash
git add frontend/src/components/wizard/steps/index.ts
git commit -m "feat(wizard): add steps index"
```

---

## Task 10: Create Main Wizard Modal

**Files:**
- Create: `frontend/src/components/wizard/GuidedBuilderWizard.tsx`
- Create: `frontend/src/components/wizard/index.ts`

**Step 1: Create the main wizard component**

```typescript
// frontend/src/components/wizard/GuidedBuilderWizard.tsx
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
  const { state, dispatch, nextStep, prevStep, canProceed } = useWizard();
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
            <h2 className="text-lg font-semibold text-gray-900">Guided Range Builder</h2>
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

export function GuidedBuilderWizard({ isOpen, onClose }: Props) {
  if (!isOpen) return null;

  return (
    <WizardProvider>
      <WizardContent onClose={onClose} />
    </WizardProvider>
  );
}
```

**Step 2: Create index file**

```typescript
// frontend/src/components/wizard/index.ts
export { GuidedBuilderWizard } from './GuidedBuilderWizard';
```

**Step 3: Commit**

```bash
git add frontend/src/components/wizard/GuidedBuilderWizard.tsx frontend/src/components/wizard/index.ts
git commit -m "feat(wizard): add main wizard modal component"
```

---

## Task 11: Add Wizard to Ranges Page

**Files:**
- Modify: `frontend/src/pages/Ranges.tsx`

**Step 1: Import the wizard**

Add to imports at top of file:
```typescript
import { GuidedBuilderWizard } from '../components/wizard';
import { Wand2 } from 'lucide-react';
```

**Step 2: Add wizard state**

After the `deleteConfirm` state, add:
```typescript
const [showGuidedBuilder, setShowGuidedBuilder] = useState(false);
```

**Step 3: Add Guided Builder button**

In the button group (around line 118-133), add before "New Range" button:
```typescript
<button
  onClick={() => setShowGuidedBuilder(true)}
  className="inline-flex items-center px-4 py-2 border border-primary-300 rounded-md shadow-sm text-sm font-medium text-primary-700 bg-primary-50 hover:bg-primary-100 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
>
  <Wand2 className="h-4 w-4 mr-2" />
  Guided Builder
</button>
```

**Step 4: Add wizard component**

After the ConfirmDialog at the end of the component (before final `</div>`), add:
```typescript
{/* Guided Builder Wizard */}
<GuidedBuilderWizard
  isOpen={showGuidedBuilder}
  onClose={() => {
    setShowGuidedBuilder(false);
    fetchRanges();
  }}
/>
```

**Step 5: Verify build**

Run: `cd frontend && npm run build`
Expected: Build completes without errors

**Step 6: Commit**

```bash
git add frontend/src/pages/Ranges.tsx
git commit -m "feat(wizard): integrate guided builder into ranges page"
```

---

## Task 12: Add Empty State CTA

**Files:**
- Modify: `frontend/src/pages/Ranges.tsx`

**Step 1: Update empty state**

Find the empty state section (around line 136-149) and replace it with:

```typescript
{ranges.length === 0 ? (
  <div className="mt-8 text-center py-12 bg-white rounded-lg shadow">
    <Network className="mx-auto h-12 w-12 text-gray-400" />
    <h3 className="mt-2 text-sm font-medium text-gray-900">No ranges</h3>
    <p className="mt-1 text-sm text-gray-500">Get started by creating a new cyber range.</p>
    <div className="mt-6 flex justify-center space-x-4">
      <button
        onClick={() => setShowGuidedBuilder(true)}
        className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700"
      >
        <Wand2 className="h-4 w-4 mr-2" />
        Guided Builder
      </button>
      <button
        onClick={() => setShowModal(true)}
        className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
      >
        <Plus className="h-4 w-4 mr-2" />
        Manual Setup
      </button>
    </div>
  </div>
) : (
```

**Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: Build completes without errors

**Step 3: Commit**

```bash
git add frontend/src/pages/Ranges.tsx
git commit -m "feat(wizard): add guided builder CTA to empty state"
```

---

## Task 13: Final Testing and Version Bump

**Files:**
- Modify: `backend/cyroid/config.py`
- Modify: `CHANGELOG.md`

**Step 1: Test the wizard manually**

1. Start the dev servers: `docker-compose up -d`
2. Navigate to Ranges page
3. Click "Guided Builder"
4. Test each scenario preset
5. Verify network and VM creation
6. Verify deployment starts

**Step 2: Update version to 0.5.0**

In `backend/cyroid/config.py`, change:
```python
app_version: str = "0.5.0"
```

**Step 3: Update CHANGELOG.md**

Add new entry at top:
```markdown
## [0.5.0] - 2026-01-17

### Added

- **Guided Range Builder** ([#19](../../issues/19)): New wizard-style interface for creating complete cyber training environments from scenario presets.
  - 4 scenario presets: AD Enterprise Lab, Segmented Network (DMZ), Incident Response Lab, Penetration Testing Target
  - 5-step wizard: Scenario → Zones → Systems → Configure → Deploy
  - Auto-assigned subnets and IP addresses
  - Active Directory configuration (domain name, admin password, user count)
  - Vulnerability level selection (hardened, realistic, vulnerable)
  - Sequential API calls create range, networks, and VMs
  - Auto-deploy after creation
```

**Step 4: Commit**

```bash
git add backend/cyroid/config.py CHANGELOG.md
git commit -m "chore: bump version to 0.5.0 for guided builder release"
```

**Step 5: Tag release**

```bash
git tag -a v0.5.0 -m "v0.5.0: Guided Range Builder

- 4 scenario presets for cyber defense training
- 5-step wizard for easy range creation
- Auto-configured networks and VMs
- AD configuration options"
```

**Step 6: Close issue**

```bash
gh issue close 19 --comment "Released in v0.5.0"
```

---

## Summary

**Total Tasks:** 13
**New Files:** 12
**Modified Files:** 3
**Estimated Lines:** ~1400

**Key Components:**
- `WizardContext.tsx` - State management
- `GuidedBuilderWizard.tsx` - Main modal
- 5 step components
- 4 scenario presets

**No Backend Changes Required**
