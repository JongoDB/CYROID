// frontend/src/components/wizard/WizardContext.tsx
import React, { createContext, useContext, useReducer, ReactNode } from 'react';
import {
  WizardState,
  ScenarioPreset,
  ZoneState,
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
