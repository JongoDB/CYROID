// frontend/src/components/blueprints/SaveBlueprintModal.tsx
// Unified modal for saving a range as a blueprint with export options (Issue #131)
import { useState, useEffect } from 'react';
import { blueprintsApi, BlueprintCreate, BlueprintExportOptions, BlueprintExportSizeEstimate } from '../../services/api';
import { LayoutTemplate, Loader2, Download, FileCode, Package, BookOpen, FileArchive, HardDrive, AlertCircle } from 'lucide-react';
import { toast } from '../../stores/toastStore';
import { Modal, ModalBody, ModalFooter } from '../common/Modal';

interface Props {
  rangeId: string;
  rangeName: string;
  onClose: () => void;
  onSuccess: () => void;
}

export default function SaveBlueprintModal({
  rangeId,
  rangeName,
  onClose,
  onSuccess,
}: Props) {
  const [name, setName] = useState(rangeName);
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportProgress, setExportProgress] = useState<string>('');

  // Size estimation
  const [sizeEstimate, setSizeEstimate] = useState<BlueprintExportSizeEstimate | null>(null);
  const [loadingSize, setLoadingSize] = useState(false);

  // Export options
  const [exportOptions, setExportOptions] = useState<BlueprintExportOptions>({
    include_msel: true,
    include_dockerfiles: true,
    include_docker_images: false,
    include_content: true,
    include_artifacts: false,
  });

  // Fetch size estimate when Docker images option changes
  useEffect(() => {
    if (exportOptions.include_docker_images) {
      fetchSizeEstimate();
    } else {
      setSizeEstimate(null);
    }
  }, [exportOptions.include_docker_images]);

  const fetchSizeEstimate = async () => {
    setLoadingSize(true);
    try {
      // First we need to save the blueprint to get an ID, or use a different approach
      // For now, we'll create a temporary blueprint to get the estimate
      // Actually, we need a range-based endpoint instead
      // Let's skip this for now and show a generic message
      setSizeEstimate(null);
    } catch (err) {
      console.error('Failed to fetch size estimate:', err);
    } finally {
      setLoadingSize(false);
    }
  };

  const toggleOption = (key: keyof BlueprintExportOptions) => {
    setExportOptions((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  const handleSaveOnly = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);

    try {
      const data: BlueprintCreate = {
        range_id: rangeId,
        name,
        description: description || undefined,
      };
      await blueprintsApi.create(data);
      toast.success('Blueprint saved successfully');
      onSuccess();
      onClose();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to save blueprint');
    } finally {
      setSubmitting(false);
    }
  };

  const handleSaveAndExport = async () => {
    setExporting(true);
    setExportProgress('Creating blueprint...');

    try {
      // First, create the blueprint
      const data: BlueprintCreate = {
        range_id: rangeId,
        name,
        description: description || undefined,
      };
      const blueprint = await blueprintsApi.create(data);

      // If Docker images are included, fetch size estimate for progress display
      if (exportOptions.include_docker_images) {
        setExportProgress('Calculating export size...');
        try {
          const estimate = await blueprintsApi.getExportSize(blueprint.data.id, true);
          setSizeEstimate(estimate);
          setExportProgress(`Exporting ${estimate.docker_images.length} Docker images (${estimate.docker_images_total_human})...`);
        } catch (err) {
          setExportProgress('Exporting Docker images...');
        }
      } else {
        setExportProgress('Generating export package...');
      }

      // Then export it with the selected options
      const blob = await blueprintsApi.export(blueprint.data.id, exportOptions);

      // Create download link
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `blueprint-${name.replace(/[^a-zA-Z0-9-_]/g, '_')}.zip`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      toast.success('Blueprint saved and exported successfully');
      onSuccess();
      onClose();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to save and export blueprint');
    } finally {
      setExporting(false);
      setExportProgress('');
    }
  };

  const isProcessing = submitting || exporting;

  return (
    <Modal
      isOpen={true}
      onClose={onClose}
      title="Save as Blueprint"
      description="Create a reusable blueprint from this range"
      size="lg"
      closeOnBackdrop={!isProcessing}
      closeOnEscape={!isProcessing}
      showCloseButton={!isProcessing}
    >
      <form onSubmit={handleSaveOnly}>
        <ModalBody className="space-y-4">
          {/* Name and Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Blueprint Name
            </label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              placeholder="e.g., Red Team Training Lab"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">
              Description
            </label>
            <textarea
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              placeholder="Optional description..."
            />
          </div>

          {/* Always included section */}
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

          {/* Export options */}
          <div>
            <p className="text-sm font-medium text-gray-700 mb-2">
              Include in export package:
            </p>
            <div className="space-y-2">
              {/* MSEL */}
              <label className="flex items-start p-2 border rounded-lg hover:bg-gray-50 cursor-pointer">
                <input
                  type="checkbox"
                  checked={exportOptions.include_msel}
                  onChange={() => toggleOption('include_msel')}
                  className="h-4 w-4 mt-0.5 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                />
                <div className="ml-3 flex-1">
                  <div className="flex items-center">
                    <FileArchive className="h-4 w-4 mr-2 text-gray-400" />
                    <span className="font-medium text-sm text-gray-900">MSEL / Scenario Injects</span>
                  </div>
                </div>
              </label>

              {/* Dockerfiles */}
              <label className="flex items-start p-2 border rounded-lg hover:bg-gray-50 cursor-pointer">
                <input
                  type="checkbox"
                  checked={exportOptions.include_dockerfiles}
                  onChange={() => toggleOption('include_dockerfiles')}
                  className="h-4 w-4 mt-0.5 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                />
                <div className="ml-3 flex-1">
                  <div className="flex items-center">
                    <FileCode className="h-4 w-4 mr-2 text-gray-400" />
                    <span className="font-medium text-sm text-gray-900">Dockerfiles</span>
                  </div>
                </div>
              </label>

              {/* Content Library */}
              <label className="flex items-start p-2 border rounded-lg hover:bg-gray-50 cursor-pointer">
                <input
                  type="checkbox"
                  checked={exportOptions.include_content}
                  onChange={() => toggleOption('include_content')}
                  className="h-4 w-4 mt-0.5 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                />
                <div className="ml-3 flex-1">
                  <div className="flex items-center">
                    <BookOpen className="h-4 w-4 mr-2 text-gray-400" />
                    <span className="font-medium text-sm text-gray-900">Content Library Items</span>
                  </div>
                </div>
              </label>

              {/* Artifacts */}
              <label className="flex items-start p-2 border rounded-lg hover:bg-gray-50 cursor-pointer">
                <input
                  type="checkbox"
                  checked={exportOptions.include_artifacts}
                  onChange={() => toggleOption('include_artifacts')}
                  className="h-4 w-4 mt-0.5 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                />
                <div className="ml-3 flex-1">
                  <div className="flex items-center">
                    <Package className="h-4 w-4 mr-2 text-gray-400" />
                    <span className="font-medium text-sm text-gray-900">Artifacts</span>
                  </div>
                </div>
              </label>

              {/* Docker Images (with warning) */}
              <label className="flex items-start p-2 border rounded-lg hover:bg-gray-50 cursor-pointer">
                <input
                  type="checkbox"
                  checked={exportOptions.include_docker_images}
                  onChange={() => toggleOption('include_docker_images')}
                  className="h-4 w-4 mt-0.5 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                />
                <div className="ml-3 flex-1">
                  <div className="flex items-center">
                    <HardDrive className="h-4 w-4 mr-2 text-gray-400" />
                    <span className="font-medium text-sm text-gray-900">Docker Image Tarballs</span>
                  </div>
                  {exportOptions.include_docker_images && (
                    <div className="mt-1 space-y-1">
                      <div className="flex items-center p-1.5 bg-amber-50 rounded text-xs text-amber-700">
                        <AlertCircle className="h-3.5 w-3.5 mr-1.5 flex-shrink-0" />
                        <span>Large file size - may take several minutes to export</span>
                      </div>
                      {sizeEstimate && sizeEstimate.docker_images.length > 0 && (
                        <div className="p-1.5 bg-blue-50 rounded text-xs text-blue-700">
                          <span className="font-medium">Estimated size: {sizeEstimate.docker_images_total_human}</span>
                          <div className="mt-1 text-blue-600">
                            {sizeEstimate.docker_images.map((img, i) => (
                              <div key={i}>• {img.tag}: {img.size_human}</div>
                            ))}
                          </div>
                        </div>
                      )}
                      {loadingSize && (
                        <div className="flex items-center p-1.5 bg-gray-50 rounded text-xs text-gray-600">
                          <Loader2 className="h-3 w-3 mr-1.5 animate-spin" />
                          <span>Calculating size...</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </label>
            </div>
          </div>

          {/* Export Progress */}
          {exporting && exportProgress && (
            <div className="bg-indigo-50 rounded-lg p-3">
              <div className="flex items-center">
                <Loader2 className="h-5 w-5 mr-3 text-indigo-600 animate-spin" />
                <div>
                  <p className="text-sm font-medium text-indigo-900">{exportProgress}</p>
                  <p className="text-xs text-indigo-600 mt-0.5">
                    Please wait, this may take a while for large images...
                  </p>
                </div>
              </div>
              {/* Progress bar (indeterminate) */}
              <div className="mt-2 h-1.5 bg-indigo-200 rounded-full overflow-hidden">
                <div className="h-full bg-indigo-600 rounded-full animate-pulse" style={{ width: '100%' }} />
              </div>
            </div>
          )}
        </ModalBody>

        <ModalFooter>
          <button
            type="button"
            onClick={onClose}
            disabled={isProcessing}
            className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isProcessing || !name}
            className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
          >
            {submitting ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <LayoutTemplate className="h-4 w-4 mr-2" />
            )}
            Save Only
          </button>
          <button
            type="button"
            onClick={handleSaveAndExport}
            disabled={isProcessing || !name}
            className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50"
          >
            {exporting ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Download className="h-4 w-4 mr-2" />
            )}
            Save & Export
          </button>
        </ModalFooter>
      </form>
    </Modal>
  );
}
