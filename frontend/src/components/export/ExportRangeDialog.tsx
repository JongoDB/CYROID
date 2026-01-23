// frontend/src/components/export/ExportRangeDialog.tsx
import { useState, useEffect, useCallback } from 'react'
import { rangesApi } from '../../services/api'
import type { ExportRequest, ExportJobStatus } from '../../types'

interface ExportRangeDialogProps {
  isOpen: boolean
  onClose: () => void
  rangeId: string
  rangeName: string
}

export default function ExportRangeDialog({
  isOpen,
  onClose,
  rangeId,
  rangeName,
}: ExportRangeDialogProps) {
  // Export options
  const [includeTemplates, setIncludeTemplates] = useState(true)
  const [includeMsel, setIncludeMsel] = useState(true)
  const [includeWalkthrough, setIncludeWalkthrough] = useState(true)
  const [includeArtifacts, setIncludeArtifacts] = useState(true)
  const [includeSnapshots, setIncludeSnapshots] = useState(false)
  const [includeDockerImages, setIncludeDockerImages] = useState(false)
  const [encryptPasswords, setEncryptPasswords] = useState(true)

  // State
  const [isExporting, setIsExporting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [jobStatus, setJobStatus] = useState<ExportJobStatus | null>(null)

  // Poll job status for offline exports
  useEffect(() => {
    if (!jobStatus || jobStatus.status === 'completed' || jobStatus.status === 'failed') {
      return
    }

    const interval = setInterval(async () => {
      try {
        const response = await rangesApi.getExportJobStatus(jobStatus.job_id)
        setJobStatus(response.data)

        if (response.data.status === 'completed' || response.data.status === 'failed') {
          clearInterval(interval)
        }
      } catch (err) {
        console.error('Failed to get export job status:', err)
      }
    }, 2000)

    return () => clearInterval(interval)
  }, [jobStatus])

  const handleExport = useCallback(async () => {
    setIsExporting(true)
    setError(null)
    setJobStatus(null)

    const options: ExportRequest = {
      include_templates: includeTemplates,
      include_msel: includeMsel,
      include_walkthrough: includeWalkthrough,
      include_artifacts: includeArtifacts,
      include_snapshots: includeSnapshots,
      include_docker_images: includeDockerImages,
      encrypt_passwords: encryptPasswords,
    }

    try {
      if (includeDockerImages) {
        // Offline export - get job status and poll
        const response = await rangesApi.exportFull(rangeId, options)
        if ('data' in response && response.data) {
          setJobStatus(response.data as ExportJobStatus)
        }
      } else {
        // Online export - download file directly
        const response = await rangesApi.exportFull(rangeId, options)
        if ('data' in response && response.data instanceof Blob) {
          // Create download link
          const blob = response.data as Blob
          const url = window.URL.createObjectURL(blob)
          const a = document.createElement('a')
          a.href = url
          a.download = `range-export-${rangeName.replace(/[^a-zA-Z0-9]/g, '_')}.zip`
          document.body.appendChild(a)
          a.click()
          window.URL.revokeObjectURL(url)
          document.body.removeChild(a)
          onClose()
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed')
    } finally {
      setIsExporting(false)
    }
  }, [
    rangeId,
    rangeName,
    includeTemplates,
    includeMsel,
    includeWalkthrough,
    includeArtifacts,
    includeSnapshots,
    includeDockerImages,
    encryptPasswords,
    onClose,
  ])

  const handleDownloadComplete = useCallback(async () => {
    if (!jobStatus?.job_id) return

    try {
      // For large files (like offline exports with Docker images), use direct URL download
      // instead of blob to avoid memory issues with multi-GB files
      const token = localStorage.getItem('token')
      const downloadUrl = `/api/v1/ranges/export/jobs/${jobStatus.job_id}/download`

      // Create a hidden link and trigger download directly
      // The browser will handle streaming the large file
      const a = document.createElement('a')
      a.href = downloadUrl + (token ? `?token=${token}` : '')
      a.download = `range-export-${rangeName.replace(/[^a-zA-Z0-9]/g, '_')}-offline.tar.gz`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Download failed')
    }
  }, [jobStatus, rangeName, onClose])

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
          onClick={onClose}
        />

        {/* Modal */}
        <div className="relative bg-white rounded-lg shadow-xl max-w-lg w-full p-6">
          <div className="mb-6">
            <h3 className="text-lg font-semibold text-gray-900">Export Range</h3>
            <p className="mt-1 text-sm text-gray-500">
              Export "{rangeName}" with all configuration for backup or transfer.
            </p>
          </div>

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

          {/* Job Progress */}
          {jobStatus && jobStatus.status !== 'completed' && jobStatus.status !== 'failed' && (
            <div className="mb-6">
              <div className="flex justify-between text-sm text-gray-600 mb-2">
                <span>{jobStatus.current_step}</span>
                <span>{jobStatus.progress_percent}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-primary-600 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${jobStatus.progress_percent}%` }}
                />
              </div>
            </div>
          )}

          {/* Completed Job */}
          {jobStatus?.status === 'completed' && (
            <div className="mb-6 bg-green-50 border border-green-200 rounded-lg p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-green-800 font-medium">Export Complete</p>
                  {jobStatus.file_size_bytes && (
                    <p className="text-sm text-green-600">
                      Size: {formatBytes(jobStatus.file_size_bytes)}
                    </p>
                  )}
                </div>
                <button
                  onClick={handleDownloadComplete}
                  className="px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-md hover:bg-green-700"
                >
                  Download
                </button>
              </div>
            </div>
          )}

          {/* Failed Job */}
          {jobStatus?.status === 'failed' && (
            <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4">
              <p className="text-red-800 font-medium">Export Failed</p>
              <p className="text-sm text-red-600">{jobStatus.error_message}</p>
            </div>
          )}

          {/* Export Options */}
          {!jobStatus && (
            <div className="space-y-4">
              <h4 className="text-sm font-medium text-gray-700">Include in Export</h4>

              <div className="space-y-3">
                <label className="flex items-start">
                  <input
                    type="checkbox"
                    checked={includeTemplates}
                    onChange={(e) => setIncludeTemplates(e.target.checked)}
                    className="mt-1 h-4 w-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                  />
                  <div className="ml-3">
                    <span className="text-sm font-medium text-gray-900">VM Templates</span>
                    <p className="text-xs text-gray-500">Include template definitions used by VMs</p>
                  </div>
                </label>

                <label className="flex items-start">
                  <input
                    type="checkbox"
                    checked={includeMsel}
                    onChange={(e) => setIncludeMsel(e.target.checked)}
                    className="mt-1 h-4 w-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                  />
                  <div className="ml-3">
                    <span className="text-sm font-medium text-gray-900">MSEL & Injects</span>
                    <p className="text-xs text-gray-500">Include scenario timeline and events</p>
                  </div>
                </label>

                <label className="flex items-start">
                  <input
                    type="checkbox"
                    checked={includeWalkthrough}
                    onChange={(e) => setIncludeWalkthrough(e.target.checked)}
                    className="mt-1 h-4 w-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                  />
                  <div className="ml-3">
                    <span className="text-sm font-medium text-gray-900">Walkthrough / Student Guide</span>
                    <p className="text-xs text-gray-500">Include linked Content Library walkthrough</p>
                  </div>
                </label>

                <label className="flex items-start">
                  <input
                    type="checkbox"
                    checked={includeArtifacts}
                    onChange={(e) => setIncludeArtifacts(e.target.checked)}
                    className="mt-1 h-4 w-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                  />
                  <div className="ml-3">
                    <span className="text-sm font-medium text-gray-900">Artifacts</span>
                    <p className="text-xs text-gray-500">Include files and their VM placements</p>
                  </div>
                </label>

                <label className="flex items-start">
                  <input
                    type="checkbox"
                    checked={includeSnapshots}
                    onChange={(e) => setIncludeSnapshots(e.target.checked)}
                    className="mt-1 h-4 w-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                  />
                  <div className="ml-3">
                    <span className="text-sm font-medium text-gray-900">Snapshots</span>
                    <p className="text-xs text-gray-500">Include VM snapshot metadata</p>
                  </div>
                </label>

                <div className="border-t border-gray-200 pt-3 mt-3">
                  <label className="flex items-start">
                    <input
                      type="checkbox"
                      checked={includeDockerImages}
                      onChange={(e) => setIncludeDockerImages(e.target.checked)}
                      className="mt-1 h-4 w-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                    />
                    <div className="ml-3">
                      <span className="text-sm font-medium text-gray-900">
                        Docker Images (Offline Mode)
                      </span>
                      <p className="text-xs text-gray-500">
                        Include all Docker images for air-gapped deployment
                      </p>
                      {includeDockerImages && (
                        <p className="text-xs text-amber-600 mt-1">
                          Warning: This may take 10-30 minutes and create a 10-50GB archive
                        </p>
                      )}
                    </div>
                  </label>
                </div>

                <div className="border-t border-gray-200 pt-3 mt-3">
                  <label className="flex items-start">
                    <input
                      type="checkbox"
                      checked={encryptPasswords}
                      onChange={(e) => setEncryptPasswords(e.target.checked)}
                      className="mt-1 h-4 w-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                    />
                    <div className="ml-3">
                      <span className="text-sm font-medium text-gray-900">Encrypt Passwords</span>
                      <p className="text-xs text-gray-500">
                        Encrypt VM credentials in the export file
                      </p>
                    </div>
                  </label>
                </div>
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex justify-end space-x-3 mt-6 pt-4 border-t border-gray-200">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
            >
              {jobStatus?.status === 'completed' ? 'Close' : 'Cancel'}
            </button>
            {!jobStatus && (
              <button
                onClick={handleExport}
                disabled={isExporting}
                className="px-4 py-2 text-sm font-medium text-white bg-primary-600 border border-transparent rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isExporting ? 'Exporting...' : includeDockerImages ? 'Start Export' : 'Export'}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
