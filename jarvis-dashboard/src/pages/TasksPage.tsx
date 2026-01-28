import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost } from '../api/client.ts'
import { LoadingSkeleton } from '../components/ui/LoadingSkeleton.tsx'
import { DecisionBatcher } from '../components/tasks/DecisionBatcher.tsx'

// ── Types ────────────────────────────────────────────────────────────────────

interface WorkflowSuggestion {
  id: string
  name: string
  description: string
  pattern_type: string
  trigger_description: string
  action_description: string
  confidence: number
  similar_captures: unknown[]
}

interface SuggestionsResponse {
  suggestions: WorkflowSuggestion[]
  total: number
}

interface WorkflowPattern {
  id: string
  name: string
  description: string
  status: string
  confidence: number
  trust_tier: 'observe' | 'suggest' | 'auto'
  pattern_type: string
  frequency_count: number
  is_active: boolean
  total_executions: number
  last_seen: string
  created_at: string
}

interface PatternsResponse {
  patterns: WorkflowPattern[]
}

interface WorkflowExecution {
  id: string
  pattern_id: string
  pattern_name?: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  started_at: string
  completed_at?: string
  result?: string
  error?: string
  user_approved?: boolean
  was_correct?: boolean | null
  actions_result?: {
    actions: Array<{
      success: boolean
      action_type: string
      message: string
    }>
  }
}

interface ExecutionsResponse {
  executions: WorkflowExecution[]
  total?: number
}

interface AnalysisCandidate {
  pattern: {
    name: string
    description: string
    pattern_type: string
    trigger_conditions: {
      type: string
      keywords?: string[]
    }
    actions: Array<{
      type: string
      message: string
    }>
  }
  confidence: number
  evidence_count: number
}

interface AnalysisResponse {
  analyzed_hours: number
  candidates_found: number
  candidates: AnalysisCandidate[]
}

// ── Tabs ─────────────────────────────────────────────────────────────────────

type Tab = 'overview' | 'patterns' | 'executions' | 'discover'

// ── Helpers ──────────────────────────────────────────────────────────────────

const TIER_CONFIG = {
  observe: { label: 'OBSERVE', color: 'text-text-muted', border: 'border-border/50', bg: 'bg-border/20', icon: '👁️', desc: 'Watching silently' },
  suggest: { label: 'SUGGEST', color: 'text-blue-400', border: 'border-blue-500/30', bg: 'bg-blue-500/10', icon: '💡', desc: 'Will ask before acting' },
  auto: { label: 'AUTO', color: 'text-emerald-400', border: 'border-emerald-500/30', bg: 'bg-emerald-500/10', icon: '⚡', desc: 'Runs automatically' },
} as const

const PATTERN_TYPE_ICONS: Record<string, string> = {
  TIME_BASED: '🕐',
  TRIGGER_RESPONSE: '🔗',
  REPETITIVE_ACTION: '🔄',
  CONTEXT_SWITCH: '🔀',
}

