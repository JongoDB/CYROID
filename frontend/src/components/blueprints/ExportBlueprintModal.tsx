// frontend/src/components/blueprints/ExportBlueprintModal.tsx
import { useState, useEffect, useRef } from 'react';
import { Blueprint, BlueprintExportOptions, api } from '../../services/api';
import { X, Download, Loader2, AlertCircle, FileCode, Package, BookOpen, FileArchive, HardDrive, CheckCircle, XCircle } from 'lucide-react';
import { toast } from '../../stores/toastStore';

interface ExportJobStatus {
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  step: string;
  progress: number;
  total_steps: number;
  current_item?: string;
  error?: string;
  download_path?: string;
  filename?: string;
}

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

  // Export state
  const [exporting, setExporting] = useState(false);
  const [exportJobId, setExportJobId] = useState<string | null>(null);
  const [exportStatus, setExportStatus] = useState<ExportJobStatus | null>(null);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, []);

  const pollExportStatus = async (jobId: string) => {
    try {
      const response = await api.get<ExportJobStatus>(`/blueprints/export/${jobId}/status`);
      const status = response.data;
      setExportStatus(status);

      if (status.status === 'completed') {
        // Stop polling
        if (pollingRef.current) {
          clearInterval(pollingRef.current);
          pollingRef.current = null;
        }
        // Trigger download
        const token = localStorage.getItem('token');
        const downloadUrl = `/api/v1/blueprints/export/${jobId}/download?token=${token}`;

        // Use iframe to trigger download
        const iframe = document.createElement('iframe');
        iframe.style.display = 'none';
        iframe.src = downloadUrl;
        document.body.appendChild(iframe);
        setTimeout(() => document.body.removeChild(iframe), 10000);

        toast.success('Export complete - download started');
        setTimeout(() => {
          setExporting(false);
          onClose();
        }, 1500);
      } else if (status.status === 'failed') {
        if (pollingRef.current) {
          clearInterval(pollingRef.current);
          pollingRef.current = null;
        }
        toast.error(status.error || 'Export failed');
        setExporting(false);
      } else if (status.status === 'cancelled') {
        if (pollingRef.current) {
          clearInterval(pollingRef.current);
          pollingRef.current = null;
        }
        toast.info('Export cancelled');
        setExporting(false);
      }
    } catch (err) {
      console.error('Failed to poll export status:', err);
    }
  };

  const handleExport = async () => {
    setExporting(true);
    setExportStatus({ status: 'pending', step: 'Starting export...', progress: 0, total_steps: 6 });

    try {
      // Start async export job
      const params = new URLSearchParams();
      params.append('include_msel', String(options.include_msel));
      params.append('include_dockerfiles', String(options.include_dockerfiles));
      params.append('include_docker_images', String(options.include_docker_images));
      params.append('include_content', String(options.include_content));
      params.append('include_artifacts', String(options.include_artifacts));

      const response = await api.post<{ job_id: string }>(
        `/blueprints/${blueprint.id}/export/start?${params.toString()}`
      );

      const jobId = response.data.job_id;
      setExportJobId(jobId);
      setExportStatus({ status: 'pending', step: 'Export queued...', progress: 0, total_steps: 6 });

      // Start polling for status
      pollingRef.current = setInterval(() => pollExportStatus(jobId), 1000);

    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to start export');
      setExporting(false);
      setExportStatus(null);
    }
  };

  const handleCancel = async () => {
    if (!exportJobId) {
      onClose();
      return;
    }

    try {
      await api.post(`/blueprints/export/${exportJobId}/cancel`);
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
      setExporting(false);
      setExportStatus(null);
      setExportJobId(null);
      toast.info('Export cancelled');
    } catch (err: any) {
      console.error('Failed to cancel export:', err);
      // Close anyway
      onClose();
    }
  };

  const toggleOption = (key: keyof BlueprintExportOptions) => {
    setOptions((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  // Calculate progress percentage
  const progressPercent = exportStatus
    ? Math.round((exportStatus.progress / exportStatus.total_steps) * 100)
    : 0;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4">
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75" onClick={exporting ? undefined : onClose} />

        <div className="relative bg-white rounded-lg shadow-xl max-w-lg w-full">
          <div className="flex items-center justify-between p-4 border-b">
            <div>
              <h3 className="text-lg font-medium text-gray-900">Export Blueprint</h3>
              <p className="text-sm text-gray-500">
                {blueprint.name} v{blueprint.version}
              </p>
            </div>
            <button
              onClick={exporting ? handleCancel : onClose}
              className="text-gray-400 hover:text-gray-500"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Export Progress Overlay */}
          {exporting && exportStatus && (
            <div className="p-6 space-y-4">
              <div className="flex items-center justify-center">
                {exportStatus.status === 'completed' ? (
                  <CheckCircle className="h-12 w-12 text-green-500" />
                ) : exportStatus.status === 'failed' ? (
                  <XCircle className="h-12 w-12 text-red-500" />
                ) : (
                  <Loader2 className="h-12 w-12 text-indigo-600 animate-spin" />
                )}
              </div>

              <div className="text-center">
                <p className="text-lg font-medium text-gray-900">{exportStatus.step}</p>
                {exportStatus.current_item && (
                  <p className="text-sm text-gray-500 mt-1 font-mono truncate">
                    {exportStatus.current_item}
                  </p>
                )}
              </div>

              {/* Progress bar */}
              <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
                <div
                  className="bg-indigo-600 h-3 rounded-full transition-all duration-300"
                  style={{ width: `${progressPercent}%` }}
                />
              </div>

              <p className="text-center text-sm text-gray-500">
                Step {exportStatus.progress} of {exportStatus.total_steps}
              </p>

              {exportStatus.error && (
                <div className="p-3 bg-red-50 rounded-lg">
                  <p className="text-sm text-red-700">{exportStatus.error}</p>
                </div>
              )}

              {/* Cancel button */}
              {(exportStatus.status === 'pending' || exportStatus.status === 'running') && (
                <div className="flex justify-center pt-2">
                  <button
                    onClick={handleCancel}
                    className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
                  >
                    Cancel Export
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Normal form (hidden during export) */}
          {!exporting && (
            <>
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
            </>
          )}
        </div>
      </div>
    </div>
  );
}
