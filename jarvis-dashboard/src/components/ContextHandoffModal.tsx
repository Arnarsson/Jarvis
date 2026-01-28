import { useState, useEffect } from 'react'
import { apiGet } from '../api/client.ts'

/* ───────────────────────── Types ───────────────────────── */

interface HandoffData {
  project: string
  last_touched: string | null
  summary: string
  pending: string[]
  sources: Array<{
    title: string
    date: string | null
    conversation_id: string
  }>
  generated_at: string
}

interface ContextHandoffModalProps {
  project: string
  isOpen: boolean
  onClose: () => void
}

/* ───────────────────────── Helpers ───────────────────────── */

function timeAgo(isoDate: string): string {
  try {
    const now = Date.now()
    const then = new Date(isoDate).getTime()
    const diffMs = now - then
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffDays === 0) return 'today'
    if (diffDays === 1) return 'yesterday'
    if (diffDays < 7) return `${diffDays}d ago`
    if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`
    if (diffDays < 365) return `${Math.floor(diffDays / 30)}mo ago`
    return `${Math.floor(diffDays / 365)}y ago`
  } catch {
    return ''
  }
}

/* ───────────────────────── Component ───────────────────────── */

export function ContextHandoffModal({ project, isOpen, onClose }: ContextHandoffModalProps) {
  const [handoff, setHandoff] = useState<HandoffData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (isOpen && project) {
      fetchHandoff()
    }
  }, [isOpen, project])

  const fetchHandoff = async () => {
    setLoading(true)
    setError(null)
    setHandoff(null)
    
    // Create timeout promise (10 seconds)
    const timeoutPromise = new Promise<never>((_, reject) => {
      setTimeout(() => reject(new Error('Request timed out after 10 seconds')), 10000)
    })
    
    try {
      const data = await Promise.race([
        apiGet<HandoffData>(
          `/api/v2/context/handoff?project=${encodeURIComponent(project)}&limit=8`
        ),
        timeoutPromise
      ])
      setHandoff(data)
    } catch (e) {
      console.error('Failed to fetch context handoff:', e)
      const errorMessage = e instanceof Error && e.message.includes('timed out')
        ? 'Request timed out. The server may be busy or unavailable.'
        : 'Failed to generate context handoff. Please try again.'
      setError(errorMessage)
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div
      className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-background border border-border rounded-lg max-w-3xl w-full max-h-[90vh] overflow-y-auto shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="border-b border-border/30 p-6 sticky top-0 bg-background/95 backdrop-blur">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-mono font-bold text-text-primary tracking-wider">
                🎯 {project}
              </h2>
              <p className="text-[11px] font-mono text-text-muted mt-1">
                Context Handoff Summary
              </p>
            </div>
            <button
              onClick={onClose}
              className="text-text-muted hover:text-text-primary text-2xl leading-none"
            >
              ×
            </button>
          </div>
          {handoff?.last_touched && (
            <div className="mt-3 text-[10px] font-mono text-text-muted">
              Last touched: {timeAgo(handoff.last_touched)}
            </div>
          )}
        </div>

        {/* Content */}
        <div className="p-6">
          {/* Loading */}
          {loading && (
            <div className="flex items-center gap-2 text-text-muted text-xs font-mono py-8">
              <span className="inline-block h-2 w-2 rounded-full bg-accent animate-pulse" />
              Generating context handoff…
            </div>
          )}

          {/* Error */}
          {error && !loading && (
            <div className="border border-red-500/30 rounded-lg p-4 bg-red-500/10">
              <div className="flex items-start gap-3">
                <span className="text-red-400 text-lg flex-shrink-0">⚠</span>
                <div>
                  <p className="text-red-400 text-xs font-mono font-bold mb-1">Error</p>
                  <p className="text-red-400/80 text-xs font-mono">{error}</p>
                  <button
                    onClick={fetchHandoff}
                    className="mt-3 px-3 py-1 text-[10px] font-mono border border-red-400/30 text-red-400 hover:bg-red-400/10 transition-colors rounded"
                  >
                    RETRY
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Summary */}
          {!loading && handoff && (
            <div className="space-y-6">
              {/* Summary Text */}
              <div className="prose prose-invert prose-sm max-w-none">
                {handoff.summary ? (
                  <div className="text-xs font-mono text-text-secondary leading-relaxed whitespace-pre-line">
                    {handoff.summary}
                  </div>
                ) : (
                  <div className="text-xs font-mono text-text-muted italic py-4">
                    No recent decisions or context found for this project.
                  </div>
                )}
              </div>

              {/* Pending Items */}
              <div className="border-t border-border/30 pt-6">
                <h3 className="text-[11px] font-mono font-bold text-text-primary uppercase tracking-wider mb-3">
                  ⚠️ Open Action Items
                </h3>
                {handoff.pending.length > 0 ? (
                  <ul className="space-y-2">
                    {handoff.pending.map((item, i) => (
                      <li
                        key={i}
                        className="flex items-start gap-2 text-xs font-mono text-text-secondary"
                      >
                        <span className="text-accent mt-0.5 flex-shrink-0">▸</span>
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="text-xs font-mono text-text-muted italic py-2">
                    No open action items found.
                  </div>
                )}
              </div>

              {/* Sources */}
              <div className="border-t border-border/30 pt-6">
                <h3 className="text-[11px] font-mono font-bold text-text-primary uppercase tracking-wider mb-3">
                  📚 Sources
                </h3>
                {handoff.sources.length > 0 ? (
                  <div className="space-y-2">
                    {handoff.sources.map((source, i) => (
                      <div
                        key={i}
                        className="text-xs font-mono text-text-muted flex items-center gap-2"
                      >
                        <span className="text-accent">•</span>
                        <span className="text-text-secondary">{source.title}</span>
                        {source.date && (
                          <span className="text-text-muted">
                            ({timeAgo(source.date)})
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-xs font-mono text-text-muted italic py-2">
                    No conversation sources found.
                  </div>
                )}
              </div>

              {/* Footer */}
              <div className="border-t border-border/30 pt-4 text-[10px] font-mono text-text-muted text-center">
                Generated {handoff.generated_at ? timeAgo(handoff.generated_at) : 'just now'}
              </div>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="border-t border-border/30 p-4 flex items-center justify-end gap-3">
          <button
            onClick={fetchHandoff}
            disabled={loading}
            className="px-4 py-2 text-[11px] font-mono border border-border text-text-primary hover:border-accent hover:text-accent transition-colors disabled:opacity-50"
          >
            REFRESH
          </button>
          <button
            onClick={onClose}
            className="px-4 py-2 text-[11px] font-mono bg-accent/10 border border-accent text-accent hover:bg-accent hover:text-background transition-colors"
          >
            CLOSE
          </button>
        </div>
      </div>
    </div>
  )
}
