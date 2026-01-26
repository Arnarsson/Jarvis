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
    if (raw) return JSON.parse(raw)
  } catch {}
  return []
}

export function TodaysFocus() {
  const [items, setItems] = useState<Daily3Item[]>(loadDaily3)

  // Re-check every 10s in case Daily3Page is used in another tab
  useEffect(() => {
    const interval = setInterval(() => {
      setItems(loadDaily3())
    }, 10_000)
    return () => clearInterval(interval)
  }, [])

  const completed = items.filter((i) => i.done).length

  if (items.length === 0) {
    return (
      <div className="mb-10">
        <div className="border border-border rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-mono text-xs font-bold text-text-secondary tracking-widest">
              TODAY'S FOCUS
            </h2>
            <Link
              to="/daily3"
              className="font-mono text-xs text-accent hover:text-red-400 tracking-wider transition-colors"
            >
              SET DAILY 3 →
            </Link>
          </div>
          <p className="font-mono text-sm text-text-muted">
            No priorities set yet. Start your day with intention.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="mb-10">
      <div className="border border-border rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-mono text-xs font-bold text-text-secondary tracking-widest">
            TODAY'S FOCUS
          </h2>
          <div className="flex items-center gap-3">
            <span
              className={`font-mono text-xs tracking-wider ${
                completed === 3 ? 'text-green-400' : 'text-text-muted'
              }`}
            >
              {completed}/3
            </span>
            <Link
              to="/daily3"
              className="font-mono text-xs text-accent hover:text-red-400 tracking-wider transition-colors"
            >
              VIEW →
            </Link>
          </div>
        </div>

        {/* Progress bar */}
        <div className="h-1 bg-surface rounded-full overflow-hidden mb-4">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              completed === 3 ? 'bg-green-400' : 'bg-accent'
            }`}
            style={{ width: `${Math.round((completed / 3) * 100)}%` }}
          />
        </div>

        {/* Items */}
        <div className="space-y-2">
          {items.map((item, i) => (
            <div key={i} className="flex items-center gap-3">
              <div
                className={`shrink-0 w-4 h-4 rounded border flex items-center justify-center ${
                  item.done
                    ? 'border-green-400 bg-green-400'
                    : 'border-text-muted'
                }`}
              >
                {item.done && (
                  <svg
                    className="w-3 h-3 text-black"
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
              <span
                className={`font-mono text-sm ${
                  item.done
                    ? 'text-text-muted line-through'
                    : 'text-text-primary'
                }`}
              >
                {item.text}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
