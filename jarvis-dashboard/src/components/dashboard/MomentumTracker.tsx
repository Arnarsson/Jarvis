import { useState, useEffect, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../../api/client.ts'

/* ───────────────── Types ───────────────── */

interface TimelineCapture {
  id: string
  timestamp: string
  app?: string
  window_title?: string
}

interface TimelineResponse {
  captures: TimelineCapture[]
}

/* ───────────────── Daily 3 helpers ───────────────── */

interface Daily3Task {
  text: string
  done: boolean
  completedAt?: number // epoch ms
}

function getTodayKey(): string {
  const d = new Date()
  return `jarvis-daily3-${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function getDaily3Tasks(): Daily3Task[] {
  try {
    const raw = localStorage.getItem(getTodayKey())
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed)) return parsed
    if (parsed?.tasks && Array.isArray(parsed.tasks)) return parsed.tasks
    return []
  } catch {
    return []
  }
}

/* ───────────────── Context-switch detection ───────────────── */

function detectContextSwitches(captures: TimelineCapture[], windowMinutes = 30): { count: number; windowMin: number } {
  const now = Date.now()
  const cutoff = now - windowMinutes * 60 * 1000

  const recent = captures
    .filter((c) => new Date(c.timestamp).getTime() >= cutoff)
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())

  if (recent.length < 2) return { count: 0, windowMin: windowMinutes }

  let switches = 0
  for (let i = 1; i < recent.length; i++) {
    const prev = recent[i - 1].app || recent[i - 1].window_title || ''
    const curr = recent[i].app || recent[i].window_title || ''
    if (prev && curr && prev !== curr) switches++
  }

  return { count: switches, windowMin: windowMinutes }
}

/* ───────────────── Component ───────────────── */

export function MomentumTracker() {
  const [tasks, setTasks] = useState<Daily3Task[]>([])

  // Poll localStorage every 10s
  useEffect(() => {
    setTasks(getDaily3Tasks())
    const interval = setInterval(() => setTasks(getDaily3Tasks()), 10_000)
    return () => clearInterval(interval)
  }, [])

  // Fetch timeline for context-switch detection
  const { data: timeline } = useQuery({
    queryKey: ['timeline', 'momentum'],
    queryFn: async () => {
      try {
        return await apiGet<TimelineResponse>('/api/timeline/')
      } catch {
        return { captures: [] }
      }
    },
    refetchInterval: 60_000,
    staleTime: 30_000,
  })

  const completedTasks = tasks.filter((t) => t.done)
  const completedCount = completedTasks.length

  // "On a roll" detection — multiple tasks done within 2 hours
  const recentCompletions = useMemo(() => {
    const twoHoursAgo = Date.now() - 2 * 60 * 60 * 1000
    return completedTasks.filter((t) => t.completedAt && t.completedAt >= twoHoursAgo)
  }, [completedTasks])

  const onARoll = recentCompletions.length >= 2

  // Context-switch detection
  const switches = useMemo(() => {
    if (!timeline?.captures?.length) return null
    const result = detectContextSwitches(timeline.captures)
    return result.count >= 5 ? result : null
  }, [timeline])

  // Nothing to show yet
  if (completedCount === 0 && !switches) return null

  return (
    <div className="border border-border/60 rounded-lg p-4 bg-surface/40 mb-6">
      {/* Momentum streak */}
      {completedCount > 0 && (
        <div className="flex items-center gap-3">
          <span className="text-2xl">{onARoll ? '⚡' : '🔥'}</span>
          <div>
            <p className="text-[14px] text-text-primary font-medium">
              {onARoll
                ? `On a roll — ${recentCompletions.length} in 2 hours`
                : `${completedCount} task${completedCount !== 1 ? 's' : ''} done today`}
            </p>
            {completedCount < 3 && (
              <p className="text-[11px] text-text-secondary mt-0.5">
                {3 - completedCount} more to complete your Daily 3
              </p>
            )}
            {completedCount >= 3 && (
              <p className="text-[11px] text-success mt-0.5">
                ✓ Daily 3 complete — excellent focus
              </p>
            )}
          </div>
        </div>
      )}

      {/* Context-switch nudge */}
      {switches && (
        <div className={`flex items-center gap-3 ${completedCount > 0 ? 'mt-3 pt-3 border-t border-border/40' : ''}`}>
          <span className="text-2xl">🔄</span>
          <div>
            <p className="text-[13px] text-text-secondary">
              You've switched apps{' '}
              <span className="text-warning font-medium">{switches.count} times</span>{' '}
              in {switches.windowMin} min
            </p>
            <p className="text-[11px] text-text-muted mt-0.5">
              Want to pick one thing to focus on?
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
