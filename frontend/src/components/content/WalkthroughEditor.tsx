// frontend/src/components/content/WalkthroughEditor.tsx
import { useState } from 'react'
import {
  Plus,
  Trash2,
  ChevronDown,
  ChevronRight,
  GripVertical,
  Code,
  Eye,
  AlertCircle,
} from 'lucide-react'
import clsx from 'clsx'
import type { Walkthrough, WalkthroughPhase, WalkthroughStep } from '../../types'
import yaml from 'js-yaml'

interface WalkthroughEditorProps {
  value: Walkthrough | null
  onChange: (data: Walkthrough) => void
}

const DEFAULT_WALKTHROUGH: Walkthrough = {
  title: '',
  phases: [],
}

export function WalkthroughEditor({ value, onChange }: WalkthroughEditorProps) {
  const [mode, setMode] = useState<'visual' | 'yaml'>('visual')
  const [yamlText, setYamlText] = useState('')
  const [yamlError, setYamlError] = useState<string | null>(null)
  const [expandedPhases, setExpandedPhases] = useState<Set<string>>(new Set())

  const data = value || DEFAULT_WALKTHROUGH

  // Sync YAML when switching to YAML mode
  const handleModeChange = (newMode: 'visual' | 'yaml') => {
    if (newMode === 'yaml') {
      setYamlText(yaml.dump(data, { lineWidth: -1, quotingType: '"' }))
      setYamlError(null)
    }
    setMode(newMode)
  }

  // Parse YAML and update
  const handleYamlChange = (text: string) => {
    setYamlText(text)
    try {
      const parsed = yaml.load(text) as Walkthrough
      if (parsed && typeof parsed === 'object') {
        setYamlError(null)
        onChange(parsed)
      }
    } catch (err) {
      setYamlError(err instanceof Error ? err.message : 'Invalid YAML')
    }
  }

  // Visual mode handlers
  const updateTitle = (title: string) => {
    onChange({ ...data, title })
  }

  const addPhase = () => {
    const newPhase: WalkthroughPhase = {
      id: `phase${data.phases.length + 1}`,
      name: 'New Phase',
      steps: [],
    }
    onChange({ ...data, phases: [...data.phases, newPhase] })
    setExpandedPhases(prev => new Set([...prev, newPhase.id]))
  }

  const updatePhase = (index: number, updates: Partial<WalkthroughPhase>) => {
    const phases = [...data.phases]
    phases[index] = { ...phases[index], ...updates }
    onChange({ ...data, phases })
  }

  const deletePhase = (index: number) => {
    const phases = data.phases.filter((_, i) => i !== index)
    onChange({ ...data, phases })
  }

  const addStep = (phaseIndex: number) => {
    const phases = [...data.phases]
    const phase = phases[phaseIndex]
    const newStep: WalkthroughStep = {
      id: `step${phaseIndex + 1}_${phase.steps.length + 1}`,
      title: 'New Step',
      content: '',
      vm: '',
    }
    phases[phaseIndex] = { ...phase, steps: [...phase.steps, newStep] }
    onChange({ ...data, phases })
  }

  const updateStep = (phaseIndex: number, stepIndex: number, updates: Partial<WalkthroughStep>) => {
    const phases = [...data.phases]
    const steps = [...phases[phaseIndex].steps]
    steps[stepIndex] = { ...steps[stepIndex], ...updates }
    phases[phaseIndex] = { ...phases[phaseIndex], steps }
    onChange({ ...data, phases })
  }

  const deleteStep = (phaseIndex: number, stepIndex: number) => {
    const phases = [...data.phases]
    phases[phaseIndex] = {
      ...phases[phaseIndex],
      steps: phases[phaseIndex].steps.filter((_, i) => i !== stepIndex),
    }
    onChange({ ...data, phases })
  }

  const togglePhase = (phaseId: string) => {
    setExpandedPhases(prev => {
      const next = new Set(prev)
      if (next.has(phaseId)) {
        next.delete(phaseId)
      } else {
        next.add(phaseId)
      }
      return next
    })
  }

  return (
    <div className="border rounded-lg overflow-hidden">
      {/* Mode Toggle */}
      <div className="flex items-center justify-between bg-gray-50 px-4 py-2 border-b">
        <div className="flex gap-2">
          <button
            onClick={() => handleModeChange('visual')}
            className={clsx(
              'px-3 py-1.5 text-sm font-medium rounded flex items-center gap-2',
              mode === 'visual'
                ? 'bg-white shadow text-gray-900'
                : 'text-gray-600 hover:text-gray-900'
            )}
          >
            <Eye className="w-4 h-4" />
            Visual
          </button>
          <button
            onClick={() => handleModeChange('yaml')}
            className={clsx(
              'px-3 py-1.5 text-sm font-medium rounded flex items-center gap-2',
              mode === 'yaml'
                ? 'bg-white shadow text-gray-900'
                : 'text-gray-600 hover:text-gray-900'
            )}
          >
            <Code className="w-4 h-4" />
            YAML
          </button>
        </div>
        <span className="text-xs text-gray-500">
          {data.phases.length} phases, {data.phases.reduce((sum, p) => sum + p.steps.length, 0)} steps
        </span>
      </div>

      {mode === 'visual' ? (
        <div className="p-4 space-y-4">
          {/* Title */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Walkthrough Title
            </label>
            <input
              type="text"
              value={data.title}
              onChange={(e) => updateTitle(e.target.value)}
              placeholder="e.g., Red Team Training Lab"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            />
          </div>

          {/* Phases */}
          <div className="space-y-3">
            {data.phases.map((phase, phaseIndex) => (
              <PhaseEditor
                key={phase.id}
                phase={phase}
                expanded={expandedPhases.has(phase.id)}
                onToggle={() => togglePhase(phase.id)}
                onUpdate={(updates) => updatePhase(phaseIndex, updates)}
                onDelete={() => deletePhase(phaseIndex)}
                onAddStep={() => addStep(phaseIndex)}
                onUpdateStep={(stepIndex, updates) => updateStep(phaseIndex, stepIndex, updates)}
                onDeleteStep={(stepIndex) => deleteStep(phaseIndex, stepIndex)}
              />
            ))}
          </div>

          {/* Add Phase Button */}
          <button
            onClick={addPhase}
            className="w-full py-2 border-2 border-dashed border-gray-300 rounded-lg text-gray-500 hover:border-primary-400 hover:text-primary-600 flex items-center justify-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Add Phase
          </button>
        </div>
      ) : (
        <div className="p-4">
          {yamlError && (
            <div className="mb-3 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700 text-sm">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              {yamlError}
            </div>
          )}
          <textarea
            value={yamlText}
            onChange={(e) => handleYamlChange(e.target.value)}
            className="w-full h-96 font-mono text-sm border border-gray-300 rounded-lg p-3 focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            placeholder="# Walkthrough structure in YAML format"
          />
          <p className="mt-2 text-xs text-gray-500">
            Edit the walkthrough structure directly in YAML format. Changes are applied automatically when valid.
          </p>
        </div>
      )}
    </div>
  )
}

// Phase Editor Component
interface PhaseEditorProps {
  phase: WalkthroughPhase
  expanded: boolean
  onToggle: () => void
  onUpdate: (updates: Partial<WalkthroughPhase>) => void
  onDelete: () => void
  onAddStep: () => void
  onUpdateStep: (stepIndex: number, updates: Partial<WalkthroughStep>) => void
  onDeleteStep: (stepIndex: number) => void
}

function PhaseEditor({
  phase,
  expanded,
  onToggle,
  onUpdate,
  onDelete,
  onAddStep,
  onUpdateStep,
  onDeleteStep,
}: PhaseEditorProps) {
  return (
    <div className="border rounded-lg bg-white">
      {/* Phase Header */}
      <div className="flex items-center gap-2 p-3 bg-gray-50 border-b">
        <GripVertical className="w-4 h-4 text-gray-400 cursor-move" />
        <button onClick={onToggle} className="p-1 hover:bg-gray-200 rounded">
          {expanded ? (
            <ChevronDown className="w-4 h-4 text-gray-500" />
          ) : (
            <ChevronRight className="w-4 h-4 text-gray-500" />
          )}
        </button>
        <input
          value={phase.name}
          onChange={(e) => onUpdate({ name: e.target.value })}
          className="flex-1 bg-transparent font-medium text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 rounded px-2 py-1"
          placeholder="Phase name"
        />
        <span className="text-xs text-gray-500">{phase.steps.length} steps</span>
        <button
          onClick={onDelete}
          className="p-1.5 text-red-500 hover:bg-red-50 rounded"
          title="Delete phase"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>

      {/* Phase Content */}
      {expanded && (
        <div className="p-3 space-y-3">
          {phase.steps.map((step, stepIndex) => (
            <StepEditor
              key={step.id}
              step={step}
              onUpdate={(updates) => onUpdateStep(stepIndex, updates)}
              onDelete={() => onDeleteStep(stepIndex)}
            />
          ))}

          <button
            onClick={onAddStep}
            className="w-full py-2 text-sm text-primary-600 hover:bg-primary-50 rounded-lg flex items-center justify-center gap-1"
          >
            <Plus className="w-4 h-4" />
            Add Step
          </button>
        </div>
      )}
    </div>
  )
}

// Step Editor Component
interface StepEditorProps {
  step: WalkthroughStep
  onUpdate: (updates: Partial<WalkthroughStep>) => void
  onDelete: () => void
}

function StepEditor({ step, onUpdate, onDelete }: StepEditorProps) {
  const [showContent, setShowContent] = useState(false)

  return (
    <div className="border rounded-lg p-3 bg-gray-50 space-y-2">
      {/* Step Header */}
      <div className="flex items-center gap-2">
        <GripVertical className="w-4 h-4 text-gray-400 cursor-move" />
        <input
          value={step.title}
          onChange={(e) => onUpdate({ title: e.target.value })}
          className="flex-1 bg-white border border-gray-300 rounded px-2 py-1 text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          placeholder="Step title"
        />
        <select
          value={step.vm || ''}
          onChange={(e) => onUpdate({ vm: e.target.value || undefined })}
          className="border border-gray-300 rounded px-2 py-1 text-sm bg-white"
        >
          <option value="">No VM</option>
          <option value="kali">kali</option>
          <option value="windows">windows</option>
          <option value="ubuntu">ubuntu</option>
        </select>
        <button
          onClick={() => setShowContent(!showContent)}
          className="p-1.5 text-gray-500 hover:bg-gray-200 rounded"
          title={showContent ? 'Hide content' : 'Edit content'}
        >
          {showContent ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </button>
        <button
          onClick={onDelete}
          className="p-1.5 text-red-500 hover:bg-red-50 rounded"
          title="Delete step"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>

      {/* Step Content */}
      {showContent && (
        <div>
          <textarea
            value={step.content}
            onChange={(e) => onUpdate({ content: e.target.value })}
            className="w-full h-32 text-sm font-mono border border-gray-300 rounded p-2 focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            placeholder="Step content in Markdown..."
          />
          <p className="text-xs text-gray-500 mt-1">
            Supports Markdown formatting: **bold**, `code`, ```code blocks```
          </p>
        </div>
      )}
    </div>
  )
}

export default WalkthroughEditor
