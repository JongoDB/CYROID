// frontend/src/components/wizard-v2/steps/ServicesStep.tsx
import { useEffect, useState } from 'react';
import { Plus, Cpu, HardDrive, MemoryStick, X, ChevronDown, ChevronRight } from 'lucide-react';
import clsx from 'clsx';
import { useWizardStore, VMPlacement } from '../../../stores/wizardStore';
import {
  SERVICE_CATALOG,
  getServicesForEnvironment,
  OS_FAMILY_VERSIONS,
  OS_FAMILY_NAMES,
  resolveTemplateName,
} from '../data/servicePresets';
import { imagesApi } from '../../../services/api';
import type { BaseImage } from '../../../types';

// Track version overrides per service (serviceId -> version)
type VersionOverrides = Record<string, string>;

export function ServicesStep() {
  const { environment, services, toggleService, addCustomVM, removeCustomVM } = useWizardStore();
  const [baseImages, setBaseImages] = useState<BaseImage[]>([]);
  const [showImageModal, setShowImageModal] = useState(false);
  const [expandedServices, setExpandedServices] = useState<Set<string>>(new Set());
  const [versionOverrides, setVersionOverrides] = useState<VersionOverrides>({});

  const toggleExpanded = (serviceId: string) => {
    setExpandedServices((prev) => {
      const next = new Set(prev);
      if (next.has(serviceId)) {
        next.delete(serviceId);
      } else {
        next.add(serviceId);
      }
      return next;
    });
  };

  const setServiceVersion = (serviceId: string, version: string) => {
    setVersionOverrides((prev) => ({ ...prev, [serviceId]: version }));
  };

  const getServiceVersion = (serviceId: string, defaultVersion: string): string => {
    return versionOverrides[serviceId] || defaultVersion;
  };

  // Load base images on mount
  useEffect(() => {
    imagesApi.listBase().then(res => setBaseImages(res.data));
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

  const handleAddCustomVM = (baseImage: BaseImage) => {
    const vm: VMPlacement = {
      id: `custom-${Date.now()}`,
      hostname: baseImage.name.toLowerCase().replace(/\s+/g, '-'),
      baseImageId: baseImage.id,
      templateName: baseImage.name,
      networkId: '',
      ip: '',
      cpu: baseImage.default_cpu,
      ramMb: baseImage.default_ram_mb,
      diskGb: baseImage.default_disk_gb,
      position: { x: 0, y: 0 },
      osFamily: baseImage.os_type,
      osVersion: baseImage.iso_version || '',
    };
    addCustomVM(vm);
    setShowImageModal(false);
  };

  // Expose version overrides for use by NetworkStep when generating VMs
  // Store them in session storage so they persist across step navigation
  useEffect(() => {
    sessionStorage.setItem('wizard-version-overrides', JSON.stringify(versionOverrides));
  }, [versionOverrides]);

  // Load version overrides from session storage on mount
  useEffect(() => {
    const stored = sessionStorage.getItem('wizard-version-overrides');
    if (stored) {
      try {
        setVersionOverrides(JSON.parse(stored));
      } catch {
        // Ignore parse errors
      }
    }
  }, []);

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
            onClick={() => setShowImageModal(true)}
            className="mt-4 w-full inline-flex items-center justify-center px-4 py-2 text-sm font-medium text-primary-600 bg-primary-50 rounded-lg hover:bg-primary-100"
          >
            <Plus className="h-4 w-4 mr-2" />
            Add Custom VM
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
              {selectedServices.map((service) => {
                const isExpanded = expandedServices.has(service.id);
                const currentVersion = getServiceVersion(service.id, service.defaultVersion);
                const availableVersions = OS_FAMILY_VERSIONS[service.osFamily] || [service.defaultVersion];
                const osName = OS_FAMILY_NAMES[service.osFamily] || service.osFamily;

                return (
                  <div
                    key={service.id}
                    className="bg-gray-50 rounded-lg overflow-hidden"
                  >
                    <div className="flex items-center justify-between p-3">
                      <button
                        onClick={() => toggleExpanded(service.id)}
                        className="flex items-center gap-2 text-left flex-1"
                      >
                        {isExpanded ? (
                          <ChevronDown className="h-4 w-4 text-gray-400" />
                        ) : (
                          <ChevronRight className="h-4 w-4 text-gray-400" />
                        )}
                        <div>
                          <div className="text-sm font-medium text-gray-900">{service.name}</div>
                          <div className="text-xs text-gray-500">
                            {osName}: {currentVersion}
                          </div>
                        </div>
                      </button>
                      <button
                        onClick={() => toggleService(service.id)}
                        className="text-gray-400 hover:text-red-500 ml-2"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </div>

                    {isExpanded && (
                      <div className="px-3 pb-3 pt-0 ml-6 border-t border-gray-200">
                        <label className="block text-xs font-medium text-gray-600 mt-2 mb-1">
                          OS Version
                        </label>
                        <select
                          value={currentVersion}
                          onChange={(e) => setServiceVersion(service.id, e.target.value)}
                          className="w-full text-sm border border-gray-300 rounded-md px-2 py-1.5 focus:ring-primary-500 focus:border-primary-500"
                        >
                          {availableVersions.map((version) => (
                            <option key={version} value={version}>
                              {resolveTemplateName(service.osFamily, version)}
                            </option>
                          ))}
                        </select>
                      </div>
                    )}
                  </div>
                );
              })}

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

      {/* Base Image selection modal */}
      {showImageModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md max-h-[80vh] overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3 border-b">
              <h3 className="text-lg font-semibold">Select Base Image</h3>
              <button onClick={() => setShowImageModal(false)}>
                <X className="h-5 w-5 text-gray-400 hover:text-gray-500" />
              </button>
            </div>
            <div className="p-4 overflow-y-auto max-h-[60vh]">
              {baseImages.length === 0 ? (
                <p className="text-gray-500 text-center py-4">No base images available. Pull images from the Image Cache first.</p>
              ) : (
                <div className="space-y-2">
                  {baseImages.map((image) => (
                    <button
                      key={image.id}
                      onClick={() => handleAddCustomVM(image)}
                      className="w-full text-left p-3 rounded-lg border border-gray-200 hover:bg-gray-50"
                    >
                      <div className="flex items-center gap-2">
                        <div className="text-sm font-medium text-gray-900">{image.name}</div>
                        <span className={`px-1.5 py-0.5 text-[10px] font-medium rounded ${
                          image.image_type === 'container' ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700'
                        }`}>
                          {image.image_type}
                        </span>
                      </div>
                      <div className="text-xs text-gray-500">
                        {image.os_type} | {image.default_cpu} CPU, {image.default_ram_mb}MB RAM
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