function timeAgo(ts: string): string {
  const ms = Date.now() - new Date(ts).getTime()
  const mins = Math.floor(ms / 60_000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  return `${days}d ago`
}

function formatTimestamp(ts: string): string {
  try {
    return new Date(ts).toLocaleString('en-GB', {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false,
    })
  } catch {
    return ts
  }
}

// ── Overview Tab ─────────────────────────────────────────────────────────────

function OverviewTab({ patterns, executions, suggestions, onNavigate }: {
  patterns: WorkflowPattern[]
  executions: WorkflowExecution[]
  suggestions: WorkflowSuggestion[]
  onNavigate: (tab: Tab) => void
}) {
  const autoPatterns = patterns.filter(p => p.trust_tier === 'auto' && p.is_active)
  const suggestPatterns = patterns.filter(p => p.trust_tier === 'suggest' && p.is_active)
  const observePatterns = patterns.filter(p => p.trust_tier === 'observe' && p.is_active)
  const recentExecs = executions.slice(0, 5)
  const completedExecs = executions.filter(e => e.status === 'completed')
  const failedExecs = executions.filter(e => e.status === 'failed')

  return (
    <div className="space-y-8">
      {/* Stats row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="border border-border/40 rounded-lg p-4">
          <p className="font-mono text-[10px] tracking-wider text-text-muted uppercase">PATTERNS</p>
          <p className="text-2xl font-bold text-text-primary mt-1">{patterns.length}</p>
          <p className="text-[11px] text-text-muted mt-0.5">{autoPatterns.length} auto · {suggestPatterns.length} suggest</p>
        </div>
        <div className="border border-border/40 rounded-lg p-4">
          <p className="font-mono text-[10px] tracking-wider text-text-muted uppercase">EXECUTIONS</p>
          <p className="text-2xl font-bold text-text-primary mt-1">{executions.length}</p>
          <p className="text-[11px] text-text-muted mt-0.5">{completedExecs.length} completed · {failedExecs.length} failed</p>
        </div>
        <div className="border border-border/40 rounded-lg p-4">
          <p className="font-mono text-[10px] tracking-wider text-text-muted uppercase">PENDING</p>
          <p className="text-2xl font-bold text-text-primary mt-1">{suggestions.length}</p>
          <p className="text-[11px] text-text-muted mt-0.5">awaiting approval</p>
        </div>
        <div className="border border-border/40 rounded-lg p-4">
          <p className="font-mono text-[10px] tracking-wider text-text-muted uppercase">TRUST</p>
          <div className="flex items-center gap-1.5 mt-2">
            <div className="flex-1 bg-border/30 h-2 rounded-full overflow-hidden flex">
              {autoPatterns.length > 0 && (
                <div className="h-full bg-emerald-500" style={{ width: `${(autoPatterns.length / Math.max(patterns.length, 1)) * 100}%` }} />
              )}
              {suggestPatterns.length > 0 && (
                <div className="h-full bg-blue-500" style={{ width: `${(suggestPatterns.length / Math.max(patterns.length, 1)) * 100}%` }} />
              )}
              {observePatterns.length > 0 && (
                <div className="h-full bg-zinc-600" style={{ width: `${(observePatterns.length / Math.max(patterns.length, 1)) * 100}%` }} />
              )}
            </div>
          </div>
          <p className="text-[11px] text-text-muted mt-1">
            <span className="text-emerald-400">⚡{autoPatterns.length}</span>
            {' · '}
            <span className="text-blue-400">💡{suggestPatterns.length}</span>
            {' · '}
            <span className="text-text-muted">👁️{observePatterns.length}</span>
          </p>
        </div>
      </div>

      {/* Pending suggestions */}
      {suggestions.length > 0 && (
        <section>
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-mono text-[11px] tracking-widest text-text-muted uppercase">
              ⚠️ PENDING DECISIONS
            </h3>
            <button onClick={() => onNavigate('patterns')} className="font-mono text-[10px] text-accent hover:underline">
              VIEW ALL →
            </button>
          </div>
          <PendingSuggestions suggestions={suggestions} />
        </section>
      )}

      {/* Active automations */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-mono text-[11px] tracking-widest text-text-muted uppercase">
            ACTIVE AUTOMATIONS
          </h3>
          <button onClick={() => onNavigate('patterns')} className="font-mono text-[10px] text-accent hover:underline">
            MANAGE →
          </button>
        </div>
        {patterns.length === 0 ? (
          <div className="border border-border/30 rounded-lg p-6 text-center">
            <div className="text-3xl mb-3">🔍</div>
            <p className="text-sm font-mono text-text-secondary">No patterns detected yet</p>
            <p className="text-xs font-mono text-text-muted mt-1">Jarvis learns from your screen activity and suggests automations</p>
            <button
              onClick={() => onNavigate('discover')}
              className="mt-4 font-mono text-[11px] tracking-wider px-4 py-2 border border-accent text-accent hover:bg-accent/10 transition-colors"
            >
              SCAN FOR PATTERNS
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            {patterns.filter(p => p.is_active).map(pattern => (
              <PatternCard key={pattern.id} pattern={pattern} compact />
            ))}
          </div>
        )}
      </section>

      {/* Recent activity */}
      {recentExecs.length > 0 && (
        <section>
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-mono text-[11px] tracking-widest text-text-muted uppercase">
              RECENT ACTIVITY
            </h3>
            <button onClick={() => onNavigate('executions')} className="font-mono text-[10px] text-accent hover:underline">
              ALL EXECUTIONS →
            </button>
          </div>
          <div className="space-y-1">
            {recentExecs.map(exec => (
              <div key={exec.id} className="flex items-center gap-3 py-2.5 px-3 border border-border/20 rounded">
                <span className={`h-2 w-2 rounded-full shrink-0 ${
                  exec.status === 'completed' ? 'bg-emerald-400' :
                  exec.status === 'failed' ? 'bg-red-400' :
                  exec.status === 'running' ? 'bg-blue-400 animate-pulse' : 'bg-zinc-500'
                }`} />
                <span className="text-[13px] text-text-primary flex-1 truncate">
                  {exec.pattern_name || exec.pattern_id.slice(0, 8)}
                </span>
                {exec.actions_result?.actions?.[0]?.message && (
                  <span className="text-[11px] text-text-muted truncate max-w-[200px] hidden sm:block">
                    {exec.actions_result.actions[0].message}
                  </span>
                )}
                <span className="font-mono text-[10px] text-text-muted shrink-0">
                  {timeAgo(exec.started_at)}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}

// ── Pending Suggestions ──────────────────────────────────────────────────────

function PendingSuggestions({ suggestions }: { suggestions: WorkflowSuggestion[] }) {
  const queryClient = useQueryClient()

  const approveMutation = useMutation({
    mutationFn: (id: string) => apiPost(`/api/workflow/suggestions/${id}/approve`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflow'] })
    },
  })

  const rejectMutation = useMutation({
    mutationFn: (id: string) => apiPost(`/api/workflow/suggestions/${id}/reject`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflow'] })
    },
  })

  return (
    <div className="space-y-3">
      {suggestions.map(s => (
        <div key={s.id} className="border border-amber-500/20 bg-amber-500/5 rounded-lg p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <p className="text-[14px] text-text-primary font-medium">{s.name}</p>
              <p className="text-[12px] text-text-secondary mt-1">{s.description || s.pattern_type}</p>
              {s.trigger_description && (
                <p className="text-[11px] text-text-muted mt-2">
                  <span className="text-text-secondary">When:</span> {s.trigger_description}
                  {' → '}
                  <span className="text-text-secondary">Then:</span> {s.action_description}
                </p>
              )}
            </div>
            <div className="flex gap-2 shrink-0">
              <button
                onClick={() => approveMutation.mutate(s.id)}
                disabled={approveMutation.isPending}
                className="font-mono text-[11px] tracking-wider px-3 py-1.5 border border-emerald-500/40 text-emerald-400 hover:bg-emerald-500/10 transition-colors"
              >
                APPROVE
              </button>
              <button
                onClick={() => rejectMutation.mutate(s.id)}
                disabled={rejectMutation.isPending}
                className="font-mono text-[11px] tracking-wider px-3 py-1.5 border border-border text-text-muted hover:text-text-primary transition-colors"
              >
                REJECT
              </button>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Pattern Card ─────────────────────────────────────────────────────────────

function PatternCard({ pattern, compact = false }: { pattern: WorkflowPattern; compact?: boolean }) {
  const [expanded, setExpanded] = useState(false)
  const queryClient = useQueryClient()
  const tier = TIER_CONFIG[pattern.trust_tier] || TIER_CONFIG.observe
  const typeIcon = PATTERN_TYPE_ICONS[pattern.pattern_type] || '📋'

  const promoteMutation = useMutation({
    mutationFn: ({ id, newTier }: { id: string; newTier: string }) =>
      apiPost(`/api/workflow/patterns/${id}/promote?tier=${encodeURIComponent(newTier)}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['workflow'] }),
  })

  const suspendMutation = useMutation({
    mutationFn: (id: string) =>
      apiPost(`/api/workflow/patterns/${id}/suspend?reason=${encodeURIComponent('Suspended from dashboard')}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['workflow'] }),
  })

  const nextTier = pattern.trust_tier === 'observe' ? 'suggest' : pattern.trust_tier === 'suggest' ? 'auto' : null

  if (compact) {
    return (
      <div
        className="flex items-center gap-3 py-3 px-4 border border-border/30 rounded-lg hover:border-border/60 cursor-pointer transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="text-lg shrink-0">{typeIcon}</span>
        <div className="flex-1 min-w-0">
          <p className="text-[13px] text-text-primary truncate">{pattern.name}</p>
          {pattern.description && !expanded && (
            <p className="text-[11px] text-text-muted truncate">{pattern.description}</p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="font-mono text-[10px] text-text-muted">
            {pattern.frequency_count}× seen
          </span>
          <span className={`font-mono text-[9px] tracking-wider px-2 py-0.5 rounded-full border ${tier.border} ${tier.bg} ${tier.color}`}>
            {tier.icon} {tier.label}
          </span>
        </div>
        {expanded && (
          <div className="absolute right-4 flex gap-1.5">
            {nextTier && (
              <button
                onClick={(e) => { e.stopPropagation(); promoteMutation.mutate({ id: pattern.id, newTier: nextTier! }) }}
                className="font-mono text-[10px] px-2 py-1 border border-accent/40 text-accent hover:bg-accent/10 rounded"
              >
                PROMOTE
              </button>
            )}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="border border-border/40 rounded-lg p-5 hover:border-border/60 transition-colors">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="text-xl mt-0.5">{typeIcon}</span>
          <div>
            <p className="text-[15px] text-text-primary font-medium">{pattern.name}</p>
            {pattern.description && (
              <p className="text-[12px] text-text-secondary mt-1">{pattern.description}</p>
            )}
          </div>
        </div>
        <span className={`font-mono text-[10px] tracking-wider px-2.5 py-1 rounded-full border shrink-0 ${tier.border} ${tier.bg} ${tier.color}`}>
          {tier.icon} {tier.label}
        </span>
      </div>

      {/* Meta */}
      <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div>
          <p className="font-mono text-[9px] tracking-wider text-text-muted uppercase">TYPE</p>
          <p className="text-[12px] text-text-secondary mt-0.5">{pattern.pattern_type.replace(/_/g, ' ')}</p>
        </div>
        <div>
          <p className="font-mono text-[9px] tracking-wider text-text-muted uppercase">FREQUENCY</p>
          <p className="text-[12px] text-text-secondary mt-0.5">{pattern.frequency_count}× detected</p>
        </div>
        <div>
          <p className="font-mono text-[9px] tracking-wider text-text-muted uppercase">EXECUTIONS</p>
          <p className="text-[12px] text-text-secondary mt-0.5">{pattern.total_executions}</p>
        </div>
        <div>
          <p className="font-mono text-[9px] tracking-wider text-text-muted uppercase">LAST SEEN</p>
          <p className="text-[12px] text-text-secondary mt-0.5">{timeAgo(pattern.last_seen)}</p>
        </div>
      </div>

      {/* Trust progression */}
      <div className="mt-4">
        <p className="font-mono text-[9px] tracking-wider text-text-muted uppercase mb-2">TRUST PROGRESSION</p>
        <div className="flex items-center gap-1">
          {(['observe', 'suggest', 'auto'] as const).map((t, i) => {
            const cfg = TIER_CONFIG[t]
            const isActive = t === pattern.trust_tier
            const isPast = ['observe', 'suggest', 'auto'].indexOf(t) < ['observe', 'suggest', 'auto'].indexOf(pattern.trust_tier)
            return (
              <div key={t} className="flex items-center gap-1">
                {i > 0 && <div className={`w-6 h-px ${isPast || isActive ? 'bg-emerald-500/50' : 'bg-border/30'}`} />}
                <div className={`font-mono text-[9px] tracking-wider px-2 py-1 rounded border ${
                  isActive ? `${cfg.border} ${cfg.bg} ${cfg.color} font-bold` :
                  isPast ? 'border-emerald-500/20 bg-emerald-500/5 text-emerald-400/50' :
                  'border-border/20 text-text-muted/30'
                }`}>
                  {cfg.icon} {cfg.label}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Actions */}
      <div className="mt-4 flex gap-2">
        {nextTier && (
          <button
            onClick={() => promoteMutation.mutate({ id: pattern.id, newTier: nextTier! })}
            disabled={promoteMutation.isPending}
            className="font-mono text-[11px] tracking-wider px-4 py-2 border border-accent text-accent hover:bg-accent/10 transition-colors disabled:opacity-50"
          >
            PROMOTE TO {nextTier.toUpperCase()}
          </button>
        )}
        {pattern.is_active && (
          <button
            onClick={() => suspendMutation.mutate(pattern.id)}
            disabled={suspendMutation.isPending}
            className="font-mono text-[11px] tracking-wider px-4 py-2 border border-border text-text-muted hover:text-warning hover:border-warning/40 transition-colors disabled:opacity-50"
          >
            SUSPEND
          </button>
        )}
      </div>
    </div>
  )
}

// ── Patterns Tab ─────────────────────────────────────────────────────────────

function PatternsTab({ patterns }: { patterns: WorkflowPattern[] }) {
  const [filter, setFilter] = useState<'all' | 'auto' | 'suggest' | 'observe'>('all')

  const filtered = filter === 'all' ? patterns : patterns.filter(p => p.trust_tier === filter)

  return (
    <div>
      {/* Filter row */}
      <div className="flex gap-2 mb-5">
        {(['all', 'auto', 'suggest', 'observe'] as const).map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`font-mono text-[11px] tracking-wider px-3 py-1.5 border rounded transition-colors ${
              filter === f
                ? 'border-accent text-accent bg-accent/10'
                : 'border-border/40 text-text-muted hover:text-text-primary hover:border-border'
            }`}
          >
            {f === 'all' ? 'ALL' : TIER_CONFIG[f].icon + ' ' + f.toUpperCase()}
            <span className="ml-1.5 text-text-muted">{f === 'all' ? patterns.length : patterns.filter(p => p.trust_tier === f).length}</span>
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className="border border-border/30 rounded-lg p-8 text-center">
          <p className="text-sm font-mono text-text-secondary">No patterns in this tier</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map(p => <PatternCard key={p.id} pattern={p} />)}
        </div>
      )}
    </div>
  )
}

// ── Executions Tab ───────────────────────────────────────────────────────────

function ExecutionsTab({ executions }: { executions: WorkflowExecution[] }) {
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const feedbackMutation = useMutation({
    mutationFn: ({ id, correct }: { id: string; correct: boolean }) =>
      apiPost(`/api/workflow/executions/${id}/feedback`, { was_correct: correct }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['workflow'] }),
  })

  if (executions.length === 0) {
    return (
      <div className="border border-border/30 rounded-lg p-8 text-center">
        <div className="text-3xl mb-3">📋</div>
        <p className="text-sm font-mono text-text-secondary">No executions yet</p>
        <p className="text-xs font-mono text-text-muted mt-1">Automations will appear here when patterns trigger</p>
      </div>
    )
  }

  return (
    <div className="space-y-1">
      {executions.map(exec => {
        const isExpanded = expandedId === exec.id
        return (
          <div
            key={exec.id}
            className="border border-border/30 rounded-lg overflow-hidden hover:border-border/50 transition-colors"
          >
            <div
              className="flex items-center gap-3 px-4 py-3 cursor-pointer"
              onClick={() => setExpandedId(isExpanded ? null : exec.id)}
            >
              <span className={`h-2.5 w-2.5 rounded-full shrink-0 ${
                exec.status === 'completed' ? 'bg-emerald-400' :
                exec.status === 'failed' ? 'bg-red-400' :
                exec.status === 'running' ? 'bg-blue-400 animate-pulse' :
                exec.status === 'pending' ? 'bg-amber-400 animate-pulse' : 'bg-zinc-500'
              }`} />
              <span className="text-[13px] text-text-primary flex-1 truncate font-medium">
                {exec.pattern_name || exec.pattern_id.slice(0, 8)}
              </span>
              <span className={`font-mono text-[10px] tracking-wider px-2 py-0.5 rounded border ${
                exec.status === 'completed' ? 'border-emerald-500/30 text-emerald-400 bg-emerald-500/10' :
                exec.status === 'failed' ? 'border-red-500/30 text-red-400 bg-red-500/10' :
                'border-border/40 text-text-muted'
              }`}>
                {exec.status.toUpperCase()}
              </span>
              <span className="font-mono text-[10px] text-text-muted shrink-0">
                {formatTimestamp(exec.started_at)}
              </span>
            </div>

            {isExpanded && (
              <div className="px-4 pb-4 border-t border-border/20 pt-3 space-y-3">
                {/* Action results */}
                {exec.actions_result?.actions?.map((action, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <span className={`text-xs mt-0.5 ${action.success ? 'text-emerald-400' : 'text-red-400'}`}>
                      {action.success ? '✓' : '✗'}
                    </span>
                    <div>
                      <span className="font-mono text-[10px] text-text-muted uppercase">{action.action_type}</span>
                      <p className="text-[12px] text-text-secondary">{action.message}</p>
                    </div>
                  </div>
                ))}

                {exec.error && (
                  <div className="bg-red-500/5 border border-red-500/20 rounded px-3 py-2">
                    <p className="font-mono text-[11px] text-red-400">{exec.error}</p>
                  </div>
                )}

                {/* Feedback */}
                {exec.status === 'completed' && exec.was_correct === null && (
                  <div className="flex items-center gap-3 pt-2">
                    <span className="text-[11px] text-text-muted">Was this correct?</span>
                    <button
                      onClick={() => feedbackMutation.mutate({ id: exec.id, correct: true })}
                      className="font-mono text-[10px] px-2.5 py-1 border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10 rounded"
                    >
                      👍 YES
                    </button>
                    <button
                      onClick={() => feedbackMutation.mutate({ id: exec.id, correct: false })}
                      className="font-mono text-[10px] px-2.5 py-1 border border-red-500/30 text-red-400 hover:bg-red-500/10 rounded"
                    >
                      👎 NO
                    </button>
                  </div>
                )}
                {exec.was_correct !== null && exec.was_correct !== undefined && (
                  <p className="text-[11px] text-text-muted">
                    Feedback: {exec.was_correct ? '👍 Correct' : '👎 Incorrect'}
                  </p>
                )}

                <p className="font-mono text-[9px] text-text-muted/50">ID: {exec.id}</p>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ── Discover Tab ─────────────────────────────────────────────────────────────

function DiscoverTab() {
  const { data, isLoading, refetch, isFetching } = useQuery<AnalysisResponse>({
    queryKey: ['workflow', 'analyze'],
    queryFn: async () => {
      try {
        return await apiGet<AnalysisResponse>('/api/workflow/analyze')
      } catch {
        return { analyzed_hours: 0, candidates_found: 0, candidates: [] }
      }
    },
    staleTime: 300_000, // 5 min
  })

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[13px] text-text-primary">
            Pattern discovery scans your screen activity to find automatable workflows.
          </p>
          {data && (
            <p className="text-[11px] text-text-muted mt-1">
              Analyzed {data.analyzed_hours}h of activity · Found {data.candidates_found} candidate patterns
            </p>
          )}
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="font-mono text-[11px] tracking-wider px-4 py-2 border border-accent text-accent hover:bg-accent/10 transition-colors disabled:opacity-50 shrink-0"
        >
          {isFetching ? 'SCANNING...' : 'SCAN NOW'}
        </button>
      </div>

      {isLoading && <LoadingSkeleton lines={6} />}

      {/* Candidates */}
      {data && data.candidates.length > 0 && (
        <div className="space-y-3">
          {data.candidates.slice(0, 10).map((candidate, i) => (
            <div key={i} className="border border-border/40 rounded-lg p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span>{PATTERN_TYPE_ICONS[candidate.pattern.pattern_type] || '📋'}</span>
                    <p className="text-[14px] text-text-primary font-medium truncate">
                      {candidate.pattern.name}
                    </p>
                  </div>
                  <p className="text-[12px] text-text-secondary mt-1">
                    {candidate.pattern.description}
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="font-mono text-[10px] text-text-muted">
                    {Math.round(candidate.confidence * 100)}% confidence
                  </span>
                  <span className="font-mono text-[10px] text-text-muted">
                    {candidate.evidence_count} evidence
                  </span>
                </div>
              </div>

              {/* Proposed action */}
              {candidate.pattern.actions?.[0] && (
                <div className="mt-3 bg-surface/50 border border-border/20 rounded px-3 py-2">
                  <span className="font-mono text-[9px] tracking-wider text-text-muted uppercase">PROPOSED ACTION</span>
                  <p className="text-[12px] text-text-secondary mt-0.5">
                    {candidate.pattern.actions[0].message}
                  </p>
                </div>
              )}

              {/* Confidence bar */}
              <div className="mt-3 flex items-center gap-2">
                <div className="flex-1 bg-border/30 h-1.5 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${
                      candidate.confidence >= 0.8 ? 'bg-emerald-500' :
                      candidate.confidence >= 0.5 ? 'bg-blue-500' : 'bg-amber-500'
                    }`}
                    style={{ width: `${Math.round(candidate.confidence * 100)}%` }}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {data && data.candidates.length === 0 && !isLoading && (
        <div className="border border-border/30 rounded-lg p-8 text-center">
          <div className="text-3xl mb-3">🧘</div>
          <p className="text-sm font-mono text-text-secondary">No new patterns found</p>
          <p className="text-xs font-mono text-text-muted mt-1">Keep using your computer — Jarvis will detect patterns over time</p>
        </div>
      )}

      {/* How it works */}
      <div className="border border-border/20 rounded-lg p-5">
        <h4 className="font-mono text-[11px] tracking-widest text-text-muted uppercase mb-3">HOW PATTERN DETECTION WORKS</h4>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <p className="text-lg mb-1">👁️ Observe</p>
            <p className="text-[12px] text-text-secondary">Jarvis watches your screen activity silently, building a model of your workflows</p>
          </div>
          <div>
            <p className="text-lg mb-1">💡 Suggest</p>
            <p className="text-[12px] text-text-secondary">When a pattern is confirmed, Jarvis suggests automations and asks for approval</p>
          </div>
          <div>
            <p className="text-lg mb-1">⚡ Automate</p>
            <p className="text-[12px] text-text-secondary">Trusted patterns run automatically — notifications, reminders, context switches</p>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Main Page ────────────────────────────────────────────────────────────────

export function TasksPage() {
  const [activeTab, setActiveTab] = useState<Tab>('overview')

  // Fetch all data at page level for the overview
  const { data: patternsData, isLoading: patternsLoading } = useQuery({
    queryKey: ['workflow', 'patterns'],
    queryFn: async () => {
      try {
        return (await apiGet<PatternsResponse>('/api/workflow/patterns')).patterns
      } catch { return [] }
    },
  })

  const { data: executionsData, isLoading: executionsLoading } = useQuery({
    queryKey: ['workflow', 'executions'],
    queryFn: async () => {
      try {
        return (await apiGet<ExecutionsResponse>('/api/workflow/executions')).executions ?? []
      } catch { return [] }
    },
    refetchInterval: 10_000,
  })

  const { data: suggestionsData } = useQuery({
    queryKey: ['workflow', 'suggestions'],
    queryFn: async () => {
      try {
        return (await apiGet<SuggestionsResponse>('/api/workflow/suggestions')).suggestions
      } catch { return [] }
    },
  })

  const patterns = patternsData ?? []
  const executions = executionsData ?? []
  const suggestions = suggestionsData ?? []
  const loading = patternsLoading || executionsLoading

  const tabs: { key: Tab; label: string; count?: number }[] = [
    { key: 'overview', label: 'OVERVIEW' },
    { key: 'patterns', label: 'PATTERNS', count: patterns.length },
    { key: 'executions', label: 'EXECUTIONS', count: executions.length },
    { key: 'discover', label: 'DISCOVER' },
  ]

  return (
    <div>
      <DecisionBatcher />

      <div className="flex items-center justify-between mb-1">
        <h2 className="section-title">AUTOMATIONS</h2>
        {suggestions.length > 0 && (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-500/10 border border-amber-500/20">
            <span className="h-1.5 w-1.5 rounded-full bg-amber-400 animate-pulse" />
            <span className="font-mono text-[10px] text-amber-400 tracking-wider">
              {suggestions.length} pending
            </span>
          </span>
        )}
      </div>

      {/* Tab navigation */}
      <div className="flex gap-4 mb-6 overflow-x-auto">
        {tabs.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`font-mono text-[12px] tracking-wider pb-2 transition-colors whitespace-nowrap flex items-center gap-1.5 ${
              activeTab === tab.key
                ? 'text-text-primary border-b-2 border-accent'
                : 'text-text-muted hover:text-text-primary border-b-2 border-transparent'
            }`}
          >
            {tab.label}
            {tab.count !== undefined && (
              <span className="text-[10px] text-text-muted">{tab.count}</span>
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {loading ? <LoadingSkeleton lines={8} /> : (
        <>
          {activeTab === 'overview' && (
            <OverviewTab
              patterns={patterns}
              executions={executions}
              suggestions={suggestions}
              onNavigate={setActiveTab}
            />
          )}
          {activeTab === 'patterns' && <PatternsTab patterns={patterns} />}
          {activeTab === 'executions' && <ExecutionsTab executions={executions} />}
          {activeTab === 'discover' && <DiscoverTab />}
        </>
      )}
    </div>
  )
}
