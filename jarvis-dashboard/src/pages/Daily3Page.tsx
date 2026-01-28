import { useState, useEffect, useCallback } from 'react'

const API = import.meta.env.VITE_API_URL || ''

interface Daily3Item {
  text: string
  done: boolean
  source?: string
}

interface Suggestion {
  text: string
  source: string
  urgency: string
  context: string
  source_id?: string
}

interface SuggestionsResponse {
  suggestions: Suggestion[]
  generated_at: string
  sources_analyzed: { emails: number; events: number; decisions: number }
}

function getTodayKey(): string {
  const d = new Date()
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `jarvis-daily3-${yyyy}-${mm}-${dd}`
}

function loadDaily3(): Daily3Item[] {
  try {
    const raw = localStorage.getItem(getTodayKey())
    if (raw) return JSON.parse(raw)
  } catch {}
  return []
}

function saveDaily3(items: Daily3Item[]) {
  localStorage.setItem(getTodayKey(), JSON.stringify(items))
}

const urgencyColor: Record<string, string> = {
  high: 'text-red-400 border-red-500/30 bg-red-500/10',
  medium: 'text-yellow-400 border-yellow-500/30 bg-yellow-500/10',
  low: 'text-blue-400 border-blue-500/30 bg-blue-500/10',
}

const sourceIcon: Record<string, string> = {
  calendar: '📅',
  email: '✉️',
  follow_up: '🔄',
}

