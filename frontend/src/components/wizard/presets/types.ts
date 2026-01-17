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
