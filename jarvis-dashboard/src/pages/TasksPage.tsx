import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost } from '../api/client.ts'
import { LoadingSkeleton } from '../components/ui/LoadingSkeleton.tsx'
import { DecisionBatcher } from '../components/tasks/DecisionBatcher.tsx'

// --- Types ---

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
}

interface ExecutionsResponse {
  executions: WorkflowExecution[]
  total?: number
}

// --- Tabs ---

type Tab = 'pending' | 'executions' | 'patterns'
type PatternFilter = 'all' | 'active' | 'suspended'

// --- Confidence bar ---

function ConfidenceBar({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100)
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-border/50 h-1.5 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${
            pct >= 80 ? 'bg-success' : pct >= 50 ? 'bg-warning' : 'bg-accent'
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="font-mono text-[11px] text-text-secondary shrink-0">
        {pct}%
      </span>
    </div>
  )
}

// --- Status helpers ---

function statusBgClass(status: string): string {
  switch (status.toLowerCase()) {
    case 'active':
      return 'border-success/40 text-success bg-success/10'
    case 'suspended':
      return 'border-warning/40 text-warning bg-warning/10'
    default:
      return 'border-border text-text-secondary bg-border/30'
  }
}


function tierBgClass(tier: string): string {
  switch (tier.toLowerCase()) {
    case 'auto':
      return 'border-success/40 bg-success/10 text-success'
    case 'suggest':
      return 'border-accent/40 bg-accent/10 text-accent'
    case 'observe':
      return 'border-border bg-border/30 text-text-secondary'
    default:
      return 'border-border bg-border/30 text-text-secondary'
  }
}

// --- Pending Tab ---

