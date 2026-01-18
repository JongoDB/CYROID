// frontend/src/components/wizard-v2/steps/VulnsStep.tsx
import { ShieldAlert, ShieldCheck, AlertTriangle, Bug, Key, Settings } from 'lucide-react';
import clsx from 'clsx';
import { useWizardStore, VulnPreset } from '../../../stores/wizardStore';
import { VULNERABILITY_CATALOG, VULN_PRESETS, VulnDefinition } from '../data/vulnPresets';

const CATEGORY_ICONS: Record<VulnDefinition['category'], React.ReactNode> = {
  network: <ShieldAlert className="h-4 w-4" />,
  web: <Bug className="h-4 w-4" />,
  credential: <Key className="h-4 w-4" />,
  misconfig: <Settings className="h-4 w-4" />,
};

const SEVERITY_COLORS: Record<VulnDefinition['severity'], string> = {
  low: 'bg-gray-100 text-gray-700',
  medium: 'bg-yellow-100 text-yellow-700',
  high: 'bg-orange-100 text-orange-700',
  critical: 'bg-red-100 text-red-700',
};

export function VulnsStep() {
  const { networks, vulnerabilities, setVulnPreset, toggleVmVuln, setNarrative } = useWizardStore();

  // Get VMs from network topology
  const vms = networks.vms;

  // Get applicable vulnerabilities for a given VM template
  const getApplicableVulns = (templateName: string): VulnDefinition[] => {
    return VULNERABILITY_CATALOG.filter((v) => v.applicableTemplates.includes(templateName));
  };

  // Get preset vuln count for display
  const getPresetVulnCount = (preset: VulnPreset): number => {
    if (preset === 'custom') return 0;
    return VULN_PRESETS[preset]?.vulnIds.length || 0;
  };

  // Check if a vuln is active for a VM based on preset or custom selection
  const isVulnActive = (vmId: string, vulnId: string): boolean => {
    if (vulnerabilities.preset === 'custom') {
      return vulnerabilities.perVm[vmId]?.includes(vulnId) || false;
    }
    return VULN_PRESETS[vulnerabilities.preset]?.vulnIds.includes(vulnId) || false;
  };

  // Count active vulns for a VM
  const getActiveVulnCount = (vmId: string, templateName: string): number => {
    const applicable = getApplicableVulns(templateName);
    return applicable.filter((v) => isVulnActive(vmId, v.id)).length;
  };

  return (
    <div className="max-w-5xl mx-auto">
      <h2 className="text-2xl font-bold text-gray-900 mb-2">Configure Vulnerabilities</h2>
      <p className="text-gray-600 mb-8">
        Select a vulnerability profile for your range. Choose from presets or customize per VM.
      </p>

      <div className="grid grid-cols-2 gap-8">
        {/* Preset Selection */}
        <div>
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Vulnerability Profile</h3>
          <div className="space-y-2">
            {(Object.keys(VULN_PRESETS) as VulnPreset[]).map((presetKey) => {
              const preset = VULN_PRESETS[presetKey];
              const isSelected = vulnerabilities.preset === presetKey;

              return (
                <button
                  key={presetKey}
                  onClick={() => setVulnPreset(presetKey)}
                  className={clsx(
                    'w-full text-left p-4 rounded-lg border transition-colors',
                    isSelected
                      ? 'border-primary-300 bg-primary-50 ring-2 ring-primary-200'
                      : 'border-gray-200 hover:bg-gray-50'
                  )}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      {presetKey === 'none' ? (
                        <ShieldCheck className="h-5 w-5 text-green-600" />
                      ) : presetKey === 'custom' ? (
                        <Settings className="h-5 w-5 text-blue-600" />
                      ) : (
                        <AlertTriangle
                          className={clsx(
                            'h-5 w-5',
                            presetKey === 'beginner'
                              ? 'text-yellow-500'
                              : presetKey === 'intermediate'
                                ? 'text-orange-500'
                                : 'text-red-500'
                          )}
                        />
                      )}
                      <div>
                        <div className="font-medium text-gray-900">{preset.name}</div>
                        <div className="text-sm text-gray-500">{preset.description}</div>
                      </div>
                    </div>
                    {presetKey !== 'custom' && presetKey !== 'none' && (
                      <span className="text-xs font-medium text-gray-500">
                        {getPresetVulnCount(presetKey)} vulns
                      </span>
                    )}
                  </div>
                </button>
              );
            })}
          </div>

          {/* Attack Narrative */}
          <div className="mt-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Attack Narrative (Optional)
            </label>
            <textarea
              value={vulnerabilities.narrative}
              onChange={(e) => setNarrative(e.target.value)}
              rows={4}
              placeholder="Describe the intended attack path or scenario for this range..."
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none"
            />
            <p className="mt-1 text-xs text-gray-500">
              This narrative helps document the intended learning objectives and attack chains.
            </p>
          </div>
        </div>

        {/* Per-VM Configuration */}
        <div>
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            Per-VM Vulnerabilities
            {vulnerabilities.preset !== 'custom' && (
              <span className="ml-2 text-sm font-normal text-gray-500">
                (Select "Custom" to edit)
              </span>
            )}
          </h3>

          {vms.length === 0 ? (
            <div className="text-center py-12 bg-gray-50 rounded-lg border border-dashed border-gray-300">
              <ShieldAlert className="h-12 w-12 text-gray-400 mx-auto mb-3" />
              <p className="text-gray-500 font-medium">No VMs in topology</p>
              <p className="text-sm text-gray-400 mt-1">
                Add VMs in the Network Topology step first
              </p>
            </div>
          ) : (
            <div className="space-y-4 max-h-[500px] overflow-y-auto pr-2">
              {vms.map((vm) => {
                const applicableVulns = getApplicableVulns(vm.templateName);
                const activeCount = getActiveVulnCount(vm.id, vm.templateName);

                return (
                  <div key={vm.id} className="border border-gray-200 rounded-lg overflow-hidden">
                    {/* VM Header */}
                    <div className="flex items-center justify-between px-4 py-3 bg-gray-50 border-b border-gray-200">
                      <div>
                        <div className="font-medium text-gray-900">{vm.hostname}</div>
                        <div className="text-xs text-gray-500">{vm.templateName}</div>
                      </div>
                      <div
                        className={clsx(
                          'px-2 py-1 rounded-full text-xs font-medium',
                          activeCount === 0
                            ? 'bg-green-100 text-green-700'
                            : activeCount <= 3
                              ? 'bg-yellow-100 text-yellow-700'
                              : 'bg-red-100 text-red-700'
                        )}
                      >
                        {activeCount} active
                      </div>
                    </div>

                    {/* Vulnerability List */}
                    <div className="p-3">
                      {applicableVulns.length === 0 ? (
                        <p className="text-sm text-gray-500 text-center py-2">
                          No vulnerabilities applicable to this template
                        </p>
                      ) : (
                        <div className="space-y-1">
                          {applicableVulns.map((vuln) => {
                            const isActive = isVulnActive(vm.id, vuln.id);
                            const isCustom = vulnerabilities.preset === 'custom';

                            return (
                              <label
                                key={vuln.id}
                                className={clsx(
                                  'flex items-center gap-3 p-2 rounded-md transition-colors',
                                  isCustom
                                    ? 'cursor-pointer hover:bg-gray-50'
                                    : 'cursor-not-allowed opacity-75',
                                  isActive && 'bg-red-50'
                                )}
                              >
                                <input
                                  type="checkbox"
                                  checked={isActive}
                                  disabled={!isCustom}
                                  onChange={() => isCustom && toggleVmVuln(vm.id, vuln.id)}
                                  className="h-4 w-4 text-red-600 rounded border-gray-300 disabled:opacity-50"
                                />
                                <span className="text-gray-500">{CATEGORY_ICONS[vuln.category]}</span>
                                <div className="flex-1 min-w-0">
                                  <div className="text-sm font-medium text-gray-900 truncate">
                                    {vuln.name}
                                  </div>
                                  <div className="text-xs text-gray-500 truncate">
                                    {vuln.description}
                                  </div>
                                </div>
                                <span
                                  className={clsx(
                                    'px-1.5 py-0.5 text-[10px] font-medium rounded',
                                    SEVERITY_COLORS[vuln.severity]
                                  )}
                                >
                                  {vuln.severity}
                                </span>
                              </label>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Summary Statistics */}
      {vms.length > 0 && (
        <div className="mt-8 p-4 bg-gray-50 rounded-lg">
          <h4 className="text-sm font-medium text-gray-700 mb-3">Vulnerability Summary</h4>
          <div className="grid grid-cols-4 gap-4">
            {(['critical', 'high', 'medium', 'low'] as const).map((severity) => {
              const count = vms.reduce((sum, vm) => {
                const applicable = getApplicableVulns(vm.templateName);
                return (
                  sum +
                  applicable.filter((v) => v.severity === severity && isVulnActive(vm.id, v.id))
                    .length
                );
              }, 0);

              return (
                <div key={severity} className="text-center">
                  <div
                    className={clsx(
                      'inline-block px-2 py-1 rounded-full text-xs font-medium mb-1',
                      SEVERITY_COLORS[severity]
                    )}
                  >
                    {severity}
                  </div>
                  <div className="text-2xl font-bold text-gray-900">{count}</div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
