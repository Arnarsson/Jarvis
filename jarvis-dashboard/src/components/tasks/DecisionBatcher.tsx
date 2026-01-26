import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost } from '../../api/client.ts'

/* ───────────────── Types ───────────────── */

interface WorkflowSuggestion {
  id: string
  name: string
  description: string
  pattern_type: string
  trigger_description: string
  action_description: string
  confidence: number
}

interface SuggestionsResponse {
  suggestions: WorkflowSuggestion[]
  total: number
}

/* ───────────────── Component ───────────────── */

type ViewMode = 'compact' | 'stack'

export function DecisionBatcher() {
  const queryClient = useQueryClient()
  const [viewMode, setViewMode] = useState<ViewMode>('compact')
  const [stackIndex, setStackIndex] = useState(0)
  const [decided, setDecided] = useState<Set<string>>(new Set())
  const [allDone, setAllDone] = useState(false)

  const { data: suggestions } = useQuery({
    queryKey: ['workflow', 'suggestions'],
    queryFn: async () => {
      try {
        const res = await apiGet<SuggestionsResponse>('/api/workflow/suggestions')
        return res.suggestions ?? []
      } catch {
        return []
      }
    },
  })

  const pending = useMemo(
    () => (suggestions ?? []).filter((s) => !decided.has(s.id)),
    [suggestions, decided]
  )

  const approveMutation = useMutation({
    mutationFn: (id: string) => apiPost(`/api/workflow/suggestions/${id}/approve`),
    onSuccess: (_data, id) => {
      markDecided(id)
    },
  })

  const rejectMutation = useMutation({
    mutationFn: (id: string) => apiPost(`/api/workflow/suggestions/${id}/reject`),
    onSuccess: (_data, id) => {
      markDecided(id)
    },
  })

  function markDecided(id: string) {
    setDecided((prev) => {
      const next = new Set(prev)
      next.add(id)
      // Check if all done
      const remaining = (suggestions ?? []).filter((s) => !next.has(s.id))
      if (remaining.length === 0 && (suggestions?.length ?? 0) > 0) {
        setAllDone(true)
        setTimeout(() => {
          queryClient.invalidateQueries({ queryKey: ['workflow', 'suggestions'] })
          queryClient.invalidateQueries({ queryKey: ['workflow', 'patterns'] })
        }, 1500)
      }
      return next
    })
    // Advance stack if in stack mode
    if (viewMode === 'stack') {
      setStackIndex((prev) => prev + 1)
    }
  }

  const isMutating = approveMutation.isPending || rejectMutation.isPending

  // Only show when 3+ pending suggestions
  if (!suggestions || suggestions.length < 3 || allDone) {
    if (allDone) {
      return (
        <div className="mb-6 border border-success/30 rounded-lg bg-success/5 px-5 py-4 text-center">
          <p className="text-success font-mono text-[14px] font-medium tracking-wide">
            All caught up ✓
          </p>
          <p className="text-[11px] text-text-secondary mt-1">
            All {suggestions?.length ?? 0} decisions handled
          </p>
        </div>
      )
    }
    return null
  }

  if (pending.length === 0 && !allDone) {
    return (
      <div className="mb-6 border border-success/30 rounded-lg bg-success/5 px-5 py-4 text-center">
        <p className="text-success font-mono text-[14px] font-medium tracking-wide">
          All caught up ✓
        </p>
      </div>
    )
  }

  return (
    <div className="mb-6">
      {/* Banner header */}
      <div className="flex items-center justify-between border border-accent/40 rounded-t-lg bg-accent/5 px-4 py-3">
        <div className="flex items-center gap-3">
          <span className="text-lg">⚡</span>
          <div>
            <p className="font-mono text-[13px] text-accent font-bold tracking-wider">
              QUICK DECISIONS
            </p>
            <p className="text-[11px] text-text-secondary mt-0.5">
              {pending.length} suggestion{pending.length !== 1 ? 's' : ''} waiting
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => { setViewMode('compact'); setStackIndex(0) }}
            className={`font-mono text-[10px] tracking-wider px-2.5 py-1 border transition-colors ${
              viewMode === 'compact'
                ? 'border-accent text-accent bg-accent/10'
                : 'border-border text-text-secondary hover:text-text-primary'
            }`}
          >
            LIST
          </button>
          <button
            onClick={() => { setViewMode('stack'); setStackIndex(0) }}
            className={`font-mono text-[10px] tracking-wider px-2.5 py-1 border transition-colors ${
              viewMode === 'stack'
                ? 'border-accent text-accent bg-accent/10'
                : 'border-border text-text-secondary hover:text-text-primary'
            }`}
          >
            CARDS
          </button>
        </div>
      </div>

      {/* Compact view */}
      {viewMode === 'compact' && (
        <div className="border border-t-0 border-border/50 rounded-b-lg bg-surface/30 divide-y divide-border/30">
          {pending.map((s) => (
            <div key={s.id} className="flex items-center justify-between px-4 py-3 gap-3">
              <div className="flex-1 min-w-0">
                <p className="text-[13px] text-text-primary truncate">{s.name}</p>
                <p className="text-[10px] text-text-muted mt-0.5 truncate">
                  {s.description || s.pattern_type}
                </p>
              </div>
              <div className="flex gap-2 shrink-0">
                <button
                  onClick={() => approveMutation.mutate(s.id)}
                  disabled={isMutating}
                  className="font-mono text-[11px] tracking-wider font-bold px-3 py-1.5 border border-success/50 text-success hover:bg-success/10 transition-colors disabled:opacity-40"
                >
                  YES
                </button>
                <button
                  onClick={() => rejectMutation.mutate(s.id)}
                  disabled={isMutating}
                  className="font-mono text-[11px] tracking-wider font-bold px-3 py-1.5 border border-border text-text-secondary hover:text-text-primary transition-colors disabled:opacity-40"
                >
                  NO
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Stack / card view */}
      {viewMode === 'stack' && (
        <div className="border border-t-0 border-border/50 rounded-b-lg bg-surface/30 p-5">
          {stackIndex < pending.length ? (
            <>
              {/* Progress */}
              <div className="flex items-center justify-between mb-4">
                <p className="font-mono text-[10px] text-text-muted tracking-wider">
                  {stackIndex + 1} of {pending.length}
                </p>
                <div className="flex gap-1">
                  {pending.map((_, i) => (
                    <div
                      key={i}
                      className={`w-2 h-2 rounded-full transition-colors ${
                        i < stackIndex ? 'bg-success' : i === stackIndex ? 'bg-accent' : 'bg-border'
                      }`}
                    />
                  ))}
                </div>
              </div>

              {/* Current card */}
              <div className="border border-border/50 rounded-lg p-5 bg-surface/50">
                <p className="text-[16px] text-text-primary font-medium mb-2">
                  {pending[stackIndex].name}
                </p>
                <p className="text-[12px] text-text-secondary mb-4 leading-relaxed">
                  {pending[stackIndex].description || pending[stackIndex].pattern_type}
                </p>

                {/* Trigger + Action */}
                <div className="grid grid-cols-2 gap-4 mb-5">
                  <div>
                    <p className="font-mono text-[9px] tracking-wider text-text-muted uppercase mb-1">
                      Trigger
                    </p>
                    <p className="text-[12px] text-text-secondary">
                      {pending[stackIndex].trigger_description}
                    </p>
                  </div>
                  <div>
                    <p className="font-mono text-[9px] tracking-wider text-text-muted uppercase mb-1">
                      Action
                    </p>
                    <p className="text-[12px] text-text-secondary">
                      {pending[stackIndex].action_description}
                    </p>
                  </div>
                </div>

                {/* Confidence */}
                <div className="flex items-center gap-2 mb-5">
                  <div className="flex-1 bg-border/50 h-1.5 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full bg-accent transition-all"
                      style={{ width: `${Math.round(pending[stackIndex].confidence * 100)}%` }}
                    />
                  </div>
                  <span className="font-mono text-[10px] text-text-secondary">
                    {Math.round(pending[stackIndex].confidence * 100)}%
                  </span>
                </div>

                {/* Action buttons */}
                <div className="flex gap-3">
                  <button
                    onClick={() => approveMutation.mutate(pending[stackIndex].id)}
                    disabled={isMutating}
                    className="flex-1 font-mono text-[13px] tracking-wider font-bold py-3 border border-success/50 text-success hover:bg-success/10 rounded transition-colors disabled:opacity-40"
                  >
                    YES — APPROVE
                  </button>
                  <button
                    onClick={() => rejectMutation.mutate(pending[stackIndex].id)}
                    disabled={isMutating}
                    className="flex-1 font-mono text-[13px] tracking-wider font-bold py-3 border border-border text-text-secondary hover:text-text-primary rounded transition-colors disabled:opacity-40"
                  >
                    NO — SKIP
                  </button>
                </div>
              </div>
            </>
          ) : (
            <div className="text-center py-6">
              <p className="text-success font-mono text-[14px] font-medium">
                All caught up ✓
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
