// frontend/src/components/blueprints/ImportBlueprintModal.tsx
import { useState, useRef } from 'react';
import {
  blueprintsApi,
  BlueprintImportValidation,
  BlueprintImportOptions,
} from '../../services/api';
import {
  Upload,
  Loader2,
  CheckCircle,
  XCircle,
  AlertTriangle,
  FileArchive,
} from 'lucide-react';
import Modal, { ModalBody, ModalFooter } from '../common/Modal';

interface Props {
  onClose: () => void;
  onSuccess: () => void;
}

type Step = 'upload' | 'validating' | 'review' | 'importing' | 'done';

export default function ImportBlueprintModal({ onClose, onSuccess }: Props) {
  const [step, setStep] = useState<Step>('upload');
  const [file, setFile] = useState<File | null>(null);
  const [validation, setValidation] = useState<BlueprintImportValidation | null>(null);
  const [newName, setNewName] = useState('');
  const [templateStrategy, setTemplateStrategy] = useState<'skip' | 'update' | 'error'>('skip');
  const [contentStrategy, setContentStrategy] = useState<'skip' | 'rename' | 'use_existing'>('skip');
  const [error, setError] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<{
    blueprintName?: string;
    templatesCreated: string[];
    templatesSkipped: string[];
    dockerfilesExtracted?: string[];
    imagesBuilt?: string[];
    contentImported?: boolean;
    artifactsImported?: string[];
    warnings: string[];
  } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) return;

    // Accept .zip and .tar.gz (for legacy v2.0 Range Export format)
    if (!selectedFile.name.endsWith('.zip') && !selectedFile.name.endsWith('.tar.gz')) {
      setError('Please select a ZIP or TAR.GZ file');
      return;
    }

    setFile(selectedFile);
    setError(null);
    setStep('validating');

    try {
      const result = await blueprintsApi.validateImport(selectedFile);
      setValidation(result);
      setNewName(result.blueprint_name);
      setStep('review');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to validate blueprint');
      setStep('upload');
    }
  };

  const handleImport = async () => {
    if (!file) return;

    setStep('importing');
    setError(null);

    try {
      const options: BlueprintImportOptions = {
        template_conflict_strategy: templateStrategy,
        content_conflict_strategy: contentStrategy,
      };

      // Only set new_name if it's different from the original
      if (validation && newName !== validation.blueprint_name) {
        options.new_name = newName;
      }

      const result = await blueprintsApi.import(file, options);

      if (result.success) {
        setImportResult({
          blueprintName: result.blueprint_name,
          templatesCreated: result.templates_created,
          templatesSkipped: result.templates_skipped,
          dockerfilesExtracted: result.dockerfiles_extracted,
          imagesBuilt: result.images_built,
          contentImported: result.content_imported,
          artifactsImported: result.artifacts_imported,
          warnings: result.warnings,
        });
        setStep('done');
      } else {
        setError(result.errors[0] || 'Import failed');
        setStep('review');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to import blueprint');
      setStep('review');
    }
  };

  const handleDone = () => {
    onSuccess();
    onClose();
  };

  const resetModal = () => {
    setFile(null);
    setValidation(null);
    setNewName('');
    setTemplateStrategy('skip');
    setContentStrategy('skip');
    setError(null);
    setImportResult(null);
    setStep('upload');
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // Determine if close should be disabled (during async operations)
  const isProcessing = step === 'validating' || step === 'importing';

  // Dynamic description based on step
  const getDescription = () => {
    switch (step) {
      case 'upload':
        return 'Upload a blueprint package';
      case 'validating':
        return 'Validating...';
      case 'review':
        return 'Review import';
      case 'importing':
        return 'Importing...';
      case 'done':
        return 'Import complete';
      default:
        return undefined;
    }
  };

  return (
    <Modal
      isOpen={true}
      onClose={onClose}
      title="Import Blueprint"
      description={getDescription()}
      size="lg"
      showCloseButton={!isProcessing}
      closeOnBackdrop={!isProcessing}
      closeOnEscape={!isProcessing}
    >
      <ModalBody>
        {/* Upload Step */}
        {step === 'upload' && (
          <div className="space-y-4">
            <div
              className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center cursor-pointer hover:border-indigo-400"
              onClick={() => fileInputRef.current?.click()}
            >
              <FileArchive className="mx-auto h-12 w-12 text-gray-400" />
              <p className="mt-2 text-sm text-gray-600">
                Click to select a blueprint package
              </p>
              <p className="text-xs text-gray-500 mt-1">
                Supports Blueprint Export (.zip) and legacy Range Export (.tar.gz)
              </p>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".zip,.tar.gz"
              onChange={handleFileSelect}
              className="hidden"
            />
            {error && (
              <div className="flex items-center text-red-600 text-sm">
                <XCircle className="h-4 w-4 mr-2" />
                {error}
              </div>
            )}
          </div>
        )}

        {/* Validating Step */}
        {step === 'validating' && (
          <div className="flex flex-col items-center py-8">
            <Loader2 className="h-8 w-8 animate-spin text-indigo-600" />
            <p className="mt-4 text-sm text-gray-600">Validating blueprint package...</p>
          </div>
        )}

        {/* Review Step */}
        {step === 'review' && validation && (
          <div className="space-y-4">
            {/* Validation Status */}
            <div
              className={`flex items-center p-3 rounded-md ${
                validation.valid
                  ? 'bg-green-50 text-green-700'
                  : 'bg-red-50 text-red-700'
              }`}
            >
              {validation.valid ? (
                <CheckCircle className="h-5 w-5 mr-2" />
              ) : (
                <XCircle className="h-5 w-5 mr-2" />
              )}
              <span className="text-sm font-medium">
                {validation.valid ? 'Blueprint is valid' : 'Blueprint has issues'}
              </span>
            </div>

            {/* Format Version */}
            {validation.manifest_version && (
              <div className="text-xs text-gray-500 -mt-2">
                Package format: v{validation.manifest_version}
                {validation.manifest_version === '2.0' && ' (Legacy Range Export)'}
                {validation.manifest_version === '3.0' && ' (Blueprint Export)'}
                {validation.manifest_version === '4.0' && ' (Unified Range Blueprint)'}
              </div>
            )}

            {/* Blueprint Name */}
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Blueprint Name
              </label>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              />
              {validation.conflicts.length > 0 && (
                <p className="mt-1 text-xs text-amber-600">
                  A blueprint with this name already exists. Change the name to import.
                </p>
              )}
            </div>

            {/* Package Contents Summary */}
            <div className="bg-gray-50 rounded-md p-3">
              <h4 className="text-sm font-medium text-gray-700 mb-2">Package Contents</h4>
              <div className="grid grid-cols-2 gap-2 text-sm">
                {validation.msel_included && (
                  <div className="flex items-center text-gray-600">
                    <span className="w-2 h-2 bg-green-400 rounded-full mr-2" />
                    MSEL / Injects
                  </div>
                )}
                {validation.included_dockerfiles && validation.included_dockerfiles.length > 0 && (
                  <div className="flex items-center text-gray-600">
                    <span className="w-2 h-2 bg-green-400 rounded-full mr-2" />
                    {validation.included_dockerfiles.length} Dockerfile(s)
                  </div>
                )}
                {validation.content_included && (
                  <div className="flex items-center text-gray-600">
                    <span className="w-2 h-2 bg-green-400 rounded-full mr-2" />
                    Content Library
                  </div>
                )}
                {validation.included_artifacts && validation.included_artifacts.length > 0 && (
                  <div className="flex items-center text-gray-600">
                    <span className="w-2 h-2 bg-green-400 rounded-full mr-2" />
                    {validation.included_artifacts.length} Artifact(s)
                  </div>
                )}
              </div>
            </div>

            {/* Included Templates */}
            {validation.included_templates.length > 0 && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Included Templates ({validation.included_templates.length})
                </label>
                <div className="bg-gray-50 rounded-md p-3 max-h-32 overflow-y-auto">
                  <ul className="text-sm text-gray-600 space-y-1">
                    {validation.included_templates.map((tpl) => (
                      <li key={tpl} className="flex items-center">
                        <span className="w-2 h-2 bg-indigo-400 rounded-full mr-2" />
                        {tpl}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            )}

            {/* Template Conflict Strategy */}
            {validation.warnings.some((w) => w.includes('already exists')) && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Template Conflict Strategy
                </label>
                <select
                  value={templateStrategy}
                  onChange={(e) =>
                    setTemplateStrategy(e.target.value as 'skip' | 'update' | 'error')
                  }
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                >
                  <option value="skip">Use existing templates (skip)</option>
                  <option value="update">Update existing templates</option>
                  <option value="error">Fail if templates exist</option>
                </select>
              </div>
            )}

            {/* Content Library Info & Conflict */}
            {validation.content_included && (
              <div className="bg-blue-50 rounded-md p-3">
                <h4 className="text-sm font-medium text-blue-800 mb-2">
                  Content Library Item Included
                </h4>
                {validation.content_conflict ? (
                  <div className="space-y-3">
                    <p className="text-sm text-amber-700">
                      Warning: Content with this title already exists: "{validation.content_conflict}"
                    </p>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Content Conflict Strategy
                      </label>
                      <select
                        value={contentStrategy}
                        onChange={(e) =>
                          setContentStrategy(e.target.value as 'skip' | 'rename' | 'use_existing')
                        }
                        className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                      >
                        <option value="use_existing">Use existing content (don't import)</option>
                        <option value="rename">Import with new name (add suffix)</option>
                        <option value="skip">Skip content import entirely</option>
                      </select>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-blue-700">
                    Content will be imported as a new item
                  </p>
                )}
              </div>
            )}

            {/* Errors */}
            {validation.errors.length > 0 && (
              <div className="bg-red-50 rounded-md p-3">
                <h4 className="text-sm font-medium text-red-800 mb-2">Errors</h4>
                <ul className="text-sm text-red-700 space-y-1">
                  {validation.errors.map((err, i) => (
                    <li key={i}>{err}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Warnings */}
            {validation.warnings.length > 0 && (
              <div className="bg-amber-50 rounded-md p-3">
                <h4 className="text-sm font-medium text-amber-800 mb-2 flex items-center">
                  <AlertTriangle className="h-4 w-4 mr-1" />
                  Warnings
                </h4>
                <ul className="text-sm text-amber-700 space-y-1">
                  {validation.warnings.map((warn, i) => (
                    <li key={i}>{warn}</li>
                  ))}
                </ul>
              </div>
            )}

            {error && (
              <div className="flex items-center text-red-600 text-sm">
                <XCircle className="h-4 w-4 mr-2" />
                {error}
              </div>
            )}
          </div>
        )}

        {/* Importing Step */}
        {step === 'importing' && (
          <div className="flex flex-col items-center py-8">
            <Loader2 className="h-8 w-8 animate-spin text-indigo-600" />
            <p className="mt-4 text-sm text-gray-600">Importing blueprint...</p>
          </div>
        )}

        {/* Done Step */}
        {step === 'done' && importResult && (
          <div className="space-y-4">
            <div className="flex items-center p-3 rounded-md bg-green-50 text-green-700">
              <CheckCircle className="h-5 w-5 mr-2" />
              <span className="text-sm font-medium">
                Blueprint "{importResult.blueprintName}" imported successfully
              </span>
            </div>

            {/* Import Summary */}
            <div className="bg-gray-50 rounded-md p-3">
              <h4 className="text-sm font-medium text-gray-700 mb-2">Import Summary</h4>
              <div className="grid grid-cols-2 gap-2 text-sm text-gray-600">
                {importResult.dockerfilesExtracted && importResult.dockerfilesExtracted.length > 0 && (
                  <div className="flex items-center">
                    <CheckCircle className="h-3 w-3 text-green-500 mr-2" />
                    {importResult.dockerfilesExtracted.length} Dockerfile(s)
                  </div>
                )}
                {importResult.imagesBuilt && importResult.imagesBuilt.length > 0 && (
                  <div className="flex items-center">
                    <CheckCircle className="h-3 w-3 text-green-500 mr-2" />
                    {importResult.imagesBuilt.length} Image(s) built
                  </div>
                )}
                {importResult.contentImported && (
                  <div className="flex items-center">
                    <CheckCircle className="h-3 w-3 text-green-500 mr-2" />
                    Content Library item
                  </div>
                )}
                {importResult.artifactsImported && importResult.artifactsImported.length > 0 && (
                  <div className="flex items-center">
                    <CheckCircle className="h-3 w-3 text-green-500 mr-2" />
                    {importResult.artifactsImported.length} Artifact(s)
                  </div>
                )}
              </div>
            </div>

            {importResult.templatesCreated.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-gray-700 mb-2">
                  Templates Created ({importResult.templatesCreated.length})
                </h4>
                <ul className="text-sm text-gray-600 bg-gray-50 rounded-md p-3 space-y-1">
                  {importResult.templatesCreated.map((tpl, i) => (
                    <li key={i} className="flex items-center">
                      <CheckCircle className="h-3 w-3 text-green-500 mr-2" />
                      {tpl}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {importResult.templatesSkipped.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-gray-700 mb-2">
                  Templates Skipped ({importResult.templatesSkipped.length})
                </h4>
                <ul className="text-sm text-gray-500 bg-gray-50 rounded-md p-3 space-y-1">
                  {importResult.templatesSkipped.map((tpl, i) => (
                    <li key={i}>{tpl} (using existing)</li>
                  ))}
                </ul>
              </div>
            )}

            {importResult.warnings.length > 0 && (
              <div className="bg-amber-50 rounded-md p-3">
                <h4 className="text-sm font-medium text-amber-800 mb-2">Warnings</h4>
                <ul className="text-sm text-amber-700 space-y-1">
                  {importResult.warnings.map((warn, i) => (
                    <li key={i}>{warn}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </ModalBody>

      {/* Footer */}
      <ModalFooter>
        {step === 'upload' && (
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
          >
            Cancel
          </button>
        )}

        {step === 'review' && (
          <>
            <button
              type="button"
              onClick={resetModal}
              className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
            >
              Back
            </button>
            <button
              type="button"
              onClick={handleImport}
              disabled={
                !newName ||
                (validation?.conflicts.length ?? 0) > 0 && newName === validation?.blueprint_name
              }
              className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50"
            >
              <Upload className="h-4 w-4 mr-2" />
              Import Blueprint
            </button>
          </>
        )}

        {step === 'done' && (
          <button
            type="button"
            onClick={handleDone}
            className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700"
          >
            <CheckCircle className="h-4 w-4 mr-2" />
            Done
          </button>
        )}
      </ModalFooter>
    </Modal>
  );
}
