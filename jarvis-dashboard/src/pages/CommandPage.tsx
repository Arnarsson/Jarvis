import { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { apiGet, apiPost } from '../api/client.ts'

// --- Types ---

interface HistoryEntry {
  role: 'user' | 'system'
  content: string
  timestamp: Date
}

interface QuickCatchUpResponse {
  query: string
  summary: string
  items_found: number
  sources: Record<string, number>
}

interface MorningBriefResponse {
  date: string
  meetings_today: Array<{ time: string; title: string; attendees: string[] }>
  key_topics: string[]
  briefing: string
  generated_at: string
}

interface SearchResult {
  id: string
  source: string
  text_preview: string
  timestamp: string
  score: number
}

interface SearchResponse {
  results: SearchResult[]
}

// --- Markdown-lite renderer ---

function renderContent(text: string) {
  const lines = text.split('\n')
  return lines.map((line, i) => {
    // Bold headings: **text**
    const boldParts = line.split(/(\*\*[^*]+\*\*)/g)
    const rendered = boldParts.map((part, j) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return (
          <span key={j} className="font-bold text-text-primary">
            {part.slice(2, -2)}
          </span>
        )
      }
      return <span key={j}>{part}</span>
    })

    // Bullet points
    if (line.trimStart().startsWith('- ')) {
      return (
        <div key={i} className="pl-4 py-0.5">
          <span className="text-accent mr-2">-</span>
          {rendered}
        </div>
      )
    }

    // Empty lines become spacing
    if (line.trim() === '') {
      return <div key={i} className="h-2" />
    }

    return (
      <div key={i} className="py-0.5">
        {rendered}
      </div>
    )
  })
}

// --- Component ---

