import React, { useState, useEffect } from 'react'
import type { FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { apiGet, apiPost } from '../api/client.ts'
import { ContextHandoffModal } from '../components/ContextHandoffModal.tsx'
import { PeopleGraph } from '../components/PeopleGraph.tsx'

/* ───────────────────────── Types ───────────────────────── */

interface MemoryStats {
  total_conversations: number
  total_chunks: number
  date_range: {
    start: string | null
    end: string | null
  }
  top_people: string[]
  top_projects: string[]
  decisions_count: number
  action_items_count: number
  sources: { [key: string]: number }
}

interface TimelineItem {
  date: string | null
  type: string
  title: string
  snippet: string
  tags: string[]
  source: string
  conversation_id: string
  chunk_index: number
}

interface SearchResultItem {
  conversation_id: string
  source: string
  title: string
  snippet: string
  chunk_index: number
  total_chunks: number
  date: string | null
  people: string[]
  projects: string[]
  topics: string[]
  sentiment: string
  relevance_score: number
}

interface TimelineResponse {
  items: TimelineItem[]
  total: number
}

interface SearchResponse {
  results: SearchResultItem[]
  total: number
}

interface SourceReference {
  title: string
  date: string | null
  conversation_id: string
  snippet: string
}

interface AskResponse {
  answer: string
  sources: SourceReference[]
}

/* ───────────────────────── Helpers ───────────────────────── */

function formatDateRange(start: string | null, end: string | null): string {
  if (!start || !end) return 'No data'
  try {
    const s = new Date(start)
    const e = new Date(end)
    return `${s.toLocaleDateString('en-US', { month: 'short', year: 'numeric' })} — ${e.toLocaleDateString('en-US', { month: 'short', year: 'numeric' })}`
  } catch {
    return 'Invalid range'
  }
}

function formatDate(isoDate: string | null): string {
  if (!isoDate) return 'Unknown date'
  try {
    return new Date(isoDate).toLocaleDateString('en-US', { 
      month: 'short', 
      day: 'numeric', 
      year: 'numeric' 
    })
  } catch {
    return 'Invalid date'
  }
}

function highlightText(text: string, query: string): React.ReactElement {
  if (!query.trim()) {
    return <span>{text}</span>
  }

  // Split query into words and escape special regex chars
  const searchTerms = query.toLowerCase().split(/\s+/).filter(t => t.length > 2)
  if (searchTerms.length === 0) {
    return <span>{text}</span>
  }

  // Build regex pattern to match any of the search terms
  const pattern = searchTerms.map(term => 
    term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  ).join('|')
  
  const regex = new RegExp(`(${pattern})`, 'gi')
  const parts = text.split(regex)

  return (
    <>
      {parts.map((part, i) => {
        const isMatch = searchTerms.some(term => 
          part.toLowerCase() === term.toLowerCase()
        )
        return isMatch ? (
          <mark key={i} className="bg-accent/30 text-accent font-semibold">
            {part}
          </mark>
        ) : (
          <span key={i}>{part}</span>
        )
      })}
    </>
  )
}

/* ───────────────────────── Stat Card ───────────────────────── */

function StatCard({ label, value, small }: { label: string; value: string | number; small?: boolean }) {
  return (
    <div className="border border-border p-5">
      <p className="font-mono text-[11px] text-text-secondary mb-3 tracking-wider">
        {label}
      </p>
      <p className={`font-bold tracking-tight text-text-primary ${small ? 'text-sm' : 'text-3xl sm:text-4xl'}`}>
        {value}
      </p>
    </div>
  )
}

/* ───────────────────────── Search Result Card ───────────────────────── */

function SearchResultCard({ result, searchQuery }: { result: SearchResultItem; searchQuery: string }) {
  const navigate = useNavigate()
  
  const sourceConfig = {
    chatgpt: { label: 'ChatGPT', color: 'text-emerald-400' },
    claude: { label: 'Claude', color: 'text-orange-400' },
    grok: { label: 'Grok', color: 'text-blue-400' },
  }[result.source.toLowerCase()] || { label: result.source, color: 'text-text-muted' }

  const scorePercent = Math.round(result.relevance_score * 100)

  const handleClick = () => {
    navigate(`/conversation/${result.conversation_id}`, {
      state: { searchQuery }
    })
  }

  return (
    <div 
      onClick={handleClick}
      className="border border-border rounded-lg p-4 hover:border-accent/50 transition-colors bg-surface cursor-pointer"
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-2">
        <h3 className="text-sm font-mono font-semibold text-text-primary line-clamp-1">
          {result.title}
        </h3>
        <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${sourceConfig.color} bg-black/20 shrink-0`}>
          {sourceConfig.label}
        </span>
      </div>

      {/* Snippet with highlighting */}
      <p className="text-xs text-text-secondary leading-relaxed mb-3 line-clamp-3">
        {highlightText(result.snippet, searchQuery)}
      </p>

      {/* Tags */}
      <div className="flex flex-wrap gap-1.5 mb-3">
        {result.people.slice(0, 3).map((person, i) => (
          <span key={i} className="px-2 py-0.5 text-[10px] font-mono text-blue-400 bg-blue-500/10 rounded">
            👤 {person}
          </span>
        ))}
        {result.projects.slice(0, 3).map((project, i) => (
          <span key={i} className="px-2 py-0.5 text-[10px] font-mono text-purple-400 bg-purple-500/10 rounded">
            📁 {project}
          </span>
        ))}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-mono text-text-muted">
          {formatDate(result.date)}
        </span>
        <div className="flex items-center gap-2">
          <div className="w-16 h-1.5 bg-border rounded-full overflow-hidden">
            <div 
              className="h-full bg-accent rounded-full transition-all"
              style={{ width: `${scorePercent}%` }}
            />
          </div>
          <span className="text-[10px] font-mono text-text-muted">{scorePercent}%</span>
        </div>
      </div>
    </div>
  )
}

/* ───────────────────────── Section Card ───────────────────────── */

function SectionCard({ 
  title, 
  items, 
  emptyMessage 
}: { 
  title: string
  items: TimelineItem[]
  emptyMessage: string
}) {
  const navigate = useNavigate()

  return (
    <div className="border border-border rounded-lg p-5">
      <h3 className="text-[11px] font-mono tracking-wider text-text-muted uppercase mb-4">
        {title}
      </h3>
      
      {items.length === 0 ? (
        <p className="text-xs font-mono text-text-muted/50 italic">{emptyMessage}</p>
      ) : (
        <div className="space-y-3">
          {items.map((item, i) => (
            <div
              key={i}
              onClick={() => {
                if (item.conversation_id) {
                  navigate(`/conversation/${item.conversation_id}`)
                }
              }}
              className={`pb-3 border-b border-border/30 last:border-0 last:pb-0 ${
                item.conversation_id ? 'cursor-pointer hover:bg-surface/30 rounded px-2 -mx-2 py-2 transition-colors' : ''
              }`}
            >
              <p className="text-xs font-mono text-text-primary mb-1 line-clamp-2">
                {item.title || item.snippet.slice(0, 80)}
              </p>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono text-text-muted">
                  {formatDate(item.date)}
                </span>
                <span className="text-[10px] font-mono text-accent">
                  {item.source}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/* ───────────────────────── Timeline Item Card ───────────────────────── */

function TimelineItemCard({ item }: { item: TimelineItem }) {
  const navigate = useNavigate()
  
  const typeConfig = {
    decision: { icon: '◆', color: 'text-purple-400' },
    action: { icon: '→', color: 'text-orange-400' },
    mention: { icon: '○', color: 'text-blue-400' },
  }[item.type] || { icon: '·', color: 'text-text-muted' }

  const handleClick = () => {
    navigate(`/conversation/${item.conversation_id}`)
  }

  return (
    <div 
      onClick={handleClick}
      className="border border-border/50 rounded p-3 hover:border-accent/30 transition-colors cursor-pointer"
    >
      <div className="flex items-start gap-3">
        <span className={`${typeConfig.color} text-sm mt-0.5`}>{typeConfig.icon}</span>
        <div className="flex-1 min-w-0">
          <p className="text-xs font-mono text-text-primary mb-1 line-clamp-2">
            {item.title || item.snippet.slice(0, 100)}
          </p>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono text-text-muted">
              {formatDate(item.date)}
            </span>
            <span className="text-[10px] font-mono text-accent">
              {item.source}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

/* ───────────────────────── Main Page ───────────────────────── */

export function BrainTimelinePage() {
  const [searchParams] = useSearchParams()
  const [stats, setStats] = useState<MemoryStats | null>(null)
  const [mode, setMode] = useState<'search' | 'ask'>('search')
  const [searchQuery, setSearchQuery] = useState(searchParams.get('search') || '')
  const [searchResults, setSearchResults] = useState<SearchResultItem[]>([])
  const [askResponse, setAskResponse] = useState<AskResponse | null>(null)
  const [isSearching, setIsSearching] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  
  // Filter states
  const [sourceFilter, setSourceFilter] = useState<string>('')
  const [dateRangeFilter, setDateRangeFilter] = useState<'all' | 'week' | 'month' | '3months' | 'custom'>('all')
  const [customStartDate, setCustomStartDate] = useState<string>('')
  const [customEndDate, setCustomEndDate] = useState<string>('')
  
  const [decisions, setDecisions] = useState<TimelineItem[]>([])
  const [actions, setActions] = useState<TimelineItem[]>([])
  const [timelineItems, setTimelineItems] = useState<TimelineItem[]>([])
  const [timelineExpanded, setTimelineExpanded] = useState(true)
  
  // Context handoff modal state
  const [handoffProject, setHandoffProject] = useState<string>('')
  const [showHandoffModal, setShowHandoffModal] = useState(false)

  // Fetch stats on mount
  useEffect(() => {
    fetchStats()
    fetchSections()
  }, [])

  // Auto-search if query param is present
  useEffect(() => {
    const searchParam = searchParams.get('search')
    if (searchParam && searchParam.trim()) {
      setSearchQuery(searchParam)
      setMode('search')
      // Trigger search after a short delay to ensure state is set
      setTimeout(() => {
        handleSearch({ preventDefault: () => {} } as FormEvent)
      }, 100)
    }
  }, [searchParams])

  const fetchStats = async () => {
    try {
      const data = await apiGet<MemoryStats>('/api/v2/memory/stats')
      setStats(data)
    } catch (e) {
      console.error('Failed to fetch stats:', e)
    }
  }

  const fetchSections = async () => {
    // Fetch each section independently so one failure doesn't block others
    try {
      const decisionsData = await apiGet<{ decisions: any[] }>('/api/v2/bridge/decisions?limit=5')
      const mappedDecisions: TimelineItem[] = (decisionsData.decisions ?? []).map(d => ({
        date: d.date_sent,
        type: 'decision',
        title: d.subject,
        snippet: d.snippet,
        tags: d.action_phrases || [],
        source: 'email',
        conversation_id: d.id,
        chunk_index: 0,
      }))
      setDecisions(mappedDecisions)
    } catch (e) {
      console.error('Failed to fetch decisions:', e)
    }

    try {
      const actionsData = await apiGet<{ followups: any[] }>('/api/v2/bridge/followups?limit=5')
      const mappedActions: TimelineItem[] = (actionsData.followups ?? []).map(f => ({
        date: f.date_sent,
        type: 'action',
        title: f.subject,
        snippet: f.promise,
        tags: [],
        source: 'email',
        conversation_id: f.id,
        chunk_index: 0,
      }))
      setActions(mappedActions)
    } catch (e) {
      console.error('Failed to fetch actions:', e)
    }

    try {
      const timelineData = await apiGet<TimelineResponse>('/api/v2/memory/timeline?limit=20')
      setTimelineItems(timelineData.items ?? [])
    } catch (e) {
      console.error('Failed to fetch timeline:', e)
    }
  }

  const handleSearch = async (e: FormEvent) => {
    e.preventDefault()
    
    if (!searchQuery.trim()) return

    setIsSearching(true)
    setHasSearched(true)

    try {
      if (mode === 'search') {
        // Build query params
        const params = new URLSearchParams()
        params.append('q', searchQuery)
        params.append('limit', '20')
        
        // Add source filter if selected
        if (sourceFilter) {
          params.append('source', sourceFilter)
        }
        
        // Add date filters based on range selection
        if (dateRangeFilter !== 'all') {
          const now = new Date()
          let startDate: Date | null = null
          
          if (dateRangeFilter === 'week') {
            startDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
          } else if (dateRangeFilter === 'month') {
            startDate = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000)
          } else if (dateRangeFilter === '3months') {
            startDate = new Date(now.getTime() - 90 * 24 * 60 * 60 * 1000)
          } else if (dateRangeFilter === 'custom' && customStartDate) {
            startDate = new Date(customStartDate)
          }
          
          if (startDate) {
            params.append('start_date', startDate.toISOString().split('T')[0])
          }
          
          if (dateRangeFilter === 'custom' && customEndDate) {
            params.append('end_date', customEndDate)
          }
        }
        
        const data = await apiGet<SearchResponse>(`/api/v2/memory/search?${params}`)
        setSearchResults(data.results)
        setAskResponse(null)
      } else {
        // Ask mode
        const data = await apiPost<AskResponse>('/api/v2/memory/ask', {
          question: searchQuery,
          limit: 5
        })
        setAskResponse(data)
        setSearchResults([])
      }
    } catch (e) {
      console.error('Failed to search/ask:', e)
      setSearchResults([])
      setAskResponse(null)
    } finally {
      setIsSearching(false)
    }
  }

  const clearSearch = () => {
    setSearchQuery('')
    setSearchResults([])
    setAskResponse(null)
    setHasSearched(false)
  }

  return (
    <div className="max-w-6xl mx-auto">
      {/* Project Catch-up */}
      <div className="mb-10">
        <h2 className="text-sm font-mono font-bold text-text-primary mb-4 tracking-wider uppercase">
          🎯 Project Catch-up
        </h2>
        <p className="text-xs font-mono text-text-muted mb-4">
          Get a quick context handoff for a project you're returning to
        </p>
        <div className="flex flex-wrap gap-2">
          {['RecruitOS', 'Jarvis', 'CMP', 'Atlas', 'Eureka'].map((project) => (
            <button
              key={project}
              onClick={() => {
                setHandoffProject(project)
                setShowHandoffModal(true)
              }}
              className="px-4 py-2 text-xs font-mono border border-border text-text-primary hover:border-accent hover:text-accent transition-colors rounded"
            >
              Catch me up: {project}
            </button>
          ))}
          <div className="flex items-center gap-2">
            <input
              type="text"
              placeholder="Other project..."
              className="px-3 py-2 text-xs font-mono bg-surface border border-border rounded text-text-primary placeholder:text-text-muted outline-none focus:border-accent transition-colors"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && e.currentTarget.value.trim()) {
                  setHandoffProject(e.currentTarget.value.trim())
                  setShowHandoffModal(true)
                  e.currentTarget.value = ''
                }
              }}
            />
          </div>
        </div>
      </div>

      {/* People Graph */}
      <PeopleGraph />

      {/* Hero Search */}
      <div className="mb-10 text-center">
        <h1 className="text-2xl font-mono font-bold text-text-primary mb-6 tracking-wider">
          🧠 MEMORY {mode === 'ask' ? 'Q&A' : 'SEARCH'}
        </h1>
        
        {/* Mode Toggle */}
        <div className="flex items-center justify-center gap-2 mb-6">
          <button
            onClick={() => setMode('search')}
            className={`px-4 py-2 text-xs font-mono tracking-wider border rounded transition-colors ${
              mode === 'search'
                ? 'border-accent text-accent bg-accent/10'
                : 'border-border text-text-secondary hover:border-border-light hover:text-text-primary'
            }`}
          >
            SEARCH
          </button>
          <button
            onClick={() => setMode('ask')}
            className={`px-4 py-2 text-xs font-mono tracking-wider border rounded transition-colors ${
              mode === 'ask'
                ? 'border-accent text-accent bg-accent/10'
                : 'border-border text-text-secondary hover:border-border-light hover:text-text-primary'
            }`}
          >
            ASK AI
          </button>
        </div>

        <form onSubmit={handleSearch} className="max-w-2xl mx-auto">
          <div className="relative">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={
                mode === 'ask'
                  ? 'Ask a question... (e.g. "what did I discuss about Atlas?")'
                  : 'Search your memory... (e.g. "Atlas project")'
              }
              className="w-full px-6 py-4 text-base font-mono bg-surface border-2 border-border rounded-lg text-text-primary placeholder:text-text-muted outline-none focus:border-accent transition-colors"
              autoFocus
            />
            <button
              type="submit"
              disabled={!searchQuery.trim() || isSearching}
              className="absolute right-3 top-1/2 -translate-y-1/2 px-4 py-2 text-xs font-mono tracking-wider border border-accent text-accent rounded hover:bg-accent/10 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSearching ? (mode === 'ask' ? 'THINKING…' : 'SEARCHING…') : (mode === 'ask' ? 'ASK' : 'SEARCH')}
            </button>
          </div>
        </form>

        {/* Search Filters (only in search mode) */}
        {mode === 'search' && (
          <div className="max-w-2xl mx-auto mt-6">
            <div className="flex flex-wrap items-center gap-3">
              {/* Source Filter */}
              <div className="flex items-center gap-2">
                <label className="text-[10px] font-mono text-text-muted tracking-wider uppercase">
                  SOURCE:
                </label>
                <select
                  value={sourceFilter}
                  onChange={(e) => setSourceFilter(e.target.value)}
                  className="px-3 py-1.5 text-xs font-mono bg-surface border border-border rounded text-text-primary outline-none focus:border-accent transition-colors"
                >
                  <option value="">All</option>
                  <option value="chatgpt">ChatGPT</option>
                  <option value="claude">Claude</option>
                  <option value="grok">Grok</option>
                </select>
              </div>

              {/* Date Range Filter */}
              <div className="flex items-center gap-2">
                <label className="text-[10px] font-mono text-text-muted tracking-wider uppercase">
                  TIME:
                </label>
                <select
                  value={dateRangeFilter}
                  onChange={(e) => setDateRangeFilter(e.target.value as typeof dateRangeFilter)}
                  className="px-3 py-1.5 text-xs font-mono bg-surface border border-border rounded text-text-primary outline-none focus:border-accent transition-colors"
                >
                  <option value="all">All Time</option>
                  <option value="week">Last Week</option>
                  <option value="month">Last Month</option>
                  <option value="3months">Last 3 Months</option>
                  <option value="custom">Custom Range</option>
                </select>
              </div>

              {/* Custom Date Range (shown when custom is selected) */}
              {dateRangeFilter === 'custom' && (
                <>
                  <input
                    type="date"
                    value={customStartDate}
                    onChange={(e) => setCustomStartDate(e.target.value)}
                    className="px-3 py-1.5 text-xs font-mono bg-surface border border-border rounded text-text-primary outline-none focus:border-accent transition-colors"
                    placeholder="Start date"
                  />
                  <span className="text-text-muted">to</span>
                  <input
                    type="date"
                    value={customEndDate}
                    onChange={(e) => setCustomEndDate(e.target.value)}
                    className="px-3 py-1.5 text-xs font-mono bg-surface border border-border rounded text-text-primary outline-none focus:border-accent transition-colors"
                    placeholder="End date"
                  />
                </>
              )}

              {/* Clear Filters Button */}
              {(sourceFilter || dateRangeFilter !== 'all') && (
                <button
                  onClick={() => {
                    setSourceFilter('')
                    setDateRangeFilter('all')
                    setCustomStartDate('')
                    setCustomEndDate('')
                  }}
                  className="px-3 py-1.5 text-[10px] font-mono text-text-muted hover:text-accent transition-colors"
                >
                  CLEAR FILTERS
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-10">
          <StatCard 
            label="TOTAL CONVERSATIONS" 
            value={stats.total_conversations.toLocaleString()} 
          />
          <StatCard 
            label="MEMORY CHUNKS" 
            value={stats.total_chunks.toLocaleString()} 
          />
          <StatCard 
            label="DATE RANGE" 
            value={formatDateRange(stats.date_range.start, stats.date_range.end)}
            small
          />
        </div>
      )}

      {/* Ask Response */}
      {hasSearched && askResponse ? (
        <div className="mb-10">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-sm font-mono tracking-wider text-text-muted uppercase">
              AI ANSWER
            </h2>
            <button
              onClick={clearSearch}
              className="text-xs font-mono text-accent hover:underline"
            >
              Clear
            </button>
          </div>
          
          {/* Answer Card */}
          <div className="border border-accent/30 rounded-lg p-6 bg-accent/5 mb-6">
            <div className="prose prose-invert max-w-none">
              <p className="text-sm leading-relaxed text-text-primary whitespace-pre-wrap">
                {askResponse.answer}
              </p>
            </div>
          </div>

          {/* Sources */}
          {askResponse.sources.length > 0 && (
            <div>
              <h3 className="text-xs font-mono tracking-wider text-text-muted uppercase mb-4">
                SOURCES ({askResponse.sources.length})
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {askResponse.sources.map((source, i) => (
                  <div key={i} className="border border-border rounded-lg p-4 bg-surface hover:border-accent/30 transition-colors">
                    <h4 className="text-xs font-mono font-semibold text-text-primary mb-2">
                      {source.title}
                    </h4>
                    <p className="text-[11px] text-text-secondary leading-relaxed mb-2 line-clamp-2">
                      {source.snippet}
                    </p>
                    <span className="text-[10px] font-mono text-text-muted">
                      {formatDate(source.date)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : hasSearched && searchResults.length > 0 ? (
        <div className="mb-10">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-sm font-mono tracking-wider text-text-muted uppercase">
              SEARCH RESULTS ({searchResults.length})
            </h2>
            <button
              onClick={clearSearch}
              className="text-xs font-mono text-accent hover:underline"
            >
              Clear search
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {searchResults.map((result, i) => (
              <SearchResultCard 
                key={`${result.conversation_id}_${result.chunk_index}_${i}`} 
                result={result} 
                searchQuery={searchQuery}
              />
            ))}
          </div>
        </div>
      ) : hasSearched && !askResponse && searchResults.length === 0 ? (
        <div className="mb-10 border border-border/30 rounded-lg p-10 text-center">
          <div className="text-3xl mb-4">{mode === 'ask' ? '🤔' : '🔍'}</div>
          <p className="text-sm font-mono text-text-secondary mb-2">
            {mode === 'ask' ? 'Could not generate an answer' : 'No results found'}
          </p>
          <p className="text-xs font-mono text-text-muted">
            {mode === 'ask' 
              ? 'Try rephrasing your question or check if the information exists in your history'
              : 'Try different keywords or phrases'}
          </p>
          <button
            onClick={clearSearch}
            className="mt-4 text-xs font-mono text-accent hover:underline"
          >
            Clear {mode === 'ask' ? 'question' : 'search'}
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
          <SectionCard
            title="Recent Decisions"
            items={decisions}
            emptyMessage="No recent decisions"
          />
          <SectionCard
            title="Open Action Items"
            items={actions}
            emptyMessage="No open actions"
          />
          <div className="border border-border rounded-lg p-5">
            <h3 className="text-[11px] font-mono tracking-wider text-text-muted uppercase mb-4">
              Active Projects
            </h3>
            {stats && stats.top_projects.length > 0 ? (
              <div className="space-y-2">
                {stats.top_projects.slice(0, 8).map((project, i) => (
                  <div
                    key={i}
                    onClick={() => {
                      setHandoffProject(project)
                      setShowHandoffModal(true)
                    }}
                    className="flex items-center gap-2 cursor-pointer hover:bg-surface/30 rounded px-2 py-1 -mx-2 transition-colors"
                  >
                    <span className="text-xs font-mono text-purple-400">📁</span>
                    <span className="text-xs font-mono text-text-primary hover:text-accent transition-colors">{project}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="space-y-2">
                {['RecruitOS', 'Jarvis', 'CMP', 'Atlas', 'Eureka'].map((project, i) => (
                  <div
                    key={i}
                    onClick={() => {
                      setHandoffProject(project)
                      setShowHandoffModal(true)
                    }}
                    className="flex items-center gap-2 cursor-pointer hover:bg-surface/30 rounded px-2 py-1 -mx-2 transition-colors"
                  >
                    <span className="text-xs font-mono text-purple-400">📁</span>
                    <span className="text-xs font-mono text-text-secondary hover:text-accent transition-colors">{project}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Collapsible Timeline */}
      {!hasSearched && (
        <div className="border-t border-border pt-8">
          <button
            onClick={() => setTimelineExpanded(!timelineExpanded)}
            className="flex items-center gap-2 text-sm font-mono tracking-wider text-text-muted uppercase mb-6 hover:text-text-primary transition-colors"
          >
            <span>{timelineExpanded ? '▼' : '▶'}</span>
            RECENT TIMELINE ({timelineItems.length})
          </button>
          
          {timelineExpanded && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {timelineItems.map((item, i) => (
                <TimelineItemCard key={`${item.conversation_id}_${item.chunk_index}_${i}`} item={item} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Context Handoff Modal */}
      <ContextHandoffModal
        project={handoffProject}
        isOpen={showHandoffModal}
        onClose={() => setShowHandoffModal(false)}
      />
    </div>
  )
}
