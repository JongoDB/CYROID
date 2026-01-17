// frontend/src/components/walkthrough/StepContent.tsx
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { ExternalLink } from 'lucide-react'
import { WalkthroughStep } from '../../types'

interface StepContentProps {
  step: WalkthroughStep
  onOpenVM?: (vmHostname: string) => void
}

export function StepContent({ step, onOpenVM }: StepContentProps) {
  return (
    <div className="p-4">
      <h2 className="text-lg font-semibold text-white mb-4">{step.title}</h2>

      <div className="prose prose-invert prose-sm max-w-none">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            code({ inline, className, children, ...props }: { inline?: boolean; className?: string; children?: React.ReactNode }) {
              return !inline ? (
                <pre className="bg-gray-900 rounded-lg p-3 overflow-x-auto">
                  <code className={className} {...props}>
                    {children}
                  </code>
                </pre>
              ) : (
                <code className="bg-gray-700 px-1 rounded" {...props}>
                  {children}
                </code>
              )
            },
            blockquote({ children }: { children?: React.ReactNode }) {
              return (
                <blockquote className="border-l-4 border-blue-500 pl-4 py-1 my-3 bg-blue-900/20 rounded-r">
                  {children}
                </blockquote>
              )
            },
          }}
        >
          {step.content || ''}
        </ReactMarkdown>
      </div>

      {step.vm && onOpenVM && (
        <button
          onClick={() => onOpenVM(step.vm!)}
          className="mt-4 inline-flex items-center gap-2 px-3 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          <span>Open {step.vm}</span>
          <ExternalLink className="w-4 h-4" />
        </button>
      )}
    </div>
  )
}