export function CommandPage() {
  const navigate = useNavigate()
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const [input, setInput] = useState('')
  const [searchMode, setSearchMode] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [history])

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const appendHistory = useCallback((role: 'user' | 'system', content: string) => {
    setHistory((prev) => [...prev, { role, content, timestamp: new Date() }])
  }, [])

  // --- Mutations ---

  const quickMutation = useMutation({
    mutationFn: (query: string) =>
      apiPost<QuickCatchUpResponse>('/api/catchup/quick', { query }),
    onSuccess: (data) => {
      const sourceSummary = Object.entries(data.sources || {})
        .map(([s, n]) => `${s}: ${n}`)
        .join(', ')
      const footer = data.items_found
        ? `\n\n**Sources:** ${sourceSummary} (${data.items_found} items)`
        : ''
      appendHistory('system', data.summary + footer)
    },
    onError: (err) => {
      appendHistory('system', `Error: ${err instanceof Error ? err.message : 'Request failed'}`)
    },
  })

  const morningMutation = useMutation({
    mutationFn: () => apiGet<MorningBriefResponse>('/api/catchup/morning'),
    onSuccess: (data) => {
      appendHistory('system', data.briefing)
    },
    onError: (err) => {
      appendHistory('system', `Error: ${err instanceof Error ? err.message : 'Failed to load morning brief'}`)
    },
  })

  const searchMutation = useMutation({
    mutationFn: (query: string) =>
      apiPost<SearchResponse>('/api/search/', { query, limit: 10 }),
    onSuccess: (data) => {
      if (!data.results || data.results.length === 0) {
        appendHistory('system', 'No results found.')
        return
      }
      const formatted = data.results
        .map((r) => {
          const time = new Date(r.timestamp).toLocaleString()
          return `- **[${r.source}]** ${r.text_preview}\n  ${time} (score: ${r.score.toFixed(2)})`
        })
        .join('\n')
      appendHistory('system', `**Search Results** (${data.results.length}):\n\n${formatted}`)
    },
    onError: (err) => {
      appendHistory('system', `Search error: ${err instanceof Error ? err.message : 'Request failed'}`)
    },
  })

  const isLoading = quickMutation.isPending || morningMutation.isPending || searchMutation.isPending

  // --- Handlers ---

  const handleSubmit = useCallback(() => {
    const trimmed = input.trim()
    if (!trimmed || isLoading) return

    appendHistory('user', trimmed)
    setInput('')

    if (searchMode) {
      searchMutation.mutate(trimmed)
    } else {
      quickMutation.mutate(trimmed)
    }
  }, [input, isLoading, searchMode, appendHistory, searchMutation, quickMutation])

  const handleQuickAction = useCallback(
    (command: string) => {
      if (isLoading) return
      appendHistory('user', command)
      quickMutation.mutate(command)
    },
    [isLoading, appendHistory, quickMutation],
  )

  const handleMorningBrief = useCallback(() => {
    navigate('/catchup')
  }, [navigate])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSubmit()
      }
    },
    [handleSubmit],
  )

  // --- Render ---

  return (
    <div className="flex flex-col h-[calc(100vh-theme(spacing.14)-theme(spacing.6)*2)] lg:h-[calc(100vh-theme(spacing.8)*2)]">
      {/* Header */}
      <div className="shrink-0 mb-4">
        <h3 className="section-title">COMMAND</h3>
      </div>

      {/* Morning Brief + Quick Actions */}
      <div className="shrink-0 mb-4 space-y-3">
        {/* Morning brief button */}
        <button
          onClick={handleMorningBrief}
          disabled={isLoading}
          className="w-full sm:w-auto px-6 py-2.5 bg-accent/10 border border-accent/40 text-accent font-mono text-xs tracking-wider uppercase hover:bg-accent/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          MORNING BRIEF
        </button>

        {/* Quick action buttons */}
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => navigate('/catchup')}
            className="px-3 py-1.5 border border-border text-text-secondary font-mono text-[11px] tracking-wider uppercase hover:border-accent hover:text-accent transition-colors"
          >
            CATCH UP
          </button>
          <button
            onClick={() => setSearchMode((prev) => !prev)}
            className={`px-3 py-1.5 border font-mono text-[11px] tracking-wider uppercase transition-colors ${
              searchMode
                ? 'border-accent text-accent bg-accent/10'
                : 'border-border text-text-secondary hover:border-accent hover:text-accent'
            }`}
          >
            SEARCH {searchMode ? 'ON' : ''}
          </button>
          <button
            onClick={() => handleQuickAction("What's on my schedule today?")}
            disabled={isLoading}
            className="px-3 py-1.5 border border-border text-text-secondary font-mono text-[11px] tracking-wider uppercase hover:border-accent hover:text-accent transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            SCHEDULE
          </button>
        </div>
      </div>

      {/* Command history (scrollable) */}
      <div
        ref={scrollRef}
        className="flex-1 min-h-0 overflow-y-auto border border-border bg-surface rounded px-4 py-3 space-y-3"
      >
        {history.length === 0 && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center space-y-2">
              <p className="font-mono text-sm text-text-muted tracking-wider">
                AWAITING COMMAND
              </p>
              <p className="text-xs text-text-muted">
                Type a question or use the quick actions above
              </p>
            </div>
          </div>
        )}

        {history.map((entry, i) => (
          <div key={i} className="group">
            {entry.role === 'user' ? (
              <div className="flex items-start gap-2">
                <span className="text-accent font-mono text-sm font-bold shrink-0 select-none">
                  &gt;
                </span>
                <span className="font-mono text-sm text-accent">
                  {entry.content}
                </span>
              </div>
            ) : (
              <div className="pl-4 text-sm text-text-primary leading-relaxed">
                {renderContent(entry.content)}
              </div>
            )}
            <div className="pl-4 mt-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <span className="font-mono text-[10px] text-text-muted">
                {entry.timestamp.toLocaleTimeString('en-US', {
                  hour12: false,
                  hour: '2-digit',
                  minute: '2-digit',
                  second: '2-digit',
                })}
              </span>
            </div>
          </div>
        ))}

        {/* Loading indicator */}
        {isLoading && (
          <div className="flex items-start gap-2 pl-4">
            <span className="font-mono text-sm text-text-secondary animate-pulse">
              ...
            </span>
          </div>
        )}
      </div>

      {/* Input area */}
      <form
        className="shrink-0 mt-3"
        onSubmit={(e) => {
          e.preventDefault()
          handleSubmit()
        }}
      >
        {/* Search mode indicator */}
        {searchMode && (
          <div className="mb-2 px-3 py-1.5 bg-accent/5 border border-accent/20 text-accent font-mono text-[11px] tracking-wider">
            SEARCH MODE ACTIVE -- results from all sources
          </div>
        )}

        <div className="flex items-center gap-2">
          <span className="text-accent font-mono text-sm font-bold shrink-0 select-none">
            &gt;
          </span>
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={searchMode ? 'Search across all sources...' : 'Type a command...'}
            disabled={isLoading}
            className="flex-1 bg-surface border border-border rounded px-3 py-2 font-mono text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-border-light transition-colors disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="px-4 py-2 border border-accent text-accent font-mono text-xs tracking-wider uppercase hover:bg-accent/10 transition-colors disabled:opacity-30 disabled:cursor-not-allowed shrink-0"
          >
            SEND
          </button>
        </div>
      </form>
    </div>
  )
}
