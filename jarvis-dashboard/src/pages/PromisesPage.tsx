import { useState, useEffect } from 'react'
import { apiGet } from '../api/client.ts'

/* ───────────────────────── Types ───────────────────────── */

interface Promise {
  id: string
  text: string
  source_conversation_id: string | null
  detected_at: string
  due_by: string | null
  status: string
  fulfilled_at: string | null
}

interface PromisesResponse {
  promises: Promise[]
  total: number
}

/* ───────────────────────── Helpers ───────────────────────── */

function timeAgo(isoDate: string): string {
  try {
    const now = Date.now()
    const then = new Date(isoDate).getTime()
    const diffMs = now - then
    const diffMin = Math.floor(diffMs / 60000)
    const diffHr = Math.floor(diffMs / 3600000)
    const diffDay = Math.floor(diffMs / 86400000)

    if (diffMin < 1) return 'just now'
    if (diffMin < 60) return `${diffMin}m ago`
    if (diffHr < 24) return `${diffHr}h ago`
    if (diffDay === 1) return 'yesterday'
    if (diffDay < 7) return `${diffDay}d ago`
    if (diffDay < 30) return `${diffDay}d ago`
    
    const months = Math.floor(diffDay / 30)
    return `${months}mo ago`
  } catch {
    return ''
  }
}

function formatFullDate(isoDate: string): string {
  try {
    const d = new Date(isoDate)
    return d.toLocaleDateString('en-US', { 
      month: 'long', 
      day: 'numeric', 
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return ''
  }
}

function getDaysOverdue(dueDateIso: string): number {
  try {
    const now = Date.now()
    const due = new Date(dueDateIso).getTime()
    const diffMs = now - due
    const diffDays = Math.floor(diffMs / 86400000)
    return diffDays
  } catch {
    return 0
  }
}

/* ───────────────────────── Promise Card ───────────────────────── */

function PromiseCard({ promise }: { promise: Promise }) {
  const statusConfig = {
    pending: { 
      label: 'PENDING', 
      color: 'text-orange-400', 
      bg: 'bg-orange-500/10', 
      border: 'border-orange-500/30' 
    },
    fulfilled: { 
      label: 'FULFILLED', 
      color: 'text-emerald-400', 
      bg: 'bg-emerald-500/10', 
      border: 'border-emerald-500/30' 
    },
    broken: { 
      label: 'BROKEN', 
      color: 'text-red-400', 
      bg: 'bg-red-500/10', 
      border: 'border-red-500/30' 
    },
  }[promise.status] || { 
    label: promise.status.toUpperCase(), 
    color: 'text-text-muted', 
    bg: 'bg-surface', 
    border: 'border-border' 
  }

  const age = timeAgo(promise.detected_at)
  const isOverdue = promise.due_by && promise.status === 'pending' && getDaysOverdue(promise.due_by) > 0
  const daysOverdue = promise.due_by ? getDaysOverdue(promise.due_by) : 0

  return (
    <div className={`border rounded-lg p-4 ${statusConfig.bg} ${statusConfig.border} hover:border-accent/50 transition-colors`}>
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono text-text-muted" title={formatFullDate(promise.detected_at)}>
            {age}
          </span>
          {isOverdue && (
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded text-red-400 bg-red-500/20">
              {daysOverdue}d overdue
            </span>
          )}
        </div>
        <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${statusConfig.color} bg-black/20`}>
          {statusConfig.label}
        </span>
      </div>

      {/* Text */}
      <p className="text-sm text-text-primary leading-relaxed mb-3">
        {promise.text}
      </p>

      {/* Footer */}
      <div className="flex items-center justify-between text-[10px] font-mono text-text-muted">
        <div>
          {promise.due_by && (
            <span>Due: {new Date(promise.due_by).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span>
          )}
        </div>
        {promise.fulfilled_at && (
          <span>Fulfilled: {timeAgo(promise.fulfilled_at)}</span>
        )}
      </div>
    </div>
  )
}

/* ───────────────────────── Main Page ───────────────────────── */

export function PromisesPage() {
  const [promises, setPromises] = useState<Promise[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<string | null>(null)

  // Fetch promises on mount and when filter changes
  useEffect(() => {
    fetchPromises()
  }, [statusFilter])

  const fetchPromises = async () => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      if (statusFilter) params.append('status', statusFilter)
      params.append('limit', '100')
      
      const data = await apiGet<PromisesResponse>(`/api/v2/promises?${params}`)
      setPromises(data.promises)
    } catch (e) {
      console.error('Failed to fetch promises:', e)
      setError('Failed to load promises')
    } finally {
      setLoading(false)
    }
  }

  const pendingCount = promises.filter(p => p.status === 'pending').length
  const overdueCount = promises.filter(p => 
    p.status === 'pending' && p.due_by && getDaysOverdue(p.due_by) > 0
  ).length

  return (
    <div className="max-w-3xl">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <h1 className="text-lg font-mono font-bold text-text-primary tracking-wider">
            🤝 PROMISE TRACKER
          </h1>
          {promises.length > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono text-text-muted">
                {promises.length} total
              </span>
              {pendingCount > 0 && (
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded text-orange-400 bg-orange-500/20">
                  {pendingCount} pending
                </span>
              )}
              {overdueCount > 0 && (
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded text-red-400 bg-red-500/20">
                  {overdueCount} overdue
                </span>
              )}
            </div>
          )}
        </div>
        <p className="text-xs font-mono text-text-muted tracking-wide">
          Track commitments and promises from conversations
        </p>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2 mb-6">
        <span className="text-[10px] font-mono text-text-muted tracking-wider uppercase">
          FILTER:
        </span>
        {[
          { value: null, label: 'All' },
          { value: 'pending', label: 'Pending' },
          { value: 'fulfilled', label: 'Fulfilled' },
          { value: 'broken', label: 'Broken' },
        ].map((opt) => (
          <button
            key={opt.value || 'all'}
            onClick={() => setStatusFilter(opt.value)}
            className={`px-3 py-1.5 text-[11px] font-mono rounded border transition-colors ${
              statusFilter === opt.value
                ? 'border-accent text-accent bg-accent/5'
                : 'border-border text-text-secondary hover:border-border-light hover:text-text-primary'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* Error */}
      {error && (
        <div className="mb-6 border border-red-500/20 rounded-lg p-4 bg-red-500/5">
          <p className="text-red-400/70 text-xs font-mono">{error}</p>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center gap-2 text-text-muted text-xs font-mono py-8">
          <span className="inline-block h-2 w-2 rounded-full bg-accent animate-pulse" />
          Loading promises…
        </div>
      )}

      {/* Empty State */}
      {!loading && promises.length === 0 && (
        <div className="border border-border/30 rounded-lg p-10 text-center">
          <div className="text-3xl mb-4">🤝</div>
          <p className="text-sm font-mono text-text-secondary mb-2">
            No promises found
          </p>
          <p className="text-xs font-mono text-text-muted">
            {statusFilter 
              ? `No ${statusFilter} promises to display`
              : 'Promises will appear here as they are detected in conversations'}
          </p>
        </div>
      )}

      {/* Promises List */}
      {!loading && promises.length > 0 && (
        <div className="space-y-3">
          {promises.map((promise) => (
            <PromiseCard key={promise.id} promise={promise} />
          ))}
        </div>
      )}
    </div>
  )
}
