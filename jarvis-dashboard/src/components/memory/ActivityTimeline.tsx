import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../../api/client.ts'

/* ───────────────── Types ───────────────── */

interface HourBlock {
  hour: number
  start: string
  end: string
  capture_count: number
  summary: string
  apps: string[]
  topics: string[]
  sample_capture_id: string | null
}

interface DaySummary {
  date: string
  total_captures: number
  active_hours: number
  hours: HourBlock[]
}

/* ───────────────── Helpers ───────────────── */

function formatHour(h: number): string {
  return `${String(h).padStart(2, '0')}:00`
}

const APP_ICONS: Record<string, string> = {
  'VS Code': '📝',
  'Terminal': '⬛',
  'Slack': '💬',
  'Browser': '🌐',
  'Telegram': '✈️',
  'Email': '📧',
  'Claude': '🤖',
  'GitHub': '🐙',
  'Docker': '🐳',
  'Calendar': '📅',
}

function appIcon(app: string): string {
  return APP_ICONS[app] || '📱'
}

/* ───────────────── Hour Card ───────────────── */

function HourCard({ block, expanded, onToggle }: {
  block: HourBlock
  expanded: boolean
  onToggle: () => void
}) {
  return (
    <div
      className="border border-border/40 rounded-lg overflow-hidden transition-all hover:border-border-light cursor-pointer"
      onClick={onToggle}
    >
      {/* Header */}
      <div className="flex items-center gap-4 px-4 py-3">
        {/* Time */}
        <div className="shrink-0 w-14">
          <span className="font-mono text-lg font-bold text-text-primary">
            {formatHour(block.hour)}
          </span>
        </div>

        {/* App icons */}
        <div className="flex items-center gap-1 shrink-0">
          {block.apps.slice(0, 5).map((app) => (
            <span key={app} className="text-sm" title={app}>
              {appIcon(app)}
            </span>
          ))}
        </div>

        {/* Summary */}
        <div className="flex-1 min-w-0">
          <p className="text-[13px] text-text-primary truncate">
            {block.topics.length > 0
              ? block.topics.join(' · ')
              : block.summary}
          </p>
        </div>

        {/* Capture count */}
        <div className="shrink-0 flex items-center gap-2">
          <span className="font-mono text-[11px] text-text-muted">
            {block.capture_count} cap{block.capture_count !== 1 ? 's' : ''}
          </span>
          <svg
            className={`w-3.5 h-3.5 text-text-muted transition-transform ${expanded ? 'rotate-180' : ''}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="px-4 pb-4 pt-1 border-t border-border/30 space-y-3">
          {/* Apps */}
          <div className="flex flex-wrap gap-2">
            {block.apps.map((app) => (
              <span
                key={app}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-mono bg-surface border border-border/50 text-text-secondary"
              >
                {appIcon(app)} {app}
              </span>
            ))}
          </div>

          {/* Topics */}
          {block.topics.length > 0 && (
            <div>
              <p className="font-mono text-[10px] tracking-wider text-text-muted uppercase mb-1.5">
                DETECTED ACTIVITY
              </p>
              <ul className="space-y-1">
                {block.topics.map((topic, i) => (
                  <li key={i} className="text-[12px] text-text-secondary flex items-start gap-2">
                    <span className="text-text-muted mt-0.5">›</span>
                    {topic}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Time range */}
          <p className="font-mono text-[10px] text-text-muted">
            {new Date(block.start).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            {' — '}
            {new Date(block.end).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            {' · '}
            {block.capture_count} screenshot{block.capture_count !== 1 ? 's' : ''} analyzed
          </p>

          {/* Sample capture thumbnail */}
          {block.sample_capture_id && (
            <div className="mt-2">
              <p className="font-mono text-[10px] tracking-wider text-text-muted uppercase mb-1.5">
                SAMPLE CAPTURE
              </p>
              <img
                src={`/captures/2026/01/${block.start.slice(8, 10)}/${block.sample_capture_id}.jpg`}
                alt={`Screen capture at ${formatHour(block.hour)}`}
                className="w-full max-w-md rounded border border-border/30"
                loading="lazy"
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/* ───────────────── Empty Hours ───────────────── */

function InactiveGap({ from, to }: { from: number; to: number }) {
  if (to - from <= 1) return null
  return (
    <div className="flex items-center gap-3 px-4 py-1.5">
      <span className="font-mono text-[11px] text-text-muted/50">
        {formatHour(from + 1)} — {formatHour(to - 1)}
      </span>
      <div className="flex-1 border-t border-border/20" />
      <span className="font-mono text-[10px] text-text-muted/30">inactive</span>
    </div>
  )
}

/* ───────────────── Main Component ───────────────── */

export function ActivityTimeline() {
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [expandedHour, setExpandedHour] = useState<number | null>(null)

  const dateParam = selectedDate || new Date().toISOString().slice(0, 10)

  const { data, isLoading, isError } = useQuery<DaySummary>({
    queryKey: ['activity', 'summary', dateParam],
    queryFn: async () => {
      try {
        return await apiGet<DaySummary>(`/api/activity/summary?date=${dateParam}`)
      } catch {
        return { date: dateParam, total_captures: 0, active_hours: 0, hours: [] }
      }
    },
    staleTime: 120_000,
  })

  // Day navigation
  const goDay = (delta: number) => {
    const current = new Date(dateParam + 'T12:00:00')
    current.setDate(current.getDate() + delta)
    setSelectedDate(current.toISOString().slice(0, 10))
    setExpandedHour(null)
  }

  const isToday = dateParam === new Date().toISOString().slice(0, 10)

  const formatDateLabel = (d: string) => {
    const dt = new Date(d + 'T12:00:00')
    if (isToday) return 'Today'
    const yesterday = new Date()
    yesterday.setDate(yesterday.getDate() - 1)
    if (d === yesterday.toISOString().slice(0, 10)) return 'Yesterday'
    return dt.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })
  }

  return (
    <section className="mb-10">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <h2 className="text-xs font-mono tracking-widest text-text-muted uppercase">
            ACTIVITY TIMELINE
          </h2>
          {data && data.total_captures > 0 && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-blue-500/10 border border-blue-500/20">
              <span className="h-1.5 w-1.5 rounded-full bg-blue-400" />
              <span className="text-[10px] font-mono text-blue-400 tracking-wider">
                {data.active_hours}h active · {data.total_captures} captures
              </span>
            </div>
          )}
        </div>

        {/* Day nav */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => goDay(-1)}
            className="p-1.5 text-text-muted hover:text-text-primary transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <span className="font-mono text-[13px] text-text-primary min-w-[100px] text-center">
            {formatDateLabel(dateParam)}
          </span>
          <button
            onClick={() => goDay(1)}
            disabled={isToday}
            className="p-1.5 text-text-muted hover:text-text-primary transition-colors disabled:opacity-20"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="flex items-center gap-2 text-text-muted text-xs font-mono py-8">
          <span className="inline-block h-2 w-2 rounded-full bg-blue-400 animate-pulse" />
          Analyzing screen activity…
        </div>
      )}

      {/* Error */}
      {isError && (
        <div className="border border-red-500/20 rounded-lg p-4 bg-red-500/5">
          <p className="text-red-400/70 text-xs font-mono">Activity data unavailable</p>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && data && data.hours.length === 0 && (
        <div className="border border-border/30 rounded-lg p-8 text-center">
          <div className="text-3xl mb-3">🌙</div>
          <p className="text-sm font-mono text-text-secondary">No screen activity recorded</p>
          <p className="text-xs font-mono text-text-muted mt-1">The capture agent wasn't running or no OCR data available</p>
        </div>
      )}

      {/* Hour blocks */}
      {data && data.hours.length > 0 && (
        <div className="space-y-1">
          {data.hours.map((block, i) => (
            <div key={block.hour}>
              {/* Show gap between non-consecutive hours */}
              {i > 0 && <InactiveGap from={data.hours[i - 1].hour} to={block.hour} />}
              <HourCard
                block={block}
                expanded={expandedHour === block.hour}
                onToggle={() => setExpandedHour(expandedHour === block.hour ? null : block.hour)}
              />
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