export function Daily3Page() {
  const [items, setItems] = useState<Daily3Item[]>(loadDaily3)
  const [drafts, setDrafts] = useState<string[]>(['', '', ''])
  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const [loading, setLoading] = useState(false)
  const [sourcesAnalyzed, setSourcesAnalyzed] = useState<SuggestionsResponse['sources_analyzed'] | null>(null)
  const [selectedSuggestions, setSelectedSuggestions] = useState<Set<number>>(new Set())
  const isSet = items.length === 3
  const completed = items.filter((i) => i.done).length

  // Fetch AI suggestions
  useEffect(() => {
    if (isSet) return // Don't fetch if already set
    setLoading(true)
    fetch(`${API}/api/daily3/suggestions`)
      .then((r) => r.json())
      .then((data: SuggestionsResponse) => {
        setSuggestions(data.suggestions)
        setSourcesAnalyzed(data.sources_analyzed)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [isSet])

  useEffect(() => {
    if (isSet) saveDaily3(items)
  }, [items, isSet])

  const handleSubmit = useCallback(() => {
    const filled = drafts.filter((d) => d.trim())
    if (filled.length < 3) return
    const newItems = drafts.map((text) => ({ text: text.trim(), done: false }))
    setItems(newItems)
    saveDaily3(newItems)
    // Also save to backend
    fetch(`${API}/api/daily3/today`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newItems),
    }).catch(() => {})
  }, [drafts])

  const useSuggestion = (suggestion: Suggestion, index: number) => {
    const newSelected = new Set(selectedSuggestions)
    if (newSelected.has(index)) {
      newSelected.delete(index)
      // Remove from drafts
      const draftIdx = drafts.findIndex((d) => d === suggestion.text)
      if (draftIdx >= 0) {
        const next = [...drafts]
        next[draftIdx] = ''
        setDrafts(next)
      }
    } else {
      if (newSelected.size >= 3) return // Max 3
      newSelected.add(index)
      // Add to first empty draft slot
      const emptyIdx = drafts.findIndex((d) => !d.trim())
      if (emptyIdx >= 0) {
        const next = [...drafts]
        next[emptyIdx] = suggestion.text
        setDrafts(next)
      }
    }
    setSelectedSuggestions(newSelected)
  }

  const toggleItem = (index: number) => {
    setItems((prev) => {
      const next = prev.map((item, i) =>
        i === index ? { ...item, done: !item.done } : item
      )
      return next
    })
    // Sync to backend
    fetch(`${API}/api/daily3/today/${index}/toggle`, { method: 'PATCH' }).catch(() => {})
  }

  const resetDay = () => {
    localStorage.removeItem(getTodayKey())
    setItems([])
    setDrafts(['', '', ''])
    setSelectedSuggestions(new Set())
  }

  const progressPct = isSet ? Math.round((completed / 3) * 100) : 0
  const allDone = completed === 3

  return (
    <div className="max-w-2xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="font-mono text-2xl font-bold text-text-primary tracking-wider mb-1">
          DAILY 3
        </h1>
        <p className="font-mono text-xs text-text-secondary tracking-wider">
          YOUR TOP PRIORITIES FOR TODAY
        </p>
      </div>

      {!isSet ? (
        <div className="space-y-6">
          {/* AI Suggestions */}
          {(suggestions.length > 0 || loading) && (
            <div className="mb-6">
              <div className="flex items-center justify-between mb-3">
                <h2 className="font-mono text-xs text-text-secondary tracking-widest uppercase">
                  💡 Eureka suggests
                </h2>
                {sourcesAnalyzed && (
                  <span className="font-mono text-[10px] text-text-muted">
                    {sourcesAnalyzed.events} events · {sourcesAnalyzed.emails} emails · {sourcesAnalyzed.decisions} action items
                  </span>
                )}
              </div>
              
              {loading ? (
                <div className="text-center py-8">
                  <div className="inline-block animate-spin w-5 h-5 border-2 border-accent border-t-transparent rounded-full mb-2" />
                  <p className="font-mono text-xs text-text-muted">Analyzing calendar, emails, follow-ups...</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {suggestions.map((s, i) => (
                    <button
                      key={i}
                      onClick={() => useSuggestion(s, i)}
                      className={`w-full text-left p-3 rounded-lg border transition-all ${
                        selectedSuggestions.has(i)
                          ? 'border-accent bg-accent/10'
                          : 'border-border bg-surface hover:border-border-hover'
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        {/* Selection indicator */}
                        <div className={`shrink-0 w-5 h-5 rounded border-2 flex items-center justify-center mt-0.5 transition-all ${
                          selectedSuggestions.has(i)
                            ? 'border-accent bg-accent'
                            : 'border-text-muted'
                        }`}>
                          {selectedSuggestions.has(i) && (
                            <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                            </svg>
                          )}
                        </div>
                        
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-sm">{sourceIcon[s.source] || '📋'}</span>
                            <span className="font-mono text-sm text-text-primary">{s.text}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className={`font-mono text-[10px] px-1.5 py-0.5 rounded border ${urgencyColor[s.urgency] || 'text-text-muted'}`}>
                              {s.urgency.toUpperCase()}
                            </span>
                            <span className="font-mono text-[11px] text-text-muted truncate">{s.context}</span>
                          </div>
                        </div>
                      </div>
                    </button>
                  ))}
                  {suggestions.length === 0 && (
                    <p className="font-mono text-xs text-text-muted text-center py-4">
                      No suggestions available — enter your priorities manually below
                    </p>
                  )}
                </div>
              )}
              
              {selectedSuggestions.size > 0 && selectedSuggestions.size < 3 && (
                <p className="font-mono text-[10px] text-text-muted mt-2 text-center">
                  {3 - selectedSuggestions.size} more needed — pick from above or type below
                </p>
              )}
            </div>
          )}

          {/* Manual input */}
          <div>
            <h2 className="font-mono text-xs text-text-secondary tracking-widest uppercase mb-3">
              {suggestions.length > 0 ? 'YOUR PICKS' : 'WHAT ARE YOUR 3 PRIORITIES?'}
            </h2>
            {drafts.map((draft, i) => (
              <div key={i} className="flex items-center gap-4 mb-3">
                <span className="font-mono text-lg text-text-muted w-6 shrink-0">
                  {i + 1}.
                </span>
                <input
                  type="text"
                  value={draft}
                  onChange={(e) => {
                    const next = [...drafts]
                    next[i] = e.target.value
                    setDrafts(next)
                    // Deselect suggestion if user manually edits
                    const matchIdx = suggestions.findIndex((s) => s.text === drafts[i])
                    if (matchIdx >= 0) {
                      const ns = new Set(selectedSuggestions)
                      ns.delete(matchIdx)
                      setSelectedSuggestions(ns)
                    }
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      if (i < 2) {
                        const nextInput = document.querySelector<HTMLInputElement>(
                          `[data-slot="${i + 1}"]`
                        )
                        nextInput?.focus()
                      } else {
                        handleSubmit()
                      }
                    }
                  }}
                  data-slot={i}
                  placeholder={
                    i === 0 ? 'Most important...' : i === 1 ? 'Second priority...' : 'Third priority...'
                  }
                  className="flex-1 bg-surface border border-border rounded px-4 py-3 font-mono text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent transition-colors"
                  autoFocus={i === 0 && suggestions.length === 0}
                />
              </div>
            ))}
            <button
              onClick={handleSubmit}
              disabled={drafts.filter((d) => d.trim()).length < 3}
              className="mt-4 w-full py-3 rounded font-mono text-sm tracking-wider bg-accent text-white hover:bg-red-700 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
            >
              LOCK IN MY DAILY 3
            </button>
          </div>
        </div>
      ) : (
        /* Cards view */
        <div>
          {/* Progress bar */}
          <div className="mb-8">
            <div className="flex items-center justify-between mb-2">
              <span className="font-mono text-xs text-text-secondary tracking-wider">
                PROGRESS
              </span>
              <span className={`font-mono text-xs tracking-wider ${allDone ? 'text-green-400' : 'text-text-secondary'}`}>
                {completed}/3
              </span>
            </div>
            <div className="h-2 bg-surface rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${allDone ? 'bg-green-400' : 'bg-accent'}`}
                style={{ width: `${progressPct}%` }}
              />
            </div>
          </div>

          {/* Celebration */}
          {allDone && (
            <div className="mb-8 p-6 rounded-lg border border-green-500/30 bg-green-500/5 text-center animate-pulse">
              <p className="font-mono text-lg text-green-400 tracking-wider mb-1">
                🎯 ALL 3 COMPLETE
              </p>
              <p className="font-mono text-xs text-green-400/70">
                You crushed it today.
              </p>
            </div>
          )}

          {/* Task cards */}
          <div className="space-y-3">
            {items.map((item, i) => (
              <button
                key={i}
                onClick={() => toggleItem(i)}
                className={`w-full text-left flex items-center gap-4 p-5 rounded-lg border transition-all ${
                  item.done
                    ? 'border-green-500/30 bg-green-500/5'
                    : 'border-border bg-surface hover:border-accent/50'
                }`}
              >
                <div className={`shrink-0 w-6 h-6 rounded border-2 flex items-center justify-center transition-all ${
                  item.done ? 'border-green-400 bg-green-400' : 'border-text-muted'
                }`}>
                  {item.done && (
                    <svg className="w-4 h-4 text-black" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <span className="font-mono text-xs text-text-muted block mb-1">#{i + 1}</span>
                  <span className={`font-mono text-base tracking-wide ${
                    item.done ? 'text-text-muted line-through' : 'text-text-primary'
                  }`}>
                    {item.text}
                  </span>
                </div>
              </button>
            ))}
          </div>

          {/* Reset */}
          <button
            onClick={resetDay}
            className="mt-8 font-mono text-xs text-text-muted hover:text-accent tracking-wider transition-colors"
          >
            RESET TODAY'S DAILY 3
          </button>
        </div>
      )}
    </div>
  )
}
