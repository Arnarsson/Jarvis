import { useState, useEffect, useCallback, useRef } from 'react'
import { apiGet, apiPost } from '../api/client.ts'

/* ───────────────────────── Types ───────────────────────── */

interface SearchResult {
  id: string
  text_preview: string
  timestamp: string
  score: number
  source?: string
  filepath?: string | null
}

interface SearchResponse {
  results: SearchResult[]
  total?: number
  query?: string
}

interface ParsedConversation {
  title: string
  userMessage: string
  assistantMessage: string
}

/* ───────────────────────── Helpers ───────────────────────── */

function parseTextPreview(text: string): ParsedConversation {
  let title = ''
  let userMessage = ''
  let assistantMessage = ''

  // Extract title
  const titleMatch = text.match(/^Title:\s*(.+?)(?:\n|$)/)
  if (titleMatch) {
    title = titleMatch[1].trim()
  }

  // Extract USER message
  const userMatch = text.match(/USER:\s*([\s\S]*?)(?=\nASSISTANT:|\n\n[A-Z]|$)/)
  if (userMatch) {
    userMessage = userMatch[1].trim()
    // Clean up: limit to first meaningful chunk
    if (userMessage.length > 300) {
      userMessage = userMessage.slice(0, 300).replace(/\s+\S*$/, '') + '…'
    }
  }

  // Extract ASSISTANT message
  const assistantMatch = text.match(/ASSISTANT:\s*([\s\S]*)$/)
  if (assistantMatch) {
    assistantMessage = assistantMatch[1].trim()
    if (assistantMessage.length > 400) {
      assistantMessage = assistantMessage.slice(0, 400).replace(/\s+\S*$/, '') + '…'
    }
  }

  // Fallback: if no structured data found, use the whole preview
  if (!title && !userMessage && !assistantMessage) {
    const cleaned = text.trim()
    if (cleaned.length > 400) {
      userMessage = cleaned.slice(0, 400) + '…'
    } else {
      userMessage = cleaned
    }
    title = 'Conversation'
  }

  return { title: title || 'Untitled conversation', userMessage, assistantMessage }
}

function timeAgo(ts: string): string {
  try {
    const now = Date.now()
    const then = new Date(ts).getTime()
    const diffMs = now - then
    const diffMin = Math.floor(diffMs / 60000)
    const diffHr = Math.floor(diffMs / 3600000)
    const diffDay = Math.floor(diffMs / 86400000)
    const diffWeek = Math.floor(diffDay / 7)
    const diffMonth = Math.floor(diffDay / 30)

    if (diffMin < 1) return 'just now'
    if (diffMin < 60) return `${diffMin}m ago`
    if (diffHr < 24) return `${diffHr}h ago`
    if (diffDay === 1) return 'yesterday'
    if (diffDay < 7) return `${diffDay}d ago`
    if (diffWeek < 5) return `${diffWeek}w ago`
    if (diffMonth < 12) return `${diffMonth}mo ago`

    const d = new Date(ts)
    return d.toLocaleDateString('en-GB', { month: 'short', year: 'numeric' })
  } catch {
    return ''
  }
}

