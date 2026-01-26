import { useState, useEffect, useCallback } from 'react'

interface Daily3Item {
  text: string
  done: boolean
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

export function Daily3Page() {
  const [items, setItems] = useState<Daily3Item[]>(loadDaily3)
  const [drafts, setDrafts] = useState<string[]>(['', '', ''])
  const isSet = items.length === 3
  const completed = items.filter((i) => i.done).length

  useEffect(() => {
    if (isSet) saveDaily3(items)
  }, [items, isSet])

  const handleSubmit = useCallback(() => {
    const filled = drafts.filter((d) => d.trim())
    if (filled.length < 3) return
    const newItems = drafts.map((text) => ({ text: text.trim(), done: false }))
    setItems(newItems)
    saveDaily3(newItems)
  }, [drafts])

  const toggleItem = (index: number) => {
    setItems((prev) => {
      const next = prev.map((item, i) =>
        i === index ? { ...item, done: !item.done } : item
      )
      return next
    })
  }

  const resetDay = () => {
    localStorage.removeItem(getTodayKey())
    setItems([])
    setDrafts(['', '', ''])
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
        /* Morning input view */
        <div className="space-y-4">
          <p className="font-mono text-sm text-text-secondary mb-6">
            What are the 3 most important things you need to do today?
          </p>
          {drafts.map((draft, i) => (
            <div key={i} className="flex items-center gap-4">
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
                  i === 0
                    ? 'Most important...'
                    : i === 1
                    ? 'Second priority...'
                    : 'Third priority...'
                }
                className="flex-1 bg-surface border border-border rounded px-4 py-3 font-mono text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent transition-colors"
                autoFocus={i === 0}
              />
            </div>
          ))}
          <button
            onClick={handleSubmit}
            disabled={drafts.filter((d) => d.trim()).length < 3}
            className="mt-6 w-full py-3 rounded font-mono text-sm tracking-wider bg-accent text-white hover:bg-red-700 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
          >
            LOCK IN MY DAILY 3
          </button>
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
              <span
                className={`font-mono text-xs tracking-wider ${
                  allDone ? 'text-green-400' : 'text-text-secondary'
                }`}
              >
                {completed}/3
              </span>
            </div>
            <div className="h-2 bg-surface rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  allDone ? 'bg-green-400' : 'bg-accent'
                }`}
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
                {/* Checkbox */}
                <div
                  className={`shrink-0 w-6 h-6 rounded border-2 flex items-center justify-center transition-all ${
                    item.done
                      ? 'border-green-400 bg-green-400'
                      : 'border-text-muted'
                  }`}
                >
                  {item.done && (
                    <svg
                      className="w-4 h-4 text-black"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={3}
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                  )}
                </div>

                {/* Number + Text */}
                <div className="flex-1 min-w-0">
                  <span className="font-mono text-xs text-text-muted block mb-1">
                    #{i + 1}
                  </span>
                  <span
                    className={`font-mono text-base tracking-wide ${
                      item.done
                        ? 'text-text-muted line-through'
                        : 'text-text-primary'
                    }`}
                  >
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
