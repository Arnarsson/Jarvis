import { useEffect, useState } from 'react'
import { apiGet, apiPost } from '../api/client.ts'

/* ───────────────────────── Types ───────────────────────── */

interface PatternAction {
  label: string
  action: 'create_automation' | 'create_project' | 'dismiss'
  params: Record<string, any>
}

interface Pattern {
  id: string
  type: string
  title: string
  description: string
  frequency: string
  confidence: number
  detected_at: string
  occurrence_count: number
  actions: PatternAction[]
}

interface PatternsResponse {
  patterns: Pattern[]
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

/* ───────────────────────── Pattern Card ───────────────────────── */

function PatternCard({ pattern, onDidAction }: { pattern: Pattern; onDidAction: () => void }) {
  const [busyAction, setBusyAction] = useState<string | null>(null)

  const typeConfig = {
    recurring_person: {
      label: 'RECURRING PERSON',
      color: 'text-blue-400',
      bg: 'bg-blue-500/10',
      border: 'border-blue-500/30',
      icon: '👤',
    },
    stale_person: {
      label: 'STALE CONTACT',
      color: 'text-yellow-400',
      bg: 'bg-yellow-500/10',
      border: 'border-yellow-500/30',
      icon: '⏰',
    },
    recurring_topic: {
      label: 'RECURRING TOPIC',
      color: 'text-purple-400',
      bg: 'bg-purple-500/10',
      border: 'border-purple-500/30',
      icon: '💭',
    },
    unfinished_business: {
      label: 'UNFINISHED',
      color: 'text-orange-400',
      bg: 'bg-orange-500/10',
      border: 'border-orange-500/30',
      icon: '⚠️',
    },
    broken_promise: {
      label: 'BROKEN PROMISE',
      color: 'text-red-400',
      bg: 'bg-red-500/10',
      border: 'border-red-500/30',
      icon: '❌',
    },
    stale_project: {
      label: 'STALE PROJECT',
      color: 'text-yellow-400',
      bg: 'bg-yellow-500/10',
      border: 'border-yellow-500/30',
      icon: '📁',
    },
  }[pattern.type] || {
    label: pattern.type.toUpperCase(),
    color: 'text-text-muted',
    bg: 'bg-surface',
    border: 'border-border',
    icon: '·',
  }

  const runAction = async (a: PatternAction) => {
    setBusyAction(a.action)
    try {
      if (a.action === 'create_automation') {
        await apiPost(`/api/patterns/${pattern.id}/convert-automation`)
      } else if (a.action === 'create_project') {
        const name = encodeURIComponent(a.params?.name || pattern.title)
        await apiPost(`/api/patterns/${pattern.id}/convert-project?name=${name}`)
      } else if (a.action === 'dismiss') {
        const snooze = Number(a.params?.snooze_days || 30)
        await apiPost(`/api/patterns/${pattern.id}/dismiss?snooze_days=${encodeURIComponent(String(snooze))}`)
      }
      onDidAction()
    } finally {
      setBusyAction(null)
    }
  }

  return (
    <div className={`border rounded-lg p-4 ${typeConfig.bg} ${typeConfig.border} hover:border-accent/50 transition-colors`}>
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2">
          <span className="text-lg">{typeConfig.icon}</span>
          <h3 className="text-sm font-mono font-semibold text-text-primary">{pattern.title}</h3>
        </div>
        <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${typeConfig.color} bg-black/20 uppercase`}>
          {typeConfig.label}
        </span>
      </div>

      {/* Description */}
      <p className="text-xs text-text-secondary leading-relaxed mb-3">{pattern.description}</p>

      {/* Why/Confidence */}
      <div className="flex items-center justify-between text-[10px] font-mono text-text-muted mb-3">
        <span>
          Frequency: {pattern.frequency} · Mentions: {pattern.occurrence_count}
        </span>
        <span>Confidence: {(pattern.confidence * 100).toFixed(0)}%</span>
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-2">
        {pattern.actions.map((a) => (
          <button
            key={a.action}
            disabled={!!busyAction}
            onClick={() => runAction(a)}
            className={`px-3 py-1.5 text-[11px] font-mono rounded border transition-colors ${
              busyAction === a.action
                ? 'border-border text-text-muted bg-surface'
                : a.action === 'dismiss'
                  ? 'border-border text-text-secondary hover:border-red-500/40 hover:text-red-300'
                  : 'border-border text-text-secondary hover:border-accent/50 hover:text-text-primary'
            }`}
          >
            {busyAction === a.action ? 'Working…' : a.label}
          </button>
        ))}
      </div>

      {/* Footer */}
      <div className="mt-3 flex items-center justify-between text-[10px] font-mono text-text-muted">
        <span>Detected: {timeAgo(pattern.detected_at)}</span>
        <span>id: {pattern.id.slice(0, 8)}</span>
      </div>
    </div>
  )
}

/* ───────────────────────── Main Page ───────────────────────── */

export function PatternsPage() {
  const [allPatterns, setAllPatterns] = useState<Pattern[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filterType, setFilterType] = useState<string | null>(null)

  useEffect(() => {
    fetchPatterns()
  }, [])

  const fetchPatterns = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await apiGet<PatternsResponse>('/api/patterns?limit=100')
      setAllPatterns(data.patterns)
    } catch (e) {
      console.error('Failed to fetch patterns:', e)
      setError('Failed to load patterns')
    } finally {
      setLoading(false)
    }
  }

  const byType = allPatterns.reduce<Record<string, number>>((acc, p) => {
    acc[p.type] = (acc[p.type] || 0) + 1
    return acc
  }, {})\n\n  const patterns = filterType ? allPatterns.filter((p) => p.type === filterType) : allPatterns

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <h1 className="text-2xl font-mono font-bold text-text-primary tracking-wider">🔍 DETECTED PATTERNS</h1>
          {patterns.length > 0 && (
            <span className="text-[10px] font-mono text-text-muted">
              {patterns.length} pattern{patterns.length !== 1 ? 's' : ''}
            </span>
          )}
        </div>
        <p className="text-xs font-mono text-text-muted tracking-wide">
          Recurring themes, people, and unfinished business from your conversations
        </p>
      </div>

      {/* Type Filter */}
      {Object.keys(byType).length > 0 && (
        <div className="flex flex-wrap items-center gap-2 mb-6">
          <span className="text-[10px] font-mono text-text-muted tracking-wider uppercase">FILTER:</span>
          <button
            onClick={() => setFilterType(null)}
            className={`px-3 py-1.5 text-[11px] font-mono rounded border transition-colors ${
              !filterType
                ? 'border-accent text-accent bg-accent/5'
                : 'border-border text-text-secondary hover:border-border-light hover:text-text-primary'
            }`}
          >
            All ({allPatterns.length})
          </button>
          {Object.entries(byType).map(([type, count]) => (
            <button
              key={type}
              onClick={() => setFilterType(type)}
              className={`px-3 py-1.5 text-[11px] font-mono rounded border transition-colors ${
                filterType === type
                  ? 'border-accent text-accent bg-accent/5'
                  : 'border-border text-text-secondary hover:border-border-light hover:text-text-primary'
              }`}
            >
              {type.replace(/_/g, ' ')} ({count})
            </button>
          ))}
        </div>
      )}

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
          Loading patterns…
        </div>
      )}

      {/* Empty State */}
      {!loading && patterns.length === 0 && (
        <div className="border border-border rounded-lg p-8 bg-surface text-center">
          <p className="text-text-muted text-xs font-mono">No patterns detected yet.</p>
        </div>
      )}

      {/* Patterns Grid */}
      {!loading && patterns.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {patterns.map((pattern) => (
            <PatternCard key={pattern.id} pattern={pattern} onDidAction={fetchPatterns} />
          ))}
        </div>
      )}
    </div>
  )
}
