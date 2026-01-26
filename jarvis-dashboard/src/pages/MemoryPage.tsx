import { useState, useEffect, useCallback, useRef } from 'react'
import { apiGet, apiPost } from '../api/client.ts'

/* ───────────────────────── Types ───────────────────────── */

interface SearchResult {
  id: string
  text_preview: string
  timestamp: string
  score: number
}

interface SearchResponse {
  results: SearchResult[]
  total?: number
  query?: string
}

interface ImportSource {
  id: string
  name: string
  format: string
  instructions: string
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

function formatColor(format: string): string {
  switch (format.toLowerCase()) {
    case 'json': return 'bg-green-500/20 text-green-400 border-green-500/30'
    case 'markdown':
    case 'md': return 'bg-blue-500/20 text-blue-400 border-blue-500/30'
    case 'html': return 'bg-orange-500/20 text-orange-400 border-orange-500/30'
    case 'csv': return 'bg-purple-500/20 text-purple-400 border-purple-500/30'
    default: return 'bg-neutral-500/20 text-neutral-400 border-neutral-500/30'
  }
}

/* ───────────────────── Section Components ───────────────────── */

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
      setError('Search unavailable')
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

      {/* Results */}
      {loading && (
        <div className="flex items-center gap-2 text-text-muted text-xs font-mono">
          <span className="inline-block h-2 w-2 rounded-full bg-accent animate-pulse" />
          Searching memory…
        </div>
      )}

      {error && !loading && (
        <p className="text-red-400/70 text-xs font-mono">{error}</p>
      )}

      {!loading && !error && searched && results.length === 0 && (
        <p className="text-text-muted text-xs font-mono">No memories found for "{query}"</p>
      )}

      {results.length > 0 && (
        <div className="space-y-3">
          <p className="text-text-muted text-[11px] font-mono tracking-wider uppercase">
            {results.length} result{results.length !== 1 ? 's' : ''}
            {total != null && total > results.length ? ` of ${total.toLocaleString()}` : ''}
          </p>
          {results.map((r) => (
            <div
              key={r.id}
              className="border border-border rounded-lg p-4 bg-surface hover:border-border-light transition-colors group"
            >
              <div className="flex items-start justify-between gap-4 mb-2">
                <span className="text-[11px] text-text-muted font-mono">
                  {formatDate(r.timestamp)} · {formatTime(r.timestamp)}
                </span>
                <span className="text-[10px] font-mono text-text-muted shrink-0">
                  {(r.score * 100).toFixed(0)}% match
                </span>
              </div>
              <p className="text-sm text-text-secondary leading-relaxed line-clamp-3">
                {r.text_preview}
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
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let mounted = true
    ;(async () => {
      try {
        const data = await apiGet<{ sources: ImportSource[] }>('/api/import/sources')
        const list = data?.sources ?? []
        if (mounted) setSources(list)
      } catch (e) {
        console.error('Failed to load import sources:', e)
        if (mounted) setError('Could not load import sources')
      } finally {
        if (mounted) setLoading(false)
      }
    })()
    return () => { mounted = false }
  }, [])

  if (loading) {
    return (
      <section className="mb-10">
        <h2 className="text-xs font-mono tracking-widest text-text-muted uppercase mb-4">IMPORT SOURCES</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="border border-border rounded-lg p-5 bg-surface animate-pulse h-28" />
          ))}
        </div>
      </section>
    )
  }

  if (error) {
    return (
      <section className="mb-10">
        <h2 className="text-xs font-mono tracking-widest text-text-muted uppercase mb-4">IMPORT SOURCES</h2>
        <div className="border border-border/50 rounded-lg p-6 text-center">
          <p className="text-text-muted text-xs font-mono">{error}</p>
        </div>
      </section>
    )
  }

  if (sources.length === 0) return null

  return (
    <section className="mb-10">
      <div className="flex items-baseline justify-between mb-4">
        <h2 className="text-xs font-mono tracking-widest text-text-muted uppercase">IMPORT SOURCES</h2>
        <span className="text-xs font-mono text-text-muted">
          {sources.length} source{sources.length !== 1 ? 's' : ''} configured
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {sources.map((src) => (
          <div
            key={src.id}
            className="border border-border rounded-lg p-5 bg-surface hover:border-border-light transition-colors"
          >
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-mono font-bold text-text-primary">
                {src.name}
              </span>
              <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono tracking-wider border ${formatColor(src.format)}`}>
                {src.format.toUpperCase()}
              </span>
            </div>
            {src.instructions && (
              <p className="text-[11px] font-mono text-text-muted leading-relaxed line-clamp-2">
                {src.instructions}
              </p>
            )}
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

      {/* Placeholder for future sections */}
      <section className="mb-10">
        <div className="border border-border/30 rounded-lg p-8 text-center">
          <p className="text-text-muted/50 text-[11px] font-mono tracking-wider uppercase mb-1">
            TIMELINE & CAPTURES
          </p>
          <p className="text-text-muted/40 text-[10px] font-mono">
            Screen capture timeline coming soon — API integration pending
          </p>
        </div>
      </section>
    </div>
  )
}
