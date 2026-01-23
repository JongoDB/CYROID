// frontend/src/components/walkthrough/WalkthroughPanel.tsx
import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { ChevronLeft, ChevronRight, BookOpen, X, Check } from 'lucide-react'
import { Walkthrough } from '../../types'
import { walkthroughApi } from '../../services/api'
import { PhaseNav } from './PhaseNav'
import { StepList } from './StepList'
import { StepContent } from './StepContent'
import { ProgressBar } from './ProgressBar'

interface WalkthroughPanelProps {
  rangeId: string
  walkthrough: Walkthrough
  onOpenVM: (vmHostname: string) => void
  onCollapse?: () => void
}

const STORAGE_KEY_PREFIX = 'cyroid_walkthrough_'
const SYNC_DEBOUNCE_MS = 3000 // 3 seconds after last change

export function WalkthroughPanel({ rangeId, walkthrough, onOpenVM, onCollapse }: WalkthroughPanelProps) {
  const [currentPhase, setCurrentPhase] = useState(walkthrough.phases[0]?.id || '')
  const [currentStep, setCurrentStep] = useState(walkthrough.phases[0]?.steps[0]?.id || '')
  const [completedSteps, setCompletedSteps] = useState<Set<string>>(new Set())
  const [isDirty, setIsDirty] = useState(false)
  const [isSyncing, setIsSyncing] = useState(false)
  const contentRef = useRef<HTMLDivElement>(null)

  // Scroll to top when step changes
  useEffect(() => {
    if (contentRef.current) {
      contentRef.current.scrollTo({ top: 0, behavior: 'instant' })
    }
  }, [currentStep])

  // Load from localStorage on mount
  useEffect(() => {
    const storageKey = `${STORAGE_KEY_PREFIX}${rangeId}`
    const saved = localStorage.getItem(storageKey)
    if (saved) {
      try {
        const data = JSON.parse(saved)
        setCompletedSteps(new Set(data.completedSteps || []))
        if (data.currentPhase) setCurrentPhase(data.currentPhase)
        if (data.currentStep) setCurrentStep(data.currentStep)
      } catch (e) {
        console.error('Failed to parse saved progress:', e)
      }
    }

    // Load from server
    walkthroughApi.getProgress(rangeId).then(res => {
      if (res.data) {
        setCompletedSteps(new Set(res.data.completed_steps || []))
        if (res.data.current_phase) setCurrentPhase(res.data.current_phase)
        if (res.data.current_step) setCurrentStep(res.data.current_step)
      }
    }).catch(() => {})
  }, [rangeId])

  // Save to localStorage when state changes
  useEffect(() => {
    const storageKey = `${STORAGE_KEY_PREFIX}${rangeId}`
    localStorage.setItem(storageKey, JSON.stringify({
      completedSteps: Array.from(completedSteps),
      currentPhase,
      currentStep,
    }))
  }, [rangeId, completedSteps, currentPhase, currentStep])

  const syncToServer = useCallback(async () => {
    setIsSyncing(true)
    try {
      await walkthroughApi.updateProgress(rangeId, {
        completed_steps: Array.from(completedSteps),
        current_phase: currentPhase,
        current_step: currentStep,
      })
      setIsDirty(false)
    } catch (e) {
      console.error('Failed to sync progress:', e)
    } finally {
      setIsSyncing(false)
    }
  }, [rangeId, completedSteps, currentPhase, currentStep])

  // Auto-sync to server with debounce (saves 3 seconds after last change)
  useEffect(() => {
    if (!isDirty) return
    const timer = setTimeout(() => {
      syncToServer()
    }, SYNC_DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [isDirty, syncToServer])

  const currentPhaseData = walkthrough.phases.find(p => p.id === currentPhase)
  const currentStepData = currentPhaseData?.steps.find(s => s.id === currentStep)

  const totalSteps = useMemo(() =>
    walkthrough.phases.reduce((acc, p) => acc + p.steps.length, 0),
    [walkthrough]
  )

  const handleToggleComplete = (stepId: string) => {
    setCompletedSteps(prev => {
      const next = new Set(prev)
      if (next.has(stepId)) {
        next.delete(stepId)
      } else {
        next.add(stepId)
      }
      return next
    })
    setIsDirty(true)
  }

  const handleStepChange = (stepId: string) => {
    setCurrentStep(stepId)
    setIsDirty(true)
  }

  const handlePhaseChange = (phaseId: string) => {
    setCurrentPhase(phaseId)
    const phase = walkthrough.phases.find(p => p.id === phaseId)
    if (phase?.steps[0]) {
      setCurrentStep(phase.steps[0].id)
    }
    setIsDirty(true)
  }

  const allSteps = useMemo(() =>
    walkthrough.phases.flatMap(p => p.steps.map(s => ({ ...s, phaseId: p.id }))),
    [walkthrough]
  )

  const currentStepIndex = useMemo(() =>
    allSteps.findIndex(s => s.id === currentStep),
    [allSteps, currentStep]
  )

  const isLastStep = currentStepIndex === allSteps.length - 1
  const isFirstStep = currentStepIndex === 0

  const navigateStep = (direction: 'prev' | 'next') => {
    const newIndex = direction === 'next' ? currentStepIndex + 1 : currentStepIndex - 1

    // Mark current step as complete when moving forward (or finishing)
    if (direction === 'next' && currentStep) {
      setCompletedSteps(prev => {
        const next = new Set(prev)
        next.add(currentStep)
        return next
      })
      setIsDirty(true)
    }

    // Navigate to new step if there is one
    if (newIndex >= 0 && newIndex < allSteps.length) {
      const newStep = allSteps[newIndex]
      if (newStep.phaseId !== currentPhase) {
        setCurrentPhase(newStep.phaseId)
      }
      setCurrentStep(newStep.id)
      setIsDirty(true)
    }
  }

  return (
    <div className="h-full flex flex-col bg-gray-800 border-r border-gray-700">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-gray-800 border-b border-gray-700">
        <div className="flex items-center gap-2">
          <BookOpen className="w-5 h-5 text-blue-400" />
          <h1 className="font-semibold text-white">{walkthrough.title}</h1>
        </div>
        {onCollapse && (
          <button
            onClick={onCollapse}
            className="p-1 text-gray-400 hover:text-white"
          >
            <X className="w-5 h-5" />
          </button>
        )}
      </div>

      {/* Progress */}
      <ProgressBar
        completed={completedSteps.size}
        total={totalSteps}
        isDirty={isDirty}
        isSyncing={isSyncing}
        onSave={syncToServer}
      />

      {/* Phase Navigation */}
      <PhaseNav
        phases={walkthrough.phases}
        currentPhase={currentPhase}
        onPhaseChange={handlePhaseChange}
        completedSteps={completedSteps}
      />

      {/* Step List */}
      {currentPhaseData && (
        <div className="border-b border-gray-700">
          <StepList
            steps={currentPhaseData.steps}
            currentStep={currentStep}
            completedSteps={completedSteps}
            onStepChange={handleStepChange}
            onToggleComplete={handleToggleComplete}
          />
        </div>
      )}

      {/* Step Content */}
      <div ref={contentRef} className="flex-1 overflow-y-auto">
        {currentStepData && (
          <StepContent step={currentStepData} onOpenVM={onOpenVM} />
        )}
      </div>

      {/* Navigation */}
      <div className="flex items-center justify-between px-4 py-3 bg-gray-800 border-t border-gray-700">
        <button
          onClick={() => navigateStep('prev')}
          disabled={isFirstStep}
          className={`flex items-center gap-1 px-3 py-1.5 text-sm rounded ${
            isFirstStep
              ? 'bg-gray-800 text-gray-500 cursor-not-allowed'
              : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
          }`}
        >
          <ChevronLeft className="w-4 h-4" />
          Prev
        </button>
        <button
          onClick={() => navigateStep('next')}
          className={`flex items-center gap-1 px-3 py-1.5 text-sm rounded ${
            isLastStep
              ? 'bg-green-600 text-white hover:bg-green-700'
              : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
          }`}
        >
          {isLastStep ? (
            <>
              Finish
              <Check className="w-4 h-4" />
            </>
          ) : (
            <>
              Next
              <ChevronRight className="w-4 h-4" />
            </>
          )}
        </button>
      </div>
    </div>
  )
}