function PendingTab() {
  const queryClient = useQueryClient()
  const [actionFeedback, setActionFeedback] = useState<{
    id: string
    type: 'success' | 'error'
    message: string
  } | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['workflow', 'suggestions'],
    queryFn: async () => {
      try {
        const res = await apiGet<SuggestionsResponse>('/api/workflow/suggestions')
        return res.suggestions
      } catch {
        return []
      }
    },
  })

  const approveMutation = useMutation({
    mutationFn: (id: string) =>
      apiPost(`/api/workflow/suggestions/${id}/approve`),
    onSuccess: (_data, id) => {
      setActionFeedback({ id, type: 'success', message: 'Approved' })
      queryClient.invalidateQueries({ queryKey: ['workflow', 'suggestions'] })
      queryClient.invalidateQueries({ queryKey: ['workflow', 'patterns'] })
      queryClient.invalidateQueries({ queryKey: ['workflow', 'executions'] })
      setTimeout(() => setActionFeedback(null), 2000)
    },
    onError: (err, id) => {
      setActionFeedback({
        id,
        type: 'error',
        message: err instanceof Error ? err.message : 'Approve failed',
      })
      setTimeout(() => setActionFeedback(null), 4000)
    },
  })

  const rejectMutation = useMutation({
    mutationFn: (id: string) =>
      apiPost(`/api/workflow/suggestions/${id}/reject`),
    onSuccess: (_data, id) => {
      setActionFeedback({ id, type: 'success', message: 'Rejected' })
      queryClient.invalidateQueries({ queryKey: ['workflow', 'suggestions'] })
      setTimeout(() => setActionFeedback(null), 2000)
    },
    onError: (err, id) => {
      setActionFeedback({
        id,
        type: 'error',
        message: err instanceof Error ? err.message : 'Reject failed',
      })
      setTimeout(() => setActionFeedback(null), 4000)
    },
  })

  if (isLoading) {
    return <LoadingSkeleton lines={4} />
  }

  if (!data || data.length === 0) {
    return (
      <p className="text-sm text-text-secondary py-6">
        No pending decisions &mdash; all clear
      </p>
    )
  }

  return (
    <div className="space-y-0">
      {data.map((suggestion) => (
        <div
          key={suggestion.id}
          className="py-5 border-b border-border/50 last:border-b-0"
        >
          {/* Name + description */}
          <p className="text-[15px] text-text-primary font-medium">
            {suggestion.name}
          </p>
          <p className="text-[12px] text-text-secondary mt-1">
            {suggestion.description || suggestion.pattern_type}
          </p>

          {/* Confidence bar */}
          <div className="mt-3">
            <ConfidenceBar confidence={suggestion.confidence} />
          </div>

          {/* Trigger + Action details */}
          <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2">
            <div>
              <span className="font-mono text-[10px] tracking-wider text-text-secondary uppercase">
                Trigger
              </span>
              <p className="text-[13px] text-text-primary mt-0.5">
                {suggestion.trigger_description}
              </p>
            </div>
            <div>
              <span className="font-mono text-[10px] tracking-wider text-text-secondary uppercase">
                Action
              </span>
              <p className="text-[13px] text-text-primary mt-0.5">
                {suggestion.action_description}
              </p>
            </div>
          </div>

          {/* Action buttons */}
          <div className="mt-4 flex flex-col sm:flex-row items-start gap-2">
            <button
              type="button"
              onClick={() => approveMutation.mutate(suggestion.id)}
              disabled={approveMutation.isPending || rejectMutation.isPending}
              className="font-mono text-[12px] tracking-wider font-bold px-4 py-2 border border-accent text-accent hover:bg-accent/10 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {approveMutation.isPending && approveMutation.variables === suggestion.id
                ? 'APPROVING...'
                : 'APPROVE'}
            </button>
            <button
              type="button"
              onClick={() => rejectMutation.mutate(suggestion.id)}
              disabled={rejectMutation.isPending || approveMutation.isPending}
              className="font-mono text-[12px] tracking-wider font-bold px-4 py-2 border border-border text-text-secondary hover:text-text-primary hover:border-border-light transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {rejectMutation.isPending && rejectMutation.variables === suggestion.id
                ? 'REJECTING...'
                : 'REJECT'}
            </button>
            {actionFeedback?.id === suggestion.id && (
              <span
                className={`font-mono text-[11px] tracking-wider px-3 py-2 ${
                  actionFeedback.type === 'success'
                    ? 'text-success'
                    : 'text-accent'
                }`}
              >
                {actionFeedback.message}
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

// --- Executions Tab ---

function executionStatusClass(status: string): string {
  switch (status.toLowerCase()) {
    case 'completed':
      return 'border-success/40 text-success bg-success/10'
    case 'running':
    case 'pending':
      return 'border-accent/40 text-accent bg-accent/10'
    case 'failed':
      return 'border-red-500/40 text-red-400 bg-red-500/10'
    case 'cancelled':
      return 'border-warning/40 text-warning bg-warning/10'
    default:
      return 'border-border text-text-secondary bg-border/30'
  }
}

function formatTimestamp(ts: string): string {
  try {
    const d = new Date(ts)
    return d.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    })
  } catch {
    return ts
  }
}

function ExecutionsTab() {
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['workflow', 'executions'],
    queryFn: async () => {
      try {
        const res = await apiGet<ExecutionsResponse>('/api/workflow/executions')
        return res.executions ?? []
      } catch {
        return []
      }
    },
    refetchInterval: 10_000, // poll for running executions
  })

  // Fetch detail for expanded execution
  const { data: detail } = useQuery({
    queryKey: ['workflow', 'executions', expandedId],
    queryFn: async () => {
      if (!expandedId) return null
      try {
        return await apiGet<WorkflowExecution>(
          `/api/workflow/executions/${expandedId}`
        )
      } catch {
        return null
      }
    },
    enabled: !!expandedId,
    refetchInterval: (query) => {
      const d = query.state.data
      if (d && (d.status === 'running' || d.status === 'pending')) return 3_000
      return false
    },
  })

  if (isLoading) return <LoadingSkeleton lines={4} />

  if (!data || data.length === 0) {
    return (
      <p className="text-sm text-text-secondary py-6">
        No executions yet &mdash; approve a suggestion to trigger one
      </p>
    )
  }

  return (
    <div className="space-y-0">
      {data.map((exec) => {
        const isExpanded = expandedId === exec.id
        const displayExec = isExpanded && detail ? detail : exec
        const isLive =
          displayExec.status === 'running' || displayExec.status === 'pending'

        return (
          <div
            key={exec.id}
            className="py-4 border-b border-border/50 last:border-b-0 cursor-pointer"
            onClick={() => setExpandedId(isExpanded ? null : exec.id)}
          >
            {/* Header row */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
              <div className="flex items-center gap-3">
                <p className="text-[15px] text-text-primary font-medium">
                  {exec.pattern_name || exec.pattern_id}
                </p>
                {isLive && (
                  <span className="inline-block w-2 h-2 rounded-full bg-accent animate-pulse" />
                )}
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <span
                  className={`inline-flex items-center font-mono text-[10px] tracking-wider px-2.5 py-1 border ${executionStatusClass(displayExec.status)}`}
                >
                  {displayExec.status.toUpperCase()}
                </span>
                <span className="font-mono text-[11px] text-text-secondary">
                  {formatTimestamp(exec.started_at)}
                </span>
              </div>
            </div>

            {/* Expanded detail */}
            {isExpanded && (
              <div className="mt-3 pl-2 space-y-2 text-[13px]">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2">
                  <div>
                    <span className="font-mono text-[10px] tracking-wider text-text-secondary uppercase">
                      Started
                    </span>
                    <p className="text-text-primary mt-0.5">
                      {formatTimestamp(displayExec.started_at)}
                    </p>
                  </div>
                  {displayExec.completed_at && (
                    <div>
                      <span className="font-mono text-[10px] tracking-wider text-text-secondary uppercase">
                        Completed
                      </span>
                      <p className="text-text-primary mt-0.5">
                        {formatTimestamp(displayExec.completed_at)}
                      </p>
                    </div>
                  )}
                </div>
                {displayExec.result && (
                  <div>
                    <span className="font-mono text-[10px] tracking-wider text-text-secondary uppercase">
                      Result
                    </span>
                    <p className="text-text-primary mt-0.5 whitespace-pre-wrap bg-surface/50 border border-border/30 rounded px-3 py-2 font-mono text-[12px]">
                      {displayExec.result}
                    </p>
                  </div>
                )}
                {displayExec.error && (
                  <div>
                    <span className="font-mono text-[10px] tracking-wider text-red-400 uppercase">
                      Error
                    </span>
                    <p className="text-red-400 mt-0.5 whitespace-pre-wrap bg-red-500/5 border border-red-500/20 rounded px-3 py-2 font-mono text-[12px]">
                      {displayExec.error}
                    </p>
                  </div>
                )}
                <p className="font-mono text-[10px] text-text-muted">
                  ID: {exec.id}
                </p>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// --- Patterns Tab ---

function PatternsTab() {
  const [filter, setFilter] = useState<PatternFilter>('all')
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['workflow', 'patterns', filter],
    queryFn: async () => {
      try {
        const params = new URLSearchParams()
        if (filter === 'active') {
          params.set('active_only', 'true')
        }
        const qs = params.toString()
        const res = await apiGet<PatternsResponse>(
          `/api/workflow/patterns${qs ? `?${qs}` : ''}`
        )
        return res.patterns
      } catch {
        return []
      }
    },
  })

  const promoteMutation = useMutation({
    mutationFn: ({ id, tier }: { id: string; tier: string }) =>
      apiPost(`/api/workflow/patterns/${id}/promote?tier=${encodeURIComponent(tier)}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflow', 'patterns'] })
    },
  })

  const suspendMutation = useMutation({
    mutationFn: (id: string) =>
      apiPost(`/api/workflow/patterns/${id}/suspend?reason=${encodeURIComponent('Suspended from dashboard')}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflow', 'patterns'] })
    },
  })

  // Client-side filter for suspended (API may not support status param directly)
  const filtered = (data ?? []).filter((p) => {
    if (filter === 'suspended') return p.status.toLowerCase() === 'suspended'
    return true
  })

  const nextTier = (current: string): string => {
    switch (current.toLowerCase()) {
      case 'observe':
        return 'suggest'
      case 'suggest':
        return 'auto'
      default:
        return current
    }
  }

  const filterButtons: { key: PatternFilter; label: string }[] = [
    { key: 'all', label: 'ALL' },
    { key: 'active', label: 'ACTIVE' },
    { key: 'suspended', label: 'SUSPENDED' },
  ]

  return (
    <div>
      {/* Filter row */}
      <div className="flex gap-2 mb-4">
        {filterButtons.map((btn) => (
          <button
            key={btn.key}
            onClick={() => setFilter(btn.key)}
            className={`font-mono text-[11px] tracking-wider px-3 py-1.5 border transition-colors ${
              filter === btn.key
                ? 'border-accent text-accent bg-accent/10'
                : 'border-border text-text-secondary hover:text-text-primary hover:border-border-light'
            }`}
          >
            {btn.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <LoadingSkeleton lines={4} />
      ) : filtered.length === 0 ? (
        <p className="text-sm text-text-secondary py-6">
          No workflow patterns detected yet
        </p>
      ) : (
        <div className="space-y-0">
          {filtered.map((pattern) => {
            const isActive = pattern.status.toLowerCase() === 'active'
            const isAuto = pattern.trust_tier.toLowerCase() === 'auto'

            return (
              <div
                key={pattern.id}
                className="py-5 border-b border-border/50 last:border-b-0"
              >
                {/* Name + badges row */}
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                  <p className="text-[15px] text-text-primary font-medium">
                    {pattern.name}
                  </p>
                  <div className="flex items-center gap-2 shrink-0">
                    {/* Status badge */}
                    <span
                      className={`inline-flex items-center font-mono text-[10px] tracking-wider px-2.5 py-1 border ${statusBgClass(pattern.status)}`}
                    >
                      {pattern.status.toUpperCase()}
                    </span>
                    {/* Trust tier badge */}
                    <span
                      className={`inline-flex items-center font-mono text-[10px] tracking-wider px-2.5 py-1 border ${tierBgClass(pattern.trust_tier)}`}
                    >
                      {pattern.trust_tier.toUpperCase()}
                    </span>
                  </div>
                </div>

                {/* Description */}
                {pattern.description && (
                  <p className="text-[12px] text-text-secondary mt-1">
                    {pattern.description}
                  </p>
                )}

                {/* Confidence */}
                <div className="mt-3 flex items-center gap-2">
                  <span className="font-mono text-[10px] tracking-wider text-text-secondary uppercase">
                    Confidence
                  </span>
                  <div className="flex-1 max-w-xs">
                    <ConfidenceBar confidence={pattern.confidence} />
                  </div>
                </div>

                {/* Action buttons */}
                <div className="mt-4 flex flex-col sm:flex-row gap-2">
                  {!isAuto && (
                    <button
                      onClick={() =>
                        promoteMutation.mutate({
                          id: pattern.id,
                          tier: nextTier(pattern.trust_tier),
                        })
                      }
                      disabled={promoteMutation.isPending}
                      className="font-mono text-[12px] tracking-wider font-bold px-4 py-2 border border-accent text-accent hover:bg-accent/10 transition-colors disabled:opacity-50"
                    >
                      PROMOTE
                    </button>
                  )}
                  {isActive && (
                    <button
                      onClick={() => suspendMutation.mutate(pattern.id)}
                      disabled={suspendMutation.isPending}
                      className="font-mono text-[12px] tracking-wider font-bold px-4 py-2 border border-warning/50 text-warning hover:bg-warning/10 transition-colors disabled:opacity-50"
                    >
                      SUSPEND
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// --- Main Page ---

export function TasksPage() {
  const [activeTab, setActiveTab] = useState<Tab>('pending')

  const tabs: { key: Tab; label: string }[] = [
    { key: 'pending', label: 'PENDING' },
    { key: 'executions', label: 'EXECUTIONS' },
    { key: 'patterns', label: 'PATTERNS' },
  ]

  return (
    <div>
      <DecisionBatcher />

      <h3 className="section-title">TASKS</h3>

      {/* Tab navigation */}
      <div className="flex gap-6 mb-6">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`font-mono text-[13px] tracking-wider pb-2 transition-colors ${
              activeTab === tab.key
                ? 'text-text-primary border-b-2 border-accent'
                : 'text-text-secondary hover:text-text-primary border-b-2 border-transparent'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'pending' && <PendingTab />}
      {activeTab === 'executions' && <ExecutionsTab />}
      {activeTab === 'patterns' && <PatternsTab />}
    </div>
  )
}
