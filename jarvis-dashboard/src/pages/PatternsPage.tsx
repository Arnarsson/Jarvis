import { useState, useEffect } from 'react'
import { apiGet } from '../api/client.ts'

/* ───────────────────────── Types ───────────────────────── */

interface Pattern {
  id: string
  pattern_type: string
  pattern_key: string
  description: string
  frequency: number
  first_seen: string
  last_seen: string
  suggested_action: string | null
  conversation_ids: string[]
  detected_at: string
  status: string
}

interface PatternsResponse {
  patterns: Pattern[]
  total: number
  by_type: Record<string, number>
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

function PatternCard({ pattern }: { pattern: Pattern }) {
  const typeConfig = {
    recurring_person: { 
      label: 'RECURRING PERSON', 
      color: 'text-blue-400', 
      bg: 'bg-blue-500/10', 
      border: 'border-blue-500/30',
      icon: '👤'
    },
    stale_person: { 
      label: 'STALE CONTACT', 
      color: 'text-yellow-400', 
      bg: 'bg-yellow-500/10', 
      border: 'border-yellow-500/30',
      icon: '⏰'
    },
    recurring_topic: { 
      label: 'RECURRING TOPIC', 
      color: 'text-purple-400', 
      bg: 'bg-purple-500/10', 
      border: 'border-purple-500/30',
      icon: '💭'
    },
    unfinished_business: { 
      label: 'UNFINISHED', 
      color: 'text-orange-400', 
      bg: 'bg-orange-500/10', 
      border: 'border-orange-500/30',
      icon: '⚠️'
    },
    broken_promise: { 
      label: 'BROKEN PROMISE', 
      color: 'text-red-400', 
      bg: 'bg-red-500/10', 
      border: 'border-red-500/30',
      icon: '❌'
    },
    stale_project: { 
      label: 'STALE PROJECT', 
      color: 'text-yellow-400', 
      bg: 'bg-yellow-500/10', 
      border: 'border-yellow-500/30',
      icon: '📁'
    },
  }[pattern.pattern_type] || { 
    label: pattern.pattern_type.toUpperCase(), 
    color: 'text-text-muted', 
    bg: 'bg-surface', 
    border: 'border-border',
    icon: '·'
  }

  return (
    <div className={`border rounded-lg p-4 ${typeConfig.bg} ${typeConfig.border} hover:border-accent/50 transition-colors`}>
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2">
          <span className="text-lg">{typeConfig.icon}</span>
          <h3 className="text-sm font-mono font-semibold text-text-primary">
            {pattern.pattern_key}
          </h3>
        </div>
        <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${typeConfig.color} bg-black/20 uppercase`}>
          {typeConfig.label}
        </span>
      </div>

      {/* Description */}
      <p className="text-xs text-text-secondary leading-relaxed mb-3">
        {pattern.description}
      </p>

      {/* Suggested Action */}
      {pattern.suggested_action && (
        <div className="mb-3 p-2 rounded bg-accent/10 border border-accent/20">
          <p className="text-[11px] font-mono text-accent">
            💡 {pattern.suggested_action}
          </p>
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between text-[10px] font-mono text-text-muted">
        <div className="flex items-center gap-3">
          <span>Last seen: {timeAgo(pattern.last_seen)}</span>
          <span>Mentions: {pattern.frequency}</span>
        </div>
        <span>{pattern.conversation_ids.length} convos</span>
      </div>
    </div>
  )
}

/* ───────────────────────── Main Page ───────────────────────── */

export function PatternsPage() {
  const [patterns, setPatterns] = useState<Pattern[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filterType, setFilterType] = useState<string | null>(null)
  const [byType, setByType] = useState<Record<string, number>>({})

  useEffect(() => {
    fetchPatterns()
  }, [filterType])

  const fetchPatterns = async () => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      if (filterType) params.append('pattern_type', filterType)
      params.append('limit', '100')
      
      const data = await apiGet<PatternsResponse>(`/api/v2/patterns?${params}`)
      setPatterns(data.patterns)
      setByType(data.by_type)
    } catch (e) {
      console.error('Failed to fetch patterns:', e)
      setError('Failed to load patterns')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <h1 className="text-2xl font-mono font-bold text-text-primary tracking-wider">
            🔍 DETECTED PATTERNS
          </h1>
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
          <span className="text-[10px] font-mono text-text-muted tracking-wider uppercase">
            FILTER:
          </span>
          <button
            onClick={() => setFilterType(null)}
            className={`px-3 py-1.5 text-[11px] font-mono rounded border transition-colors ${
              !filterType
                ? 'border-accent text-accent bg-accent/5'
                : 'border-border text-text-secondary hover:border-border-light hover:text-text-primary'
            }`}
          >
            All ({patterns.length})
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
        <div className="border border-border/30 rounded-lg p-10 text-center">
          <div className="text-3xl mb-4">🔍</div>
          <p className="text-sm font-mono text-text-secondary mb-2">
            No patterns detected yet
          </p>
          <p className="text-xs font-mono text-text-muted">
            Run the pattern detector to analyze your conversation history
          </p>
        </div>
      )}

      {/* Patterns Grid */}
      {!loading && patterns.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {patterns.map((pattern) => (
            <PatternCard key={pattern.id} pattern={pattern} />
          ))}
        </div>
      )}
    </div>
  )
}
