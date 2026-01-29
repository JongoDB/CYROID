// frontend/src/components/files/CreateFileModal.tsx
import { useState } from 'react';
import { FileCode, Loader2 } from 'lucide-react';
import clsx from 'clsx';
import { filesApi } from '../../services/api';
import { toast } from '../../stores/toastStore';
import { Modal, ModalBody, ModalFooter } from '../common/Modal';

interface CreateFileModalProps {
  isOpen: boolean;
  basePath: string;
  onClose: () => void;
  onCreated: (path: string) => void;
}

type FileType = 'dockerfile' | 'yaml' | 'shell' | 'markdown' | 'json' | 'text';

interface FileTemplate {
  type: FileType;
  label: string;
  defaultName: string;
  content: string;
}

const FILE_TEMPLATES: FileTemplate[] = [
  {
    type: 'dockerfile',
    label: 'Dockerfile',
    defaultName: 'Dockerfile',
    content: `FROM ubuntu:22.04

LABEL maintainer="your-email@example.com"
LABEL description="Description of this image"

# Install dependencies
RUN apt-get update && apt-get install -y \\
    package1 \\
    package2 \\
    && rm -rf /var/lib/apt/lists/*

# Copy configuration files
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set working directory
WORKDIR /app

# Expose ports
EXPOSE 22 80

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]
`,
  },
  {
    type: 'shell',
    label: 'Shell Script',
    defaultName: 'script.sh',
    content: `#!/bin/bash
set -e

# Description: What this script does
# Usage: ./script.sh [options]

main() {
    echo "Starting..."
    # Your code here
}

main "$@"
`,
  },
  {
    type: 'yaml',
    label: 'YAML Config',
    defaultName: 'config.yaml',
    content: `# Configuration file
name: example
version: "1.0"

settings:
  enabled: true
  timeout: 30

items:
  - name: item1
    value: 100
  - name: item2
    value: 200
`,
  },
  {
    type: 'yaml',
    label: 'Training Scenario',
    defaultName: 'scenario.yaml',
    content: `id: new-scenario
name: "New Training Scenario"
description: "Brief description of this scenario"
category: red-team  # red-team, blue-team, purple-team, insider-threat
difficulty: intermediate  # beginner, intermediate, advanced, expert
duration_hours: 4

objectives:
  - "Primary learning objective"
  - "Secondary learning objective"

required_roles:
  - role: attacker
    description: "Kali Linux attack platform"
  - role: target
    description: "Target system to compromise"

events:
  - id: event-1
    time_offset: "00:00:00"
    type: INJECT
    title: "Initial Access"
    description: "Begin the attack scenario"
    target_role: attacker
`,
  },
  {
    type: 'json',
    label: 'JSON Config',
    defaultName: 'config.json',
    content: `{
  "name": "example",
  "version": "1.0.0",
  "settings": {
    "enabled": true,
    "timeout": 30
  },
  "items": [
    { "name": "item1", "value": 100 },
    { "name": "item2", "value": 200 }
  ]
}
`,
  },
  {
    type: 'markdown',
    label: 'Markdown (README)',
    defaultName: 'README.md',
    content: `# Project Name

Brief description of this project.

## Features

- Feature 1
- Feature 2

## Usage

\`\`\`bash
./script.sh
\`\`\`

## Configuration

Describe configuration options here.

## License

MIT
`,
  },
  {
    type: 'text',
    label: 'Empty Text File',
    defaultName: 'file.txt',
    content: '',
  },
];

export function CreateFileModal({
  isOpen,
  basePath,
  onClose,
  onCreated,
}: CreateFileModalProps) {
  const [selectedTemplate, setSelectedTemplate] = useState<FileTemplate>(FILE_TEMPLATES[0]);
  const [fileName, setFileName] = useState(FILE_TEMPLATES[0].defaultName);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleTemplateSelect = (template: FileTemplate) => {
    setSelectedTemplate(template);
    setFileName(template.defaultName);
    setError(null);
  };

  const handleCreate = async () => {
    if (!fileName.trim()) {
      setError('File name is required');
      return;
    }

    // Basic validation
    if (fileName.includes('/') || fileName.includes('\\')) {
      setError('File name cannot contain path separators');
      return;
    }

    const fullPath = `${basePath}/${fileName}`.replace(/\/+/g, '/');

    setCreating(true);
    setError(null);
    try {
      await filesApi.createFile(fullPath, selectedTemplate.content);
      toast.success(`Created ${fileName}`);
      onCreated(fullPath);
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'Failed to create file';
      setError(detail);
      toast.error(detail);
    } finally {
      setCreating(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Create New File"
      size="lg"
      description="Select a file template and enter a file name to create a new file"
    >
      <ModalBody>
        {/* Template Selection */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            File Template
          </label>
          <div className="grid grid-cols-2 gap-2">
            {FILE_TEMPLATES.map((template, i) => (
              <button
                key={i}
                onClick={() => handleTemplateSelect(template)}
                className={clsx(
                  'flex items-center px-3 py-2 text-sm rounded-lg border transition-colors text-left',
                  selectedTemplate === template
                    ? 'border-primary-500 bg-primary-50 text-primary-700'
                    : 'border-gray-200 hover:bg-gray-50 text-gray-700'
                )}
              >
                <FileCode className="h-4 w-4 mr-2 flex-shrink-0" />
                {template.label}
              </button>
            ))}
          </div>
        </div>

        {/* File Name */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            File Name
          </label>
          <input
            type="text"
            value={fileName}
            onChange={(e) => {
              setFileName(e.target.value);
              setError(null);
            }}
            className={clsx(
              'w-full px-3 py-2 border rounded-lg text-sm',
              error
                ? 'border-red-300 focus:ring-red-500 focus:border-red-500'
                : 'border-gray-300 focus:ring-primary-500 focus:border-primary-500'
            )}
            placeholder="filename.ext"
          />
          {error && <p className="mt-1 text-sm text-red-600">{error}</p>}
        </div>

        {/* Path Preview */}
        <div className="p-3 bg-gray-50 rounded-lg">
          <p className="text-xs text-gray-500 mb-1">Will create:</p>
          <code className="text-sm text-gray-700">
            {basePath}/{fileName}
          </code>
        </div>
      </ModalBody>

      <ModalFooter>
        <button
          onClick={onClose}
          className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
        >
          Cancel
        </button>
        <button
          onClick={handleCreate}
          disabled={creating || !fileName.trim()}
          className={clsx(
            'inline-flex items-center px-4 py-2 text-sm font-medium rounded-md',
            creating || !fileName.trim()
              ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
              : 'bg-primary-600 text-white hover:bg-primary-700'
          )}
        >
          {creating && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
          Create File
        </button>
      </ModalFooter>
    </Modal>
  );
}
