import { useState, useEffect, useCallback, useRef } from 'react'
import { apiGet, apiPost } from '../api/client.ts'

/* ───────────────────────── Types ───────────────────────── */

interface SearchResult {
  id: string
  content: string
  source: 'chatgpt' | 'claude' | 'capture' | string
  timestamp: string
  score: number
}

interface SearchResponse {
  results: SearchResult[]
  total?: number
  query?: string
}

interface TimelineCapture {
  id: string
  timestamp: string
  thumbnail_url?: string
  url?: string
  title?: string
  app?: string
}

interface TimelineResponse {
  captures: TimelineCapture[]
  date?: string
}

interface ImportSource {
  source: string
  count: number
  status: string
  last_import?: string
}

interface RecentCapture {
  id: string
  timestamp: string
  thumbnail_url?: string
  url?: string
  title?: string
  app?: string
}

/* ───────────────────────── Helpers ───────────────────────── */

function formatTime(ts: string): string {
  try {
    const d = new Date(ts)
    return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
  } catch { return '' }
}

function formatDate(ts: string): string {
  try {
    const d = new Date(ts)
    return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
  } catch { return '' }
}

function formatRelative(ts: string): string {
  try {
    const now = Date.now()
    const then = new Date(ts).getTime()
    const diff = now - then
    const mins = Math.floor(diff / 60000)
    if (mins < 1) return 'just now'
    if (mins < 60) return `${mins}m ago`
    const hrs = Math.floor(mins / 60)
    if (hrs < 24) return `${hrs}h ago`
    const days = Math.floor(hrs / 24)
    return `${days}d ago`
  } catch { return '' }
}

function sourceColor(source: string): string {
  switch (source) {
    case 'chatgpt': return 'bg-green-500/20 text-green-400 border-green-500/30'
    case 'claude': return 'bg-orange-500/20 text-orange-400 border-orange-500/30'
    case 'capture': return 'bg-blue-500/20 text-blue-400 border-blue-500/30'
    case 'grok': return 'bg-purple-500/20 text-purple-400 border-purple-500/30'
    default: return 'bg-neutral-500/20 text-neutral-400 border-neutral-500/30'
  }
}

function sourceIcon(source: string): string {
  switch (source) {
    case 'chatgpt': return '◉'
    case 'claude': return '◈'
    case 'capture': return '◻'
    case 'grok': return '◆'
    default: return '○'
  }
}

function todayStr(): string {
  return new Date().toISOString().slice(0, 10)
}

/* ───────────────────── Section Components ───────────────────── */

