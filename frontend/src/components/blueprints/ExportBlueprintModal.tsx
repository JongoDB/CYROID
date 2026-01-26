// frontend/src/components/blueprints/ExportBlueprintModal.tsx
import { useState } from 'react';
import { Blueprint, BlueprintExportOptions, blueprintsApi } from '../../services/api';
import { X, Download, Loader2, AlertCircle, FileCode, Package, BookOpen, FileArchive, HardDrive } from 'lucide-react';
import { toast } from '../../stores/toastStore';

interface Props {
  blueprint: Blueprint;
  onClose: () => void;
}

export default function ExportBlueprintModal({ blueprint, onClose }: Props) {
  const [options, setOptions] = useState<BlueprintExportOptions>({
    include_msel: true,
    include_dockerfiles: true,
    include_docker_images: false,
    include_content: true,
    include_artifacts: false,
  });
  const [exporting, setExporting] = useState(false);

  const handleExport = async () => {
    setExporting(true);
    try {
      const blob = await blueprintsApi.export(blueprint.id, options);
      // Create download link
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `blueprint-${blueprint.name.replace(/[^a-zA-Z0-9-_]/g, '_')}.zip`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      toast.success('Blueprint exported successfully');
      onClose();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to export blueprint');
    } finally {
      setExporting(false);
    }
  };

  const toggleOption = (key: keyof BlueprintExportOptions) => {
    setOptions((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4">
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75" onClick={onClose} />

        <div className="relative bg-white rounded-lg shadow-xl max-w-lg w-full">
          <div className="flex items-center justify-between p-4 border-b">
            <div>
              <h3 className="text-lg font-medium text-gray-900">Export Blueprint</h3>
              <p className="text-sm text-gray-500">
                {blueprint.name} v{blueprint.version}
              </p>
            </div>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-500">
              <X className="h-5 w-5" />
            </button>
          </div>

          <div className="p-4 space-y-4">
            <p className="text-sm text-gray-600">
              Select what to include in the export package:
            </p>

            {/* Always included */}
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs font-medium text-gray-500 uppercase mb-2">Always Included</p>
              <div className="space-y-1 text-sm text-gray-700">
                <div className="flex items-center">
                  <span className="w-5 h-5 text-green-500 mr-2">✓</span>
                  Network configuration
                </div>
                <div className="flex items-center">
                  <span className="w-5 h-5 text-green-500 mr-2">✓</span>
                  VM definitions
                </div>
              </div>
            </div>

            {/* Optional items */}
            <div className="space-y-3">
              {/* MSEL */}
              <label className="flex items-start p-3 border rounded-lg hover:bg-gray-50 cursor-pointer">
                <input
                  type="checkbox"
                  checked={options.include_msel}
                  onChange={() => toggleOption('include_msel')}
                  className="h-4 w-4 mt-0.5 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                />
                <div className="ml-3 flex-1">
                  <div className="flex items-center">
                    <FileArchive className="h-4 w-4 mr-2 text-gray-400" />
                    <span className="font-medium text-sm text-gray-900">MSEL / Scenario Injects</span>
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Master Scenario Events List for exercise execution
                  </p>
                </div>
              </label>

              {/* Dockerfiles */}
              <label className="flex items-start p-3 border rounded-lg hover:bg-gray-50 cursor-pointer">
                <input
                  type="checkbox"
                  checked={options.include_dockerfiles}
                  onChange={() => toggleOption('include_dockerfiles')}
                  className="h-4 w-4 mt-0.5 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                />
                <div className="ml-3 flex-1">
                  <div className="flex items-center">
                    <FileCode className="h-4 w-4 mr-2 text-gray-400" />
                    <span className="font-medium text-sm text-gray-900">Dockerfiles</span>
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Source files for building custom Docker images
                  </p>
                </div>
              </label>

              {/* Content Library */}
              <label className="flex items-start p-3 border rounded-lg hover:bg-gray-50 cursor-pointer">
                <input
                  type="checkbox"
                  checked={options.include_content}
                  onChange={() => toggleOption('include_content')}
                  className="h-4 w-4 mt-0.5 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                />
                <div className="ml-3 flex-1">
                  <div className="flex items-center">
                    <BookOpen className="h-4 w-4 mr-2 text-gray-400" />
                    <span className="font-medium text-sm text-gray-900">Content Library Items</span>
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Student guides, instructor materials, and walkthroughs
                  </p>
                </div>
              </label>

              {/* Artifacts */}
              <label className="flex items-start p-3 border rounded-lg hover:bg-gray-50 cursor-pointer">
                <input
                  type="checkbox"
                  checked={options.include_artifacts}
                  onChange={() => toggleOption('include_artifacts')}
                  className="h-4 w-4 mt-0.5 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                />
                <div className="ml-3 flex-1">
                  <div className="flex items-center">
                    <Package className="h-4 w-4 mr-2 text-gray-400" />
                    <span className="font-medium text-sm text-gray-900">Artifacts</span>
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Tools, scripts, and evidence templates
                  </p>
                </div>
              </label>

              {/* Docker Images (with warning) */}
              <label className="flex items-start p-3 border rounded-lg hover:bg-gray-50 cursor-pointer">
                <input
                  type="checkbox"
                  checked={options.include_docker_images}
                  onChange={() => toggleOption('include_docker_images')}
                  className="h-4 w-4 mt-0.5 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                />
                <div className="ml-3 flex-1">
                  <div className="flex items-center">
                    <HardDrive className="h-4 w-4 mr-2 text-gray-400" />
                    <span className="font-medium text-sm text-gray-900">Docker Image Tarballs</span>
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Pre-built images for offline/air-gapped deployment
                  </p>
                  {options.include_docker_images && (
                    <div className="flex items-center mt-2 p-2 bg-amber-50 rounded text-xs text-amber-700">
                      <AlertCircle className="h-3.5 w-3.5 mr-1.5 flex-shrink-0" />
                      <span>This may result in a very large file (several GB)</span>
                    </div>
                  )}
                </div>
              </label>
            </div>
          </div>

          <div className="flex justify-end space-x-3 p-4 border-t bg-gray-50 rounded-b-lg">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              onClick={handleExport}
              disabled={exporting}
              className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50"
            >
              {exporting ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Download className="h-4 w-4 mr-2" />
              )}
              Export Blueprint
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
