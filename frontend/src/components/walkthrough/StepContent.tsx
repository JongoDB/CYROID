// frontend/src/components/walkthrough/StepContent.tsx
import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { ExternalLink, Copy, Check } from 'lucide-react'
import { WalkthroughStep } from '../../types'
import { useVmClipboardOptional } from '../../contexts'

interface StepContentProps {
  step: WalkthroughStep
  onOpenVM?: (vmHostname: string) => void
}

// Code block with copy button - used for <pre> elements (fenced code blocks)
function PreBlock({ children }: { children?: React.ReactNode }) {
  const [copied, setCopied] = useState(false)
  const vmClipboard = useVmClipboardOptional()

  const handleCopy = () => {
    // Extract text content from children
    const text = extractText(children)
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
      // Also store in VM clipboard context for sending to VNC
      if (vmClipboard) {
        vmClipboard.setClipboardText(text)
      }
    })
  }

  return (
    <div className="relative group my-3">
      <pre className="bg-gray-900 rounded-lg p-3 pr-12 overflow-x-auto">
        {children}
      </pre>
      <button
        onClick={handleCopy}
        className="absolute top-2 right-2 p-1.5 rounded bg-gray-700 hover:bg-gray-600 text-gray-300 hover:text-white opacity-0 group-hover:opacity-100 transition-opacity"
        title={copied ? 'Copied! Click "Send to VM" in console header to paste in VM' : 'Copy to clipboard'}
      >
        {copied ? (
          <Check className="w-4 h-4 text-green-400" />
        ) : (
          <Copy className="w-4 h-4" />
        )}
      </button>
    </div>
  )
}

// Helper to extract text from React children
function extractText(children: React.ReactNode): string {
  if (typeof children === 'string') return children
  if (typeof children === 'number') return String(children)
  if (Array.isArray(children)) return children.map(extractText).join('')
  if (children && typeof children === 'object' && 'props' in children) {
    return extractText((children as React.ReactElement).props.children)
  }
  return ''
}

export function StepContent({ step, onOpenVM }: StepContentProps) {
  return (
    <div className="p-4">
      <h2 className="text-lg font-semibold text-white mb-4">{step.title}</h2>

      <div className="prose prose-invert prose-sm max-w-none">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            // Handle <pre> elements (code blocks) - add copy button
            pre({ children }: { children?: React.ReactNode }) {
              return <PreBlock>{children}</PreBlock>
            },
            // Handle <code> elements - just style them (no copy button for inline)
            code({ className, children, ...props }: { className?: string; children?: React.ReactNode }) {
              return (
                <code className={className || 'bg-gray-700 px-1 rounded'} {...props}>
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
