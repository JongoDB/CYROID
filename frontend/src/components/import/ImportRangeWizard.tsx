// frontend/src/components/import/ImportRangeWizard.tsx
import { useState, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { rangesApi } from '../../services/api'
import type { ImportValidationResult, ImportResult } from '../../types'

interface ImportRangeWizardProps {
  isOpen: boolean
  onClose: () => void
}

type WizardStep = 'upload' | 'validate' | 'options' | 'importing' | 'complete'

export default function ImportRangeWizard({ isOpen, onClose }: ImportRangeWizardProps) {
  const navigate = useNavigate()
  const fileInputRef = useRef<HTMLInputElement>(null)

  // State
  const [step, setStep] = useState<WizardStep>('upload')
  const [file, setFile] = useState<File | null>(null)
  const [dragActive, setDragActive] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [validationResult, setValidationResult] = useState<ImportValidationResult | null>(null)
  const [importResult, setImportResult] = useState<ImportResult | null>(null)

  // Import options
  const [nameOverride, setNameOverride] = useState('')
  const [templateConflictAction, setTemplateConflictAction] = useState<
    'use_existing' | 'create_new' | 'skip'
  >('use_existing')
  const [skipArtifacts, setSkipArtifacts] = useState(false)
  const [skipMsel, setSkipMsel] = useState(false)
  const [skipWalkthrough, setSkipWalkthrough] = useState(false)

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0]
      if (
        droppedFile.name.endsWith('.zip') ||
        droppedFile.name.endsWith('.tar.gz') ||
        droppedFile.name.endsWith('.tgz')
      ) {
        setFile(droppedFile)
        setError(null)
      } else {
        setError('Please upload a .zip or .tar.gz file')
      }
    }
  }, [])

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0]
      if (
        selectedFile.name.endsWith('.zip') ||
        selectedFile.name.endsWith('.tar.gz') ||
        selectedFile.name.endsWith('.tgz')
      ) {
        setFile(selectedFile)
        setError(null)
      } else {
        setError('Please upload a .zip or .tar.gz file')
      }
    }
  }, [])

  const handleValidate = useCallback(async () => {
    if (!file) return

    setIsLoading(true)
    setError(null)
    setStep('validate')

    try {
      const response = await rangesApi.validateImport(file)
      setValidationResult(response.data)

      // Pre-fill name override if there's a conflict
      if (response.data.conflicts.name_conflict) {
        setNameOverride(`${response.data.summary.range_name} (Imported)`)
      }

      setStep('options')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Validation failed')
      setStep('upload')
    } finally {
      setIsLoading(false)
    }
  }, [file])

  const handleImport = useCallback(async () => {
    if (!file) return

    setIsLoading(true)
    setError(null)
    setStep('importing')

    try {
      const response = await rangesApi.executeImport(file, {
        name_override: nameOverride || undefined,
        template_conflict_action: templateConflictAction,
        skip_artifacts: skipArtifacts,
        skip_msel: skipMsel,
        skip_walkthrough: skipWalkthrough,
      })

      setImportResult(response.data)
      setStep('complete')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed')
      setStep('options')
    } finally {
      setIsLoading(false)
    }
  }, [file, nameOverride, templateConflictAction, skipArtifacts, skipMsel, skipWalkthrough])

  const handleNavigateToRange = useCallback(() => {
    if (importResult?.range_id) {
      navigate(`/ranges/${importResult.range_id}`)
      onClose()
    }
  }, [importResult, navigate, onClose])

  const resetWizard = useCallback(() => {
    setStep('upload')
    setFile(null)
    setError(null)
    setValidationResult(null)
    setImportResult(null)
    setNameOverride('')
    setTemplateConflictAction('use_existing')
    setSkipArtifacts(false)
    setSkipMsel(false)
    setSkipWalkthrough(false)
  }, [])

  if (!isOpen) return null

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-screen items-center justify-center px-4 py-12">
        {/* Backdrop */}
        <div
          className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity"
          onClick={step === 'complete' ? onClose : undefined}
        />

        {/* Modal */}
        <div className="relative bg-white rounded-lg shadow-xl max-w-2xl w-full p-6">
          {/* Header */}
          <div className="mb-6">
            <h3 className="text-lg font-semibold text-gray-900">Import Range</h3>
            <p className="mt-1 text-sm text-gray-500">
              {step === 'upload' && 'Upload an exported range archive to import'}
              {step === 'validate' && 'Validating archive...'}
              {step === 'options' && 'Configure import options'}
              {step === 'importing' && 'Importing range...'}
              {step === 'complete' && 'Import complete'}
            </p>
          </div>

          {/* Error */}
          {error && (
            <div className="mb-4 bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded relative">
              {error}
              <button
                type="button"
                className="absolute top-0 right-0 p-4"
                onClick={() => setError(null)}
              >
                &times;
              </button>
            </div>
          )}

          {/* Step: Upload */}
          {step === 'upload' && (
            <div>
              <div
                className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                  dragActive
                    ? 'border-primary-500 bg-primary-50'
                    : 'border-gray-300 hover:border-gray-400'
                }`}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".zip,.tar.gz,.tgz"
                  onChange={handleFileSelect}
                  className="hidden"
                />

                {file ? (
                  <div>
                    <div className="text-4xl mb-2">📦</div>
                    <p className="text-sm font-medium text-gray-900">{file.name}</p>
                    <p className="text-xs text-gray-500">{formatBytes(file.size)}</p>
                    <button
                      type="button"
                      onClick={() => setFile(null)}
                      className="mt-2 text-sm text-red-600 hover:text-red-800"
                    >
                      Remove
                    </button>
                  </div>
                ) : (
                  <div>
                    <div className="text-4xl mb-2">📁</div>
                    <p className="text-sm text-gray-600">
                      Drag and drop an export archive here, or{' '}
                      <button
                        type="button"
                        onClick={() => fileInputRef.current?.click()}
                        className="text-primary-600 hover:text-primary-800 font-medium"
                      >
                        browse
                      </button>
                    </p>
                    <p className="mt-2 text-xs text-gray-500">
                      Supports .zip and .tar.gz files
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Step: Validating */}
          {step === 'validate' && (
            <div className="text-center py-8">
              <div className="animate-spin h-10 w-10 border-4 border-primary-500 border-t-transparent rounded-full mx-auto mb-4" />
              <p className="text-gray-600">Validating archive...</p>
            </div>
          )}

          {/* Step: Options */}
          {step === 'options' && validationResult && (
            <div className="space-y-6">
              {/* Summary */}
              <div className="bg-gray-50 rounded-lg p-4">
                <h4 className="text-sm font-medium text-gray-900 mb-3">Import Summary</h4>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-gray-500">Range Name:</span>
                    <span className="ml-2 font-medium">{validationResult.summary.range_name}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Networks:</span>
                    <span className="ml-2 font-medium">{validationResult.summary.networks_count}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">VMs:</span>
                    <span className="ml-2 font-medium">{validationResult.summary.vms_count}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Templates:</span>
                    <span className="ml-2 font-medium">
                      {validationResult.summary.templates_to_create} new,{' '}
                      {validationResult.summary.templates_existing} existing
                    </span>
                  </div>
                  {validationResult.summary.artifacts_count > 0 && (
                    <div>
                      <span className="text-gray-500">Artifacts:</span>
                      <span className="ml-2 font-medium">
                        {validationResult.summary.artifacts_count}
                      </span>
                    </div>
                  )}
                  {validationResult.summary.injects_count > 0 && (
                    <div>
                      <span className="text-gray-500">Injects:</span>
                      <span className="ml-2 font-medium">
                        {validationResult.summary.injects_count}
                      </span>
                    </div>
                  )}
                  {validationResult.summary.walkthrough_status && (
                    <div className="col-span-2">
                      <span className="text-gray-500">Student Walkthrough:</span>
                      <span className={`ml-2 font-medium ${
                        validationResult.summary.walkthrough_status === 'create_renamed'
                          ? 'text-amber-600'
                          : validationResult.summary.walkthrough_status === 'reuse_existing'
                          ? 'text-blue-600'
                          : 'text-green-600'
                      }`}>
                        {validationResult.summary.walkthrough_status === 'reuse_existing' && '✓ Will use existing (same content)'}
                        {validationResult.summary.walkthrough_status === 'create_new' && '+ Will create new'}
                        {validationResult.summary.walkthrough_status === 'create_renamed' && '⚠ Will create with new name (conflict)'}
                      </span>
                    </div>
                  )}
                </div>
              </div>

              {/* Warnings */}
              {validationResult.warnings.length > 0 && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                  <h4 className="text-sm font-medium text-amber-800 mb-2">Warnings</h4>
                  <ul className="text-sm text-amber-700 space-y-1">
                    {validationResult.warnings.map((warning, idx) => (
                      <li key={idx}>• {warning}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Conflicts */}
              {validationResult.conflicts.name_conflict && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Range Name (required - name already exists)
                  </label>
                  <input
                    type="text"
                    value={nameOverride}
                    onChange={(e) => setNameOverride(e.target.value)}
                    placeholder="Enter a new name for the range"
                    className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
                  />
                </div>
              )}

              {validationResult.conflicts.template_conflicts.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Template Conflict Resolution
                  </label>
                  <p className="text-xs text-gray-500 mb-2">
                    {validationResult.conflicts.template_conflicts.length} template(s) already exist
                  </p>
                  <select
                    value={templateConflictAction}
                    onChange={(e) =>
                      setTemplateConflictAction(
                        e.target.value as 'use_existing' | 'create_new' | 'skip'
                      )
                    }
                    className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
                  >
                    <option value="use_existing">Use existing templates</option>
                    <option value="create_new">Create new templates with suffix</option>
                    <option value="skip">Skip conflicting templates</option>
                  </select>
                </div>
              )}

              {/* Optional Skip */}
              <div className="space-y-3">
                <h4 className="text-sm font-medium text-gray-700">Import Options</h4>
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    checked={skipArtifacts}
                    onChange={(e) => setSkipArtifacts(e.target.checked)}
                    className="h-4 w-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                  />
                  <span className="ml-2 text-sm text-gray-600">Skip artifact import</span>
                </label>
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    checked={skipMsel}
                    onChange={(e) => setSkipMsel(e.target.checked)}
                    className="h-4 w-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                  />
                  <span className="ml-2 text-sm text-gray-600">Skip MSEL/injects import</span>
                </label>
                {validationResult?.summary.walkthrough_status && (
                  <label className="flex items-center">
                    <input
                      type="checkbox"
                      checked={skipWalkthrough}
                      onChange={(e) => setSkipWalkthrough(e.target.checked)}
                      className="h-4 w-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                    />
                    <span className="ml-2 text-sm text-gray-600">
                      Skip student walkthrough import
                      {validationResult.summary.walkthrough_status === 'create_renamed' && (
                        <span className="text-amber-600 ml-1">(will create duplicate otherwise)</span>
                      )}
                    </span>
                  </label>
                )}
              </div>
            </div>
          )}

          {/* Step: Importing */}
          {step === 'importing' && (
            <div className="text-center py-8">
              <div className="animate-spin h-10 w-10 border-4 border-primary-500 border-t-transparent rounded-full mx-auto mb-4" />
              <p className="text-gray-600">Importing range...</p>
            </div>
          )}

          {/* Step: Complete */}
          {step === 'complete' && importResult && (
            <div>
              {importResult.success ? (
                <div className="bg-green-50 border border-green-200 rounded-lg p-6 text-center">
                  <div className="text-4xl mb-2">✅</div>
                  <h4 className="text-lg font-medium text-green-800 mb-2">Import Successful</h4>
                  <p className="text-sm text-green-700 mb-4">
                    Range "{importResult.range_name}" has been imported.
                  </p>
                  <div className="grid grid-cols-2 gap-4 text-sm text-green-700 mb-4">
                    <div>Networks: {importResult.networks_created}</div>
                    <div>VMs: {importResult.vms_created}</div>
                    <div>Templates: {importResult.templates_created}</div>
                    <div>Artifacts: {importResult.artifacts_imported}</div>
                  </div>
                  {importResult.warnings.length > 0 && (
                    <div className="text-xs text-amber-600 mt-2">
                      {importResult.warnings.length} warning(s) - check console for details
                    </div>
                  )}
                </div>
              ) : (
                <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
                  <div className="text-4xl mb-2">❌</div>
                  <h4 className="text-lg font-medium text-red-800 mb-2">Import Failed</h4>
                  <ul className="text-sm text-red-700">
                    {importResult.errors.map((err, idx) => (
                      <li key={idx}>{err}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Actions */}
          <div className="flex justify-between mt-6 pt-4 border-t border-gray-200">
            <div>
              {step !== 'upload' && step !== 'complete' && !isLoading && (
                <button
                  type="button"
                  onClick={resetWizard}
                  className="px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900"
                >
                  ← Back to Upload
                </button>
              )}
            </div>
            <div className="flex space-x-3">
              <button
                type="button"
                onClick={step === 'complete' ? () => { resetWizard(); onClose(); } : onClose}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
              >
                {step === 'complete' ? 'Close' : 'Cancel'}
              </button>

              {step === 'upload' && (
                <button
                  onClick={handleValidate}
                  disabled={!file || isLoading}
                  className="px-4 py-2 text-sm font-medium text-white bg-primary-600 border border-transparent rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Validate
                </button>
              )}

              {step === 'options' && (
                <button
                  onClick={handleImport}
                  disabled={
                    isLoading ||
                    (validationResult?.conflicts.name_conflict && !nameOverride)
                  }
                  className="px-4 py-2 text-sm font-medium text-white bg-primary-600 border border-transparent rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Import
                </button>
              )}

              {step === 'complete' && importResult?.success && (
                <button
                  onClick={handleNavigateToRange}
                  className="px-4 py-2 text-sm font-medium text-white bg-primary-600 border border-transparent rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
                >
                  Go to Range
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