function formatFullDate(ts: string): string {
  try {
    const d = new Date(ts)
    return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

function sourceConfig(source?: string): { label: string; color: string; accent: string; icon: string; bg: string } {
  switch (source?.toLowerCase()) {
    case 'chatgpt':
      return {
        label: 'ChatGPT',
        color: 'text-emerald-400',
        accent: 'border-emerald-500/40',
        bg: 'bg-emerald-500/8',
        icon: '◉',
      }
    case 'claude':
      return {
        label: 'Claude',
        color: 'text-orange-400',
        accent: 'border-orange-500/40',
        bg: 'bg-orange-500/8',
        icon: '◈',
      }
    default:
      return {
        label: 'Unknown',
        color: 'text-neutral-400',
        accent: 'border-neutral-500/30',
        bg: 'bg-neutral-500/8',
        icon: '○',
      }
  }
}

/* ───────────────────── Suggested Searches ───────────────────── */

const SUGGESTED_SEARCHES = [
  { label: '🧠 Recent decisions', query: 'decisions and conclusions reached' },
  { label: '🏗️ Project discussions', query: 'project architecture and development' },
  { label: '👥 People mentioned', query: 'people names mentioned in conversations' },
  { label: '🔧 Technical problems', query: 'bugs errors technical issues debugging' },
  { label: '📋 Action items', query: 'tasks to do action items next steps' },
  { label: '💡 Ideas & brainstorms', query: 'ideas brainstorming creative concepts' },
]

/* ───────────────────── Relevance Bar ───────────────────── */

function RelevanceBar({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const width = Math.max(pct, 8)
  const color = pct >= 70 ? 'bg-emerald-500' : pct >= 40 ? 'bg-amber-500' : 'bg-neutral-500'

  return (
    <div className="flex items-center gap-2 shrink-0">
      <div className="w-16 h-1.5 rounded-full bg-neutral-800 overflow-hidden">
        <div className={`h-full rounded-full ${color} transition-all duration-300`} style={{ width: `${width}%` }} />
      </div>
      <span className="text-[10px] font-mono text-text-muted tabular-nums">{pct}%</span>
    </div>
  )
}

/* ───────────────────── Conversation Card ───────────────────── */

function ConversationCard({ result }: { result: SearchResult }) {
  const parsed = parseTextPreview(result.text_preview)
  const src = sourceConfig(result.source)
  const [expanded, setExpanded] = useState(false)

  return (
    <div
      className={`border rounded-lg overflow-hidden transition-all duration-200 hover:border-border-light ${src.accent} ${src.bg}`}
    >
      {/* Header */}
      <div className="px-4 pt-3.5 pb-2 flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <span className={`text-sm ${src.color}`}>{src.icon}</span>
          <h3 className="text-sm font-mono font-semibold text-text-primary truncate">
            {parsed.title}
          </h3>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <RelevanceBar score={result.score} />
          <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${src.color} bg-black/20`}>
            {src.label}
          </span>
        </div>
      </div>

      {/* Conversation bubbles */}
      <div className="px-4 pb-3 space-y-2">
        {parsed.userMessage && (
          <div className="flex justify-end">
            <div className="max-w-[85%] rounded-xl rounded-tr-sm bg-blue-600/15 border border-blue-500/20 px-3.5 py-2.5">
              <p className="text-[10px] font-mono text-blue-400/70 mb-1 tracking-wider">YOU</p>
              <p className="text-xs text-text-secondary leading-relaxed">
                {expanded ? parsed.userMessage : (
                  parsed.userMessage.length > 150
                    ? parsed.userMessage.slice(0, 150).replace(/\s+\S*$/, '') + '…'
                    : parsed.userMessage
                )}
              </p>
            </div>
          </div>
        )}

        {parsed.assistantMessage && (
          <div className="flex justify-start">
            <div className={`max-w-[85%] rounded-xl rounded-tl-sm border px-3.5 py-2.5 ${
              result.source === 'chatgpt'
                ? 'bg-emerald-600/10 border-emerald-500/15'
                : 'bg-orange-600/10 border-orange-500/15'
            }`}>
              <p className={`text-[10px] font-mono mb-1 tracking-wider ${src.color} opacity-70`}>
                {src.label.toUpperCase()}
              </p>
              <p className="text-xs text-text-secondary leading-relaxed">
                {expanded ? parsed.assistantMessage : (
                  parsed.assistantMessage.length > 200
                    ? parsed.assistantMessage.slice(0, 200).replace(/\s+\S*$/, '') + '…'
                    : parsed.assistantMessage
                )}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-4 pb-3 flex items-center justify-between">
        <span className="text-[10px] font-mono text-text-muted" title={formatFullDate(result.timestamp)}>
          {timeAgo(result.timestamp)}
        </span>
        {(parsed.userMessage.length > 150 || parsed.assistantMessage.length > 200) && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-[10px] font-mono text-text-muted hover:text-text-primary transition-colors"
          >
            {expanded ? '↑ collapse' : '↓ expand'}
          </button>
        )}
      </div>
    </div>
  )
}

/* ───────────────────── Search Section ───────────────────── */

function SearchSection() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [total, setTotal] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  const doSearch = useCallback(async (q: string) => {
    if (!q.trim()) { setResults([]); setSearched(false); setTotal(null); setError(null); return }
    setLoading(true)
    setSearched(true)
    setError(null)
    try {
      const data = await apiPost<SearchResponse>('/api/search/', { query: q.trim(), limit: 20 })
      setResults(data.results ?? [])
      setTotal(data.total ?? null)
    } catch (e) {
      console.error('Search failed:', e)
      setResults([])
      setTotal(null)
      setError('Search unavailable — is the memory backend running?')
    } finally {
      setLoading(false)
    }
  }, [])

  const handleInput = (val: string) => {
    setQuery(val)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => doSearch(val), 400)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (debounceRef.current) clearTimeout(debounceRef.current)
    doSearch(query)
  }

  const handleSuggestion = (q: string) => {
    setQuery(q)
    doSearch(q)
  }

  return (
    <section className="mb-10">
      {/* Search bar */}
      <form onSubmit={handleSubmit} className="relative mb-4">
        <div className="flex items-center border border-border rounded-lg bg-surface overflow-hidden focus-within:border-accent transition-colors">
          <span className="pl-4 text-text-muted">
            <svg width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.35-4.35" strokeLinecap="round" />
            </svg>
          </span>
          <input
            type="text"
            value={query}
            onChange={(e) => handleInput(e.target.value)}
            placeholder="Search your memory — conversations, decisions, people, anything…"
            className="flex-1 bg-transparent px-4 py-3.5 text-sm text-text-primary placeholder:text-text-muted font-mono outline-none"
            autoFocus
          />
          {query && (
            <button
              type="button"
              onClick={() => { setQuery(''); setResults([]); setSearched(false); setTotal(null); setError(null) }}
              className="pr-2 text-text-muted hover:text-text-primary transition-colors"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M18 6 6 18M6 6l12 12" strokeLinecap="round" />
              </svg>
            </button>
          )}
          <button
            type="submit"
            className="px-5 py-3.5 text-xs font-mono tracking-wider text-accent hover:text-red-400 transition-colors border-l border-border"
          >
            SEARCH
          </button>
        </div>
      </form>

      {/* Suggested searches */}
      {!searched && (
        <div className="flex flex-wrap gap-2 mb-6">
          {SUGGESTED_SEARCHES.map((s) => (
            <button
              key={s.query}
              onClick={() => handleSuggestion(s.query)}
              className="px-3 py-1.5 rounded-full text-[11px] font-mono text-text-muted bg-surface border border-border hover:border-accent/50 hover:text-text-primary transition-all duration-200"
            >
              {s.label}
            </button>
          ))}
        </div>
      )}

      {/* Empty state */}
      {!searched && !loading && (
        <div className="border border-border/30 rounded-lg p-10 text-center">
          <div className="text-3xl mb-4">🧠</div>
          <p className="text-sm font-mono text-text-secondary mb-2">
            Your unified memory across <span className="text-text-primary font-semibold">5,110+</span> ChatGPT &amp; Claude conversations.
          </p>
          <p className="text-xs font-mono text-text-muted mb-5">
            Search for anything — decisions, people, technical discussions, ideas…
          </p>
          <div className="flex flex-wrap justify-center gap-x-4 gap-y-1 text-[10px] font-mono text-text-muted/60">
            <span>try: "what did I decide about…"</span>
            <span>·</span>
            <span>"conversations about React"</span>
            <span>·</span>
            <span>"meeting with…"</span>
          </div>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center gap-2 text-text-muted text-xs font-mono py-4">
          <span className="inline-block h-2 w-2 rounded-full bg-accent animate-pulse" />
          Searching across your memories…
        </div>
      )}

      {/* Error */}
      {error && !loading && (
        <div className="border border-red-500/20 rounded-lg p-4 bg-red-500/5">
          <p className="text-red-400/70 text-xs font-mono">{error}</p>
        </div>
      )}

      {/* No results */}
      {!loading && !error && searched && results.length === 0 && (
        <div className="border border-border/30 rounded-lg p-8 text-center">
          <p className="text-text-muted text-sm font-mono mb-1">No memories found for "{query}"</p>
          <p className="text-text-muted/60 text-[11px] font-mono">Try different keywords or a broader search</p>
        </div>
      )}

      {/* Results */}
      {results.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-text-muted text-[11px] font-mono tracking-wider uppercase">
              {results.length} result{results.length !== 1 ? 's' : ''}
              {total != null && total > results.length ? ` of ${total.toLocaleString()}` : ''}
            </p>
            <div className="flex items-center gap-3 text-[10px] font-mono text-text-muted">
              <span className="flex items-center gap-1">
                <span className="text-emerald-400">◉</span> ChatGPT
              </span>
              <span className="flex items-center gap-1">
                <span className="text-orange-400">◈</span> Claude
              </span>
            </div>
          </div>
          {results.map((r) => (
            <ConversationCard key={r.id} result={r} />
          ))}
        </div>
      )}
    </section>
  )
}

/* ───────────────────── Sources Section (ChatGPT + Claude only) ───────────────────── */

function SourcesSection() {
  const sources = [
    {
      name: 'ChatGPT',
      icon: '◉',
      color: 'text-emerald-400',
      borderColor: 'border-emerald-500/30',
      bgColor: 'bg-emerald-500/8',
      description: 'Conversations exported from OpenAI ChatGPT',
      format: 'JSON',
    },
    {
      name: 'Claude',
      icon: '◈',
      color: 'text-orange-400',
      borderColor: 'border-orange-500/30',
      bgColor: 'bg-orange-500/8',
      description: 'Conversations from Anthropic Claude',
      format: 'JSON',
    },
  ]

  return (
    <section className="mb-10">
      <h2 className="text-xs font-mono tracking-widest text-text-muted uppercase mb-4">CONNECTED SOURCES</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {sources.map((src) => (
          <div
            key={src.name}
            className={`border rounded-lg p-5 transition-colors ${src.borderColor} ${src.bgColor}`}
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className={`text-lg ${src.color}`}>{src.icon}</span>
                <span className="text-sm font-mono font-bold text-text-primary">{src.name}</span>
              </div>
              <span className="inline-flex items-center gap-1.5 text-[10px] font-mono text-emerald-400">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                indexed
              </span>
            </div>
            <p className="text-[11px] font-mono text-text-muted leading-relaxed">{src.description}</p>
          </div>
        ))}
      </div>
    </section>
  )
}

/* ───────────────────── Memory Stats Header ───────────────────── */

function MemoryStatsHeader() {
  const [pointsCount, setPointsCount] = useState<number | null>(null)

  useEffect(() => {
    let mounted = true
    ;(async () => {
      try {
        const resp = await fetch('/api/health/')
        if (resp.ok) {
          const data = await resp.json()
          if (data.qdrant_vectors && mounted) {
            setPointsCount(data.qdrant_vectors)
          }
        }
      } catch {
        // Silently fail — we have a fallback
      }
    })()
    return () => { mounted = false }
  }, [])

  const count = pointsCount ? pointsCount.toLocaleString() : '5,110+'

  return (
    <div className="mb-8">
      <div className="flex items-center gap-3 mb-2">
        <h1 className="text-lg font-mono font-bold text-text-primary tracking-wider">
          MEMORY
        </h1>
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-accent/10 border border-accent/20">
          <span className="h-1.5 w-1.5 rounded-full bg-accent animate-pulse" />
          <span className="text-[10px] font-mono text-accent tracking-wider">{count} memories</span>
        </div>
      </div>
      <p className="text-xs font-mono text-text-muted tracking-wide">
        Semantic search across all your ChatGPT &amp; Claude conversations — find anything you've ever discussed.
      </p>
    </div>
  )
}

/* ───────────────────── Timeline Types ───────────────────── */

interface TimelineCapture {
  id: string
  timestamp: string
  filepath: string
  width: number
  height: number
  monitor_index: number
  has_ocr: boolean
  text_preview?: string
}

interface TimelineResponse {
  captures: TimelineCapture[]
}

interface TimelineDay {
  date: string
  count: number
  first_capture: string
  last_capture: string
}

/* ───────────────────── Timeline Helpers ───────────────────── */

function captureImageUrl(filepath: string): string {
  // filepath comes as "/data/captures/2026/01/26/{id}.jpg" — strip /data/captures prefix
  const stripped = filepath.replace(/^\/data\/captures\//, '')
  return `/captures/${stripped}`
}

function formatCaptureTime(ts: string): string {
  try {
    const d = new Date(ts)
    return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return ''
  }
}

function formatDayLabel(dateStr: string): string {
  try {
    const d = new Date(dateStr + 'T12:00:00Z')
    const today = new Date()
    const todayStr = today.toISOString().slice(0, 10)
    const yesterday = new Date(today)
    yesterday.setDate(yesterday.getDate() - 1)
    const yesterdayStr = yesterday.toISOString().slice(0, 10)

    if (dateStr === todayStr) return 'Today'
    if (dateStr === yesterdayStr) return 'Yesterday'
    return d.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })
  } catch {
    return dateStr
  }
}

/* ───────────────────── Timeline Section ───────────────────── */

function TimelineSection() {
  const [captures, setCaptures] = useState<TimelineCapture[]>([])
  const [days, setDays] = useState<TimelineDay[]>([])
  const [selectedDay, setSelectedDay] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedCapture, setSelectedCapture] = useState<TimelineCapture | null>(null)

  // Total count across all days
  const totalCount = days.reduce((sum, d) => sum + d.count, 0)

  useEffect(() => {
    let mounted = true
    ;(async () => {
      try {
        const [timelineData, daysData] = await Promise.all([
          apiGet<TimelineResponse>('/api/timeline/'),
          apiGet<TimelineDay[]>('/api/timeline/days'),
        ])
        if (!mounted) return
        setCaptures(timelineData.captures ?? [])
        setDays(daysData ?? [])
      } catch (e) {
        console.error('Timeline fetch failed:', e)
        if (mounted) setError('Timeline unavailable — is the capture agent running?')
      } finally {
        if (mounted) setLoading(false)
      }
    })()
    return () => { mounted = false }
  }, [])

  // Filter captures by selected day
  const filteredCaptures = selectedDay
    ? captures.filter((c) => c.timestamp.startsWith(selectedDay))
    : captures

  return (
    <section className="mb-10">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xs font-mono tracking-widest text-text-muted uppercase">TIMELINE</h2>
        {totalCount > 0 && (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-violet-500/10 border border-violet-500/20">
            <span className="h-1.5 w-1.5 rounded-full bg-violet-400 animate-pulse" />
            <span className="text-[10px] font-mono text-violet-400 tracking-wider">
              {totalCount.toLocaleString()} screenshot{totalCount !== 1 ? 's' : ''} captured
            </span>
          </div>
        )}
      </div>

      {/* Day navigation */}
      {days.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-4">
          <button
            onClick={() => setSelectedDay(null)}
            className={`px-3 py-1.5 rounded-full text-[11px] font-mono border transition-all duration-200 ${
              selectedDay === null
                ? 'bg-violet-500/20 border-violet-500/40 text-violet-300'
                : 'bg-surface border-border text-text-muted hover:border-violet-500/30 hover:text-text-primary'
            }`}
          >
            All days
          </button>
          {days.map((day) => (
            <button
              key={day.date}
              onClick={() => setSelectedDay(day.date === selectedDay ? null : day.date)}
              className={`px-3 py-1.5 rounded-full text-[11px] font-mono border transition-all duration-200 ${
                selectedDay === day.date
                  ? 'bg-violet-500/20 border-violet-500/40 text-violet-300'
                  : 'bg-surface border-border text-text-muted hover:border-violet-500/30 hover:text-text-primary'
              }`}
            >
              {formatDayLabel(day.date)}
              <span className="ml-1.5 text-[9px] opacity-60">({day.count})</span>
            </button>
          ))}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center gap-2 text-text-muted text-xs font-mono py-8">
          <span className="inline-block h-2 w-2 rounded-full bg-violet-400 animate-pulse" />
          Loading captures…
        </div>
      )}

      {/* Error */}
      {error && !loading && (
        <div className="border border-red-500/20 rounded-lg p-4 bg-red-500/5">
          <p className="text-red-400/70 text-xs font-mono">{error}</p>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && captures.length === 0 && (
        <div className="border border-border/30 rounded-lg p-8 text-center">
          <div className="text-3xl mb-3">📸</div>
          <p className="text-sm font-mono text-text-secondary">No screen captures yet.</p>
          <p className="text-xs font-mono text-text-muted mt-1">The capture agent will start recording your screen automatically.</p>
        </div>
      )}

      {/* Capture grid */}
      {!loading && filteredCaptures.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
          {filteredCaptures.map((cap) => (
            <button
              key={cap.id}
              onClick={() => setSelectedCapture(selectedCapture?.id === cap.id ? null : cap)}
              className={`group border rounded-lg overflow-hidden transition-all duration-200 text-left ${
                selectedCapture?.id === cap.id
                  ? 'border-violet-500/60 ring-1 ring-violet-500/30'
                  : 'border-border/40 hover:border-violet-500/30'
              }`}
            >
              <div className="aspect-video bg-neutral-900 overflow-hidden">
                <img
                  src={captureImageUrl(cap.filepath)}
                  alt={`Screen capture ${formatCaptureTime(cap.timestamp)}`}
                  loading="lazy"
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                />
              </div>
              <div className="px-2 py-1.5 bg-surface/50">
                <p className="text-[10px] font-mono text-text-muted truncate">
                  {formatCaptureTime(cap.timestamp)}
                </p>
                {cap.has_ocr && (
                  <p className="text-[9px] font-mono text-violet-400/50 truncate mt-0.5">
                    OCR ✓
                  </p>
                )}
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Expanded capture detail */}
      {selectedCapture && (
        <div className="mt-4 border border-violet-500/30 rounded-lg overflow-hidden bg-violet-500/5">
          <div className="p-4">
            <div className="flex items-center justify-between mb-3">
              <div>
                <p className="text-xs font-mono text-text-primary">
                  {formatFullDate(selectedCapture.timestamp)}
                </p>
                <p className="text-[10px] font-mono text-text-muted mt-0.5">
                  {selectedCapture.width}×{selectedCapture.height} · Monitor {selectedCapture.monitor_index}
                </p>
              </div>
              <button
                onClick={() => setSelectedCapture(null)}
                className="text-text-muted hover:text-text-primary transition-colors p-1"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 6 6 18M6 6l12 12" strokeLinecap="round" />
                </svg>
              </button>
            </div>
            <img
              src={captureImageUrl(selectedCapture.filepath)}
              alt="Full capture"
              className="w-full rounded-md border border-border/20"
            />
            {selectedCapture.text_preview && (
              <div className="mt-3 p-3 rounded-md bg-black/20 border border-border/20">
                <p className="text-[10px] font-mono text-text-muted tracking-wider mb-1.5">OCR TEXT</p>
                <p className="text-[11px] font-mono text-text-secondary leading-relaxed whitespace-pre-wrap">
                  {selectedCapture.text_preview.slice(0, 500)}
                  {selectedCapture.text_preview.length > 500 ? '…' : ''}
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  )
}

/* ───────────────────── Main Page ───────────────────── */

export function MemoryPage() {
  return (
    <div>
      <MemoryStatsHeader />
      <TimelineSection />
      <SearchSection />
      <SourcesSection />
    </div>
  )
}
