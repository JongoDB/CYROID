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
