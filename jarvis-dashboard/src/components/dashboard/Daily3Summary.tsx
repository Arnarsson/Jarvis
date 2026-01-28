import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

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
    if (raw) {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed)) return parsed
      if (parsed?.tasks && Array.isArray(parsed.tasks)) return parsed.tasks
    }
  } catch (err) {
    console.error('Failed to parse daily3 from localStorage:', err)
  }
  return []
}

export function Daily3Summary() {
  const [items, setItems] = useState<Daily3Item[]>(loadDaily3)

  // Poll localStorage every 5s
  useEffect(() => {
    const interval = setInterval(() => setItems(loadDaily3()), 5_000)
    return () => clearInterval(interval)
  }, [])

  const isSet = items.length === 3
  const completed = items.filter((i) => i.done).length
  const allDone = completed === 3
  const progressPct = isSet ? Math.round((completed / 3) * 100) : 0

  return (
    <div className="mb-8">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-mono text-[11px] text-text-secondary tracking-widest uppercase">
          🎯 DAILY 3
        </h3>
        <Link
          to="/daily3"
          className="font-mono text-[10px] text-text-muted hover:text-accent tracking-wider transition-colors"
        >
          {isSet ? 'VIEW →' : 'SET PRIORITIES →'}
        </Link>
      </div>

      {!isSet ? (
        /* Not set yet */
        <Link
          to="/daily3"
          className="block p-5 border border-dashed border-border/60 rounded-lg bg-surface/30 hover:border-accent/40 hover:bg-surface/50 transition-all text-center group"
        >
          <p className="font-mono text-sm text-text-secondary group-hover:text-accent transition-colors">
            Set your 3 priorities for today
          </p>
          <p className="font-mono text-[11px] text-text-muted mt-1">
            Focus on what matters most
          </p>
        </Link>
      ) : (
        /* Tasks summary */
        <div className="border border-border/50 rounded-lg bg-surface/40 overflow-hidden">
          {/* Progress bar */}
          <div className="px-4 pt-3 pb-2">
            <div className="flex items-center justify-between mb-1.5">
              <span className={`font-mono text-[11px] tracking-wider ${
                allDone ? 'text-green-400' : 'text-text-secondary'
              }`}>
                {allDone ? '✓ ALL COMPLETE' : `${completed}/3 DONE`}
              </span>
              <span className="font-mono text-[10px] text-text-muted">
                {progressPct}%
              </span>
            </div>
            <div className="h-1.5 bg-border/30 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-700 ease-out ${
                  allDone ? 'bg-green-400' : 'bg-accent'
                }`}
                style={{ width: `${progressPct}%` }}
              />
            </div>
          </div>

          {/* Tasks */}
          <div className="px-4 pb-3 space-y-1.5">
            {items.map((item, i) => (
              <div
                key={i}
                className="flex items-center gap-3 py-1.5"
              >
                <div className={`shrink-0 w-4 h-4 rounded border flex items-center justify-center transition-all ${
                  item.done ? 'border-green-400 bg-green-400' : 'border-text-muted/50'
                }`}>
                  {item.done && (
                    <svg className="w-2.5 h-2.5 text-black" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </div>
                <span className={`font-mono text-[13px] truncate ${
                  item.done ? 'text-text-muted line-through' : 'text-text-primary'
                }`}>
                  {item.text}
                </span>
              </div>
            ))}
          </div>

          {/* Quick action */}
          {!allDone && (
            <Link
              to="/focus"
              className="block px-4 py-2.5 border-t border-border/30 font-mono text-[11px] text-text-muted hover:text-accent hover:bg-surface/60 tracking-wider transition-all text-center"
            >
              ⏱ START FOCUS SESSION
            </Link>
          )}
        </div>
      )}
    </div>
  )
}
