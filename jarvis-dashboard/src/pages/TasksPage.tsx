import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost } from '../api/client.ts'
import { LoadingSkeleton } from '../components/ui/LoadingSkeleton.tsx'

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

// --- Tabs ---

type Tab = 'pending' | 'patterns'
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
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflow', 'suggestions'] })
    },
  })

  const rejectMutation = useMutation({
    mutationFn: (id: string) =>
      apiPost(`/api/workflow/suggestions/${id}/reject`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflow', 'suggestions'] })
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
          <div className="mt-4 flex flex-col sm:flex-row gap-2">
            <button
              onClick={() => approveMutation.mutate(suggestion.id)}
              disabled={approveMutation.isPending}
              className="font-mono text-[12px] tracking-wider font-bold px-4 py-2 border border-accent text-accent hover:bg-accent/10 transition-colors disabled:opacity-50"
            >
              APPROVE
            </button>
            <button
              onClick={() => rejectMutation.mutate(suggestion.id)}
              disabled={rejectMutation.isPending}
              className="font-mono text-[12px] tracking-wider font-bold px-4 py-2 border border-border text-text-secondary hover:text-text-primary hover:border-border-light transition-colors disabled:opacity-50"
            >
              REJECT
            </button>
          </div>
        </div>
      ))}
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
      apiPost(`/api/workflow/patterns/${id}/promote`, { tier }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflow', 'patterns'] })
    },
  })

  const suspendMutation = useMutation({
    mutationFn: (id: string) =>
      apiPost(`/api/workflow/patterns/${id}/suspend`, {
        reason: 'Suspended from dashboard',
      }),
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
    { key: 'patterns', label: 'PATTERNS' },
  ]

  return (
    <div>
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
      {activeTab === 'pending' ? <PendingTab /> : <PatternsTab />}
    </div>
  )
}