function SearchSection() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  const doSearch = useCallback(async (q: string) => {
    if (!q.trim()) { setResults([]); setSearched(false); return }
    setLoading(true)
    setSearched(true)
    try {
      const data = await apiPost<SearchResponse>('/api/search/', { query: q.trim(), limit: 20 })
      setResults(data.results ?? [])
    } catch {
      setResults([])
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

  return (
    <section className="mb-10">
      {/* Search bar */}
      <form onSubmit={handleSubmit} className="relative mb-6">
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
            placeholder="Search your memory — conversations, captures, everything…"
            className="flex-1 bg-transparent px-4 py-3.5 text-sm text-text-primary placeholder:text-text-muted font-mono outline-none"
          />
          {query && (
            <button
              type="button"
              onClick={() => { setQuery(''); setResults([]); setSearched(false) }}
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

      {/* Results */}
      {loading && (
        <div className="flex items-center gap-2 text-text-muted text-xs font-mono">
          <span className="inline-block h-2 w-2 rounded-full bg-accent animate-pulse" />
          Searching memory…
        </div>
      )}

      {!loading && searched && results.length === 0 && (
        <p className="text-text-muted text-xs font-mono">No memories found for "{query}"</p>
      )}

      {results.length > 0 && (
        <div className="space-y-3">
          <p className="text-text-muted text-[11px] font-mono tracking-wider uppercase">
            {results.length} result{results.length !== 1 ? 's' : ''}
          </p>
          {results.map((r) => (
            <div
              key={r.id}
              className="border border-border rounded-lg p-4 bg-surface hover:border-border-light transition-colors group"
            >
              <div className="flex items-start justify-between gap-4 mb-2">
                <div className="flex items-center gap-2">
                  <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono tracking-wider border ${sourceColor(r.source)}`}>
                    {sourceIcon(r.source)} {r.source.toUpperCase()}
                  </span>
                  <span className="text-[11px] text-text-muted font-mono">
                    {formatDate(r.timestamp)} · {formatTime(r.timestamp)}
                  </span>
                </div>
                <span className="text-[10px] font-mono text-text-muted shrink-0">
                  {(r.score * 100).toFixed(0)}% match
                </span>
              </div>
              <p className="text-sm text-text-secondary leading-relaxed line-clamp-3">
                {r.content}
              </p>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

function SourcesSection() {
  const [sources, setSources] = useState<ImportSource[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let mounted = true
    ;(async () => {
      try {
        const data = await apiGet<{ sources: ImportSource[] } | ImportSource[]>('/api/import/sources')
        const list = Array.isArray(data) ? data : (data as { sources: ImportSource[] }).sources ?? []
        if (mounted) setSources(list)
      } catch {
        // Fallback with known stats
        if (mounted) setSources([
          { source: 'chatgpt', count: 3802, status: 'indexed', last_import: '' },
          { source: 'claude', count: 1238, status: 'indexed', last_import: '' },
          { source: 'grok', count: 0, status: 'pending', last_import: '' },
        ])
      } finally {
        if (mounted) setLoading(false)
      }
    })()
    return () => { mounted = false }
  }, [])

  const total = sources.reduce((s, x) => s + (x.count || 0), 0)

  if (loading) {
    return (
      <section className="mb-10">
        <h2 className="text-xs font-mono tracking-widest text-text-muted uppercase mb-4">CONVERSATION SOURCES</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="border border-border rounded-lg p-5 bg-surface animate-pulse h-28" />
          ))}
        </div>
      </section>
    )
  }

  return (
    <section className="mb-10">
      <div className="flex items-baseline justify-between mb-4">
        <h2 className="text-xs font-mono tracking-widest text-text-muted uppercase">CONVERSATION SOURCES</h2>
        <span className="text-xs font-mono text-text-muted">
          {total.toLocaleString()} total indexed
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {sources.map((src) => {
          const isActive = src.count > 0
          return (
            <div
              key={src.source}
              className={`border rounded-lg p-5 transition-colors ${
                isActive
                  ? 'border-border bg-surface hover:border-border-light'
                  : 'border-border/50 bg-surface/50'
              }`}
            >
              <div className="flex items-center justify-between mb-3">
                <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono tracking-wider border ${sourceColor(src.source)}`}>
                  {sourceIcon(src.source)} {src.source.toUpperCase()}
                </span>
                <span className={`inline-block h-2 w-2 rounded-full ${
                  src.status === 'indexed' ? 'bg-green-500' :
                  src.status === 'importing' ? 'bg-yellow-500 animate-pulse' :
                  'bg-neutral-600'
                }`} />
              </div>
              <p className="text-2xl font-mono font-bold text-text-primary mb-1">
                {src.count.toLocaleString()}
              </p>
              <p className="text-[11px] font-mono text-text-muted uppercase tracking-wider">
                {src.status === 'indexed' ? 'conversations indexed' :
                 src.status === 'importing' ? 'importing…' :
                 'awaiting import'}
              </p>
            </div>
          )
        })}
      </div>
    </section>
  )
}

function TimelineSection() {
  const [date, setDate] = useState(todayStr())
  const [captures, setCaptures] = useState<TimelineCapture[]>([])
  const [loading, setLoading] = useState(true)

  const fetchTimeline = useCallback(async (d: string) => {
    setLoading(true)
    try {
      const data = await apiGet<TimelineResponse | TimelineCapture[]>(
        `/api/web/timeline/grid?date=${d}`
      )
      const list = Array.isArray(data) ? data : (data as TimelineResponse).captures ?? []
      setCaptures(list)
    } catch {
      setCaptures([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchTimeline(date) }, [date, fetchTimeline])

  const changeDay = (delta: number) => {
    const d = new Date(date)
    d.setDate(d.getDate() + delta)
    setDate(d.toISOString().slice(0, 10))
  }

  return (
    <section className="mb-10">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xs font-mono tracking-widest text-text-muted uppercase">TIMELINE</h2>
        <div className="flex items-center gap-2">
          <button
            onClick={() => changeDay(-1)}
            className="px-2 py-1 text-text-muted hover:text-text-primary border border-border rounded text-xs font-mono transition-colors"
          >
            ← PREV
          </button>
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="bg-surface border border-border rounded px-3 py-1 text-xs font-mono text-text-primary outline-none focus:border-accent transition-colors"
          />
          <button
            onClick={() => changeDay(1)}
            disabled={date >= todayStr()}
            className="px-2 py-1 text-text-muted hover:text-text-primary border border-border rounded text-xs font-mono transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
          >
            NEXT →
          </button>
          {date !== todayStr() && (
            <button
              onClick={() => setDate(todayStr())}
              className="px-2 py-1 text-accent hover:text-red-400 border border-accent/30 rounded text-[10px] font-mono tracking-wider transition-colors"
            >
              TODAY
            </button>
          )}
        </div>
      </div>

      {loading && (
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="aspect-video bg-surface border border-border rounded-lg animate-pulse" />
          ))}
        </div>
      )}

      {!loading && captures.length === 0 && (
        <div className="border border-border/50 rounded-lg p-12 text-center">
          <p className="text-text-muted text-xs font-mono">No captures for {formatDate(date + 'T00:00:00')}</p>
        </div>
      )}

      {!loading && captures.length > 0 && (
        <>
          <p className="text-[11px] font-mono text-text-muted mb-3">
            {captures.length} capture{captures.length !== 1 ? 's' : ''} · {formatDate(date + 'T00:00:00')}
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
            {captures.map((cap) => (
              <div
                key={cap.id}
                className="group relative border border-border rounded-lg overflow-hidden bg-surface hover:border-accent/50 transition-colors cursor-pointer"
              >
                {(cap.thumbnail_url || cap.url) ? (
                  <img
                    src={cap.thumbnail_url || cap.url}
                    alt={cap.title || 'Capture'}
                    className="w-full aspect-video object-cover opacity-80 group-hover:opacity-100 transition-opacity"
                    loading="lazy"
                  />
                ) : (
                  <div className="w-full aspect-video bg-neutral-800 flex items-center justify-center">
                    <svg width="24" height="24" fill="none" stroke="currentColor" strokeWidth="1" viewBox="0 0 24 24" className="text-text-muted">
                      <rect x="2" y="3" width="20" height="14" rx="2" />
                      <path d="M8 21h8M12 17v4" />
                    </svg>
                  </div>
                )}
                <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/80 to-transparent p-2">
                  <span className="text-[10px] font-mono text-white/80">
                    {formatTime(cap.timestamp)}
                  </span>
                  {cap.app && (
                    <span className="text-[9px] font-mono text-white/50 ml-2">
                      {cap.app}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  )
}

function RecentCapturesSection() {
  const [captures, setCaptures] = useState<RecentCapture[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let mounted = true
    ;(async () => {
      try {
        const data = await apiGet<{ captures: RecentCapture[] } | RecentCapture[]>('/api/web/recent-captures')
        const list = Array.isArray(data) ? data : (data as { captures: RecentCapture[] }).captures ?? []
        if (mounted) setCaptures(list)
      } catch {
        if (mounted) setCaptures([])
      } finally {
        if (mounted) setLoading(false)
      }
    })()
    return () => { mounted = false }
  }, [])

  if (loading) {
    return (
      <section className="mb-10">
        <h2 className="text-xs font-mono tracking-widest text-text-muted uppercase mb-4">RECENT CAPTURES</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="aspect-video bg-surface border border-border rounded-lg animate-pulse" />
          ))}
        </div>
      </section>
    )
  }

  if (captures.length === 0) return null

  return (
    <section className="mb-10">
      <h2 className="text-xs font-mono tracking-widest text-text-muted uppercase mb-4">RECENT CAPTURES</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {captures.slice(0, 8).map((cap) => (
          <div
            key={cap.id}
            className="group relative border border-border rounded-lg overflow-hidden bg-surface hover:border-accent/50 transition-all cursor-pointer"
          >
            {(cap.thumbnail_url || cap.url) ? (
              <img
                src={cap.thumbnail_url || cap.url}
                alt={cap.title || 'Recent capture'}
                className="w-full aspect-video object-cover opacity-80 group-hover:opacity-100 transition-opacity"
                loading="lazy"
              />
            ) : (
              <div className="w-full aspect-video bg-neutral-800 flex items-center justify-center">
                <svg width="28" height="28" fill="none" stroke="currentColor" strokeWidth="1" viewBox="0 0 24 24" className="text-text-muted">
                  <rect x="2" y="3" width="20" height="14" rx="2" />
                  <path d="M8 21h8M12 17v4" />
                </svg>
              </div>
            )}
            <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/80 via-black/40 to-transparent p-3">
              {cap.title && (
                <p className="text-[11px] font-mono text-white/90 truncate mb-0.5">
                  {cap.title}
                </p>
              )}
              <span className="text-[10px] font-mono text-white/60">
                {formatRelative(cap.timestamp)}
              </span>
              {cap.app && (
                <span className="text-[9px] font-mono text-white/40 ml-2">
                  {cap.app}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

/* ───────────────────── Main Page ───────────────────── */

export function MemoryPage() {
  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-lg font-mono font-bold text-text-primary tracking-wider mb-1">
          MEMORY
        </h1>
        <p className="text-xs font-mono text-text-muted tracking-wide">
          Search and explore your unified digital memory — conversations, captures, everything indexed.
        </p>
      </div>

      <SearchSection />
      <SourcesSection />
      <RecentCapturesSection />
      <TimelineSection />
    </div>
  )
}
