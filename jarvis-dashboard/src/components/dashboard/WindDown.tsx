import { useState, useEffect } from 'react'

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

function isAfter18(): boolean {
  return new Date().getHours() >= 18
}

function getDaily3Stats(): { completed: number; total: number } {
  try {
    const raw = localStorage.getItem(getTodayKey())
    if (raw) {
      const items: Daily3Item[] = JSON.parse(raw)
      return {
        total: items.length,
        completed: items.filter((i) => i.done).length,
      }
    }
  } catch (err) {
    console.error('Failed to get daily3 progress from localStorage:', err)
  }
  return { completed: 0, total: 0 }
}

function getCaptureCount(): number {
  try {
    const raw = localStorage.getItem('jarvis-captures')
    if (raw) {
      const captures = JSON.parse(raw)
      const today = new Date().toDateString()
      return captures.filter(
        (c: { ts: number }) => new Date(c.ts).toDateString() === today
      ).length
    }
  } catch (err) {
    console.error('Failed to get capture count from localStorage:', err)
  }
  return 0
}

export function WindDown() {
  const [show, setShow] = useState(isAfter18)

  useEffect(() => {
    const interval = setInterval(() => {
      setShow(isAfter18())
    }, 60_000)
    return () => clearInterval(interval)
  }, [])

  if (!show) return null

  const daily3 = getDaily3Stats()
  const captures = getCaptureCount()

  return (
    <div className="mb-10">
      <div className="border border-border rounded-lg p-6 bg-surface/50">
        <h2 className="font-mono text-xs font-bold tracking-widest mb-4" style={{ color: '#DC2626' }}>
          WIND DOWN
        </h2>

        <div className="grid grid-cols-3 gap-4 mb-5">
          <div>
            <p className="font-mono text-2xl font-bold text-text-primary">
              {daily3.completed}
            </p>
            <p className="font-mono text-[10px] text-text-muted tracking-wider">
              TASKS DONE
            </p>
          </div>
          <div>
            <p className="font-mono text-2xl font-bold text-text-primary">
              {captures}
            </p>
            <p className="font-mono text-[10px] text-text-muted tracking-wider">
              CAPTURES
            </p>
          </div>
          <div>
            <p className="font-mono text-2xl font-bold text-text-primary">
              {daily3.total > 0 ? Math.round((daily3.completed / daily3.total) * 100) : 0}%
            </p>
            <p className="font-mono text-[10px] text-text-muted tracking-wider">
              COMPLETION
            </p>
          </div>
        </div>

        <p className="font-mono text-sm text-text-secondary">
          You're done for today. Rest well.
        </p>
      </div>
    </div>
  )
}
