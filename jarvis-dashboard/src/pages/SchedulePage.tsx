import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../api/client.ts'
import type { CalendarEvent } from '../api/calendar.ts'
import { LoadingSkeleton } from '../components/ui/LoadingSkeleton.tsx'

// --- Types ---

interface UpcomingEventsResponse {
  events: CalendarEvent[]
  count: number
}

interface StoredEvent {
  id: string
  summary: string
  start_time: string
  end_time: string
  location: string | null
  meeting_link: string | null
  attendees: { email?: string }[]
}

type ViewMode = 'today' | 'week'

// --- Helpers ---

function formatTime(isoString: string): string {
  const date = new Date(isoString)
  return date.toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatDayLabel(date: Date): string {
  return date.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  })
}

function getPriority(summary: string): 'priority' | 'routine' {
  const lower = summary.toLowerCase()
  if (
    lower.includes('board') ||
    lower.includes('investor') ||
    lower.includes('strategy') ||
    lower.includes('series') ||
    lower.includes('review') ||
    lower.includes('interview') ||
    lower.includes('1:1')
  ) {
    return 'priority'
  }
  return 'routine'
}

function getAttendeeLabel(attendees: string[]): string {
  if (attendees.length === 0) return ''
  const first = attendees[0].split('@')[0].toUpperCase()
  const extra = attendees.length > 1 ? ` +${attendees.length - 1}` : ''
  return `${first}${extra}`
}

/** Get Monday 00:00 of the current week (ISO week, Monday start). */
function getWeekStart(date: Date): Date {
  const d = new Date(date)
  const day = d.getDay()
  const diff = day === 0 ? -6 : 1 - day
  d.setDate(d.getDate() + diff)
  d.setHours(0, 0, 0, 0)
  return d
}

/** Get Sunday 23:59:59 of the current week. */
function getWeekEnd(date: Date): Date {
  const start = getWeekStart(date)
  const end = new Date(start)
  end.setDate(end.getDate() + 6)
  end.setHours(23, 59, 59, 999)
  return end
}

function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  )
}

function toISODate(date: Date): string {
  return date.toISOString()
}

function isPastEvent(endTime: string): boolean {
  return new Date(endTime).getTime() < Date.now()
}

function isCurrentEvent(start: string, end: string): boolean {
  const now = Date.now()
  return new Date(start).getTime() <= now && new Date(end).getTime() > now
}

const DAY_LABELS = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'] as const

// --- Data hooks ---

function useTodayEvents() {
  return useQuery<CalendarEvent[]>({
    queryKey: ['schedule', 'today'],
    queryFn: async () => {
      const now = new Date()
      const dayStart = new Date(now)
      dayStart.setHours(0, 0, 0, 0)
      const dayEnd = new Date(now)
      dayEnd.setHours(23, 59, 59, 999)

      try {
        // Fetch ALL events for today (including past ones)
        const data = await apiGet<StoredEvent[] | { events: CalendarEvent[] }>(
          `/api/calendar/events?start_date=${dayStart.toISOString()}&end_date=${dayEnd.toISOString()}&limit=50`,
        )
        const events = Array.isArray(data) ? data : ((data as any).events ?? [])
        // Normalize field names (stored events use start_time/end_time)
        return events.map((e: any) => ({
          id: e.id,
          summary: e.summary,
          start: e.start || e.start_time,
          end: e.end || e.end_time,
          location: e.location ?? null,
          meeting_link: e.meeting_link ?? null,
          attendees: Array.isArray(e.attendees)
            ? e.attendees.map((a: any) => (typeof a === 'string' ? a : a.email || ''))
            : [],
        }))
      } catch {
        // Fallback: use upcoming endpoint and filter to today
        try {
          const data = await apiGet<UpcomingEventsResponse>(
            '/api/calendar/events/upcoming?limit=50',
          )
          return (data.events ?? []).filter((e) => {
            const start = new Date(e.start)
            return isSameDay(start, now)
          })
        } catch {
          return []
        }
      }
    },
    refetchInterval: 60_000,
  })
}

function useWeekEvents() {
  const now = new Date()
  const weekStart = getWeekStart(now)
  const weekEnd = getWeekEnd(now)

  return useQuery<StoredEvent[]>({
    queryKey: ['schedule', 'week', weekStart.toISOString()],
    queryFn: async () => {
      try {
        const data = await apiGet<StoredEvent[]>(
          `/api/calendar/events?start_date=${toISODate(weekStart)}&end_date=${toISODate(weekEnd)}&limit=100`,
        )
        return Array.isArray(data) ? data : []
      } catch {
        return []
      }
    },
    refetchInterval: 60_000,
  })
}

// --- Sub-components ---

function ViewToggle({
  active,
  onChange,
}: {
  active: ViewMode
  onChange: (mode: ViewMode) => void
}) {
  const modes: ViewMode[] = ['today', 'week']
  return (
    <div className="flex gap-2 mb-6">
      {modes.map((mode) => (
        <button
          key={mode}
          onClick={() => onChange(mode)}
          className={`font-mono text-[11px] tracking-wider uppercase px-3 py-1.5 border transition-colors ${
            active === mode
              ? 'border-accent text-accent bg-accent/10'
              : 'border-border text-text-secondary hover:text-text-primary hover:border-border-light'
          }`}
        >
          {mode === 'today' ? 'TODAY' : 'WEEK'}
        </button>
      ))}
    </div>
  )
}

function NowIndicator() {
  const now = new Date()
  const timeStr = now.toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
  })
  return (
    <div className="flex items-center gap-3 py-1">
      <span className="font-mono text-[11px] text-accent tracking-wider font-bold">
        {timeStr}
      </span>
      <div className="flex-1 flex items-center gap-2">
        <div className="w-2 h-2 rounded-full bg-accent shadow-[0_0_6px_theme(colors.accent)]" />
        <div className="flex-1 h-px bg-accent/50" />
      </div>
      <span className="font-mono text-[10px] text-accent tracking-wider">NOW</span>
    </div>
  )
}

function EventCard({ event, dimmed, active }: { event: CalendarEvent; dimmed?: boolean; active?: boolean }) {
  const priority = getPriority(event.summary)
  const attendeeLabel = getAttendeeLabel(event.attendees)
  const isPriority = priority === 'priority'

  return (
    <div
      className={`flex items-start gap-4 py-4 border-b border-border/50 last:border-b-0 transition-opacity ${
        dimmed ? 'opacity-40' : ''
      } ${active ? 'bg-accent/5 -mx-2 px-2 rounded' : ''}`}
    >
      {/* Time column */}
      <div className="shrink-0 w-14 pt-0.5">
        <span className={`font-mono text-[13px] tracking-wide ${
          dimmed ? 'text-text-muted line-through' : active ? 'text-accent' : 'text-text-secondary'
        }`}>
          {formatTime(event.start)}
        </span>
      </div>

      {/* Event card with left border */}
      <div
        className={`flex-1 min-w-0 pl-4 border-l-2 ${
          active ? 'border-accent' : isPriority ? 'border-accent' : dimmed ? 'border-border/50' : 'border-border'
        }`}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <p className={`text-[15px] font-medium ${
              dimmed ? 'text-text-muted' : 'text-text-primary'
            }`}>
              {event.summary}
              {active && (
                <span className="ml-2 inline-block w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
              )}
            </p>
            <div className="flex flex-wrap items-center gap-x-3 mt-1">
              <span className={`text-[12px] font-mono tracking-wide ${
                dimmed ? 'text-text-muted' : 'text-text-secondary'
              }`}>
                {formatTime(event.start)} &mdash; {formatTime(event.end)}
              </span>
              {event.location && (
                <span className={`text-[12px] truncate ${
                  dimmed ? 'text-text-muted' : 'text-text-secondary'
                }`}>
                  {event.location}
                </span>
              )}
              {attendeeLabel && (
                <span className={`text-[12px] font-mono tracking-wide ${
                  dimmed ? 'text-text-muted' : 'text-text-secondary'
                }`}>
                  {attendeeLabel}
                </span>
              )}
            </div>
          </div>
          <span
            className={`shrink-0 font-mono text-[10px] tracking-wider px-2.5 py-1 border ${
              dimmed
                ? 'border-border/30 text-text-muted bg-border/10'
                : isPriority
                  ? 'border-accent/40 text-accent bg-accent/10'
                  : 'border-border text-text-secondary bg-border/30'
            }`}
          >
            {isPriority ? 'PRIORITY' : 'ROUTINE'}
          </span>
        </div>
      </div>
    </div>
  )
}

function TodayView() {
  const { data: events, isLoading, isError } = useTodayEvents()

  if (isLoading) return <LoadingSkeleton lines={6} />

  if (isError) {
    return (
      <p className="text-sm text-text-secondary">
        Unable to load today's events
      </p>
    )
  }

  if (!events || events.length === 0) {
    return (
      <div className="py-8 text-center space-y-2">
        <p className="font-mono text-sm text-text-muted tracking-wider">NO EVENTS TODAY</p>
        <p className="text-xs text-text-muted">Schedule is clear</p>
      </div>
    )
  }

  const sorted = [...events].sort(
    (a, b) => new Date(a.start).getTime() - new Date(b.start).getTime(),
  )

  // Find where "now" falls in the timeline
  let nowInserted = false

  return (
    <div>
      {/* Summary bar */}
      <div className="flex items-center gap-4 mb-4 py-2 px-3 bg-surface border border-border/30 rounded">
        <span className="font-mono text-[11px] text-text-secondary tracking-wider">
          {sorted.length} EVENT{sorted.length !== 1 ? 'S' : ''}
        </span>
        <span className="text-border">|</span>
        <span className="font-mono text-[11px] text-text-secondary tracking-wider">
          {sorted.filter(e => !isPastEvent(e.end)).length} REMAINING
        </span>
        <span className="text-border">|</span>
        <span className="font-mono text-[11px] text-text-secondary tracking-wider">
          {sorted.filter(e => isPastEvent(e.end)).length} DONE
        </span>
      </div>

      {sorted.map((event, i) => {
        const past = isPastEvent(event.end)
        const current = isCurrentEvent(event.start, event.end)
        const elements: React.ReactNode[] = []

        // Insert NOW indicator before the first non-past event
        if (!nowInserted && !past) {
          // Check if this is truly future (not current)
          if (!current || i === 0) {
            // Only show NOW line between past and future events (not mid-event)
            const prevEvent = i > 0 ? sorted[i - 1] : null
            if (prevEvent && isPastEvent(prevEvent.end) && !current) {
              elements.push(<NowIndicator key="now-indicator" />)
            } else if (i === 0 && !current) {
              elements.push(<NowIndicator key="now-indicator" />)
            }
          }
          nowInserted = true
        }

        elements.push(
          <EventCard
            key={event.id}
            event={event}
            dimmed={past}
            active={current}
          />
        )

        // If current event, show NOW after it
        if (current) {
          nowInserted = true
        }

        return elements
      })}

      {/* If all events are past, show NOW at the end */}
      {sorted.every(e => isPastEvent(e.end)) && <NowIndicator />}
    </div>
  )
}

function WeekView() {
  const { data: storedEvents, isLoading, isError } = useWeekEvents()

  const now = new Date()
  const weekStart = getWeekStart(now)

  // Build the 7 days of the week
  const days = useMemo(() => {
    return Array.from({ length: 7 }, (_, i) => {
      const date = new Date(weekStart)
      date.setDate(date.getDate() + i)
      return date
    })
  }, [weekStart.toISOString()])

  // Group events by day index
  const eventsByDay = useMemo(() => {
    const grouped: Map<number, StoredEvent[]> = new Map()
    for (let i = 0; i < 7; i++) grouped.set(i, [])

    if (storedEvents) {
      for (const event of storedEvents) {
        const eventDate = new Date(event.start_time)
        for (let i = 0; i < 7; i++) {
          if (isSameDay(eventDate, days[i])) {
            grouped.get(i)!.push(event)
            break
          }
        }
      }
      // Sort each day's events by time
      for (let i = 0; i < 7; i++) {
        grouped.get(i)!.sort(
          (a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime()
        )
      }
    }

    return grouped
  }, [storedEvents, days])

  // Find today's index
  const todayIndex = useMemo(() => {
    for (let i = 0; i < 7; i++) {
      if (isSameDay(days[i], now)) return i
    }
    return -1
  }, [days, now.toDateString()])

  if (isLoading) return <LoadingSkeleton lines={6} />

  if (isError) {
    return (
      <p className="text-sm text-text-secondary">
        Unable to load week events
      </p>
    )
  }

  return (
    <div className="space-y-1">
      {days.map((day, i) => {
        const dayEvents = eventsByDay.get(i) || []
        const isToday = i === todayIndex
        const isPastDay = day.getTime() < new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()

        return (
          <div
            key={i}
            className={`border transition-colors ${
              isToday
                ? 'border-accent/40 bg-accent/5'
                : isPastDay
                  ? 'border-border/30 opacity-60'
                  : 'border-border/40 bg-surface'
            }`}
          >
            {/* Day header */}
            <div className={`flex items-center justify-between px-4 py-2.5 border-b ${
              isToday ? 'border-accent/30' : 'border-border/30'
            }`}>
              <div className="flex items-center gap-3">
                <span className={`font-mono text-[12px] tracking-wider font-bold ${
                  isToday ? 'text-accent' : isPastDay ? 'text-text-muted' : 'text-text-primary'
                }`}>
                  {DAY_LABELS[i]}
                </span>
                <span className={`font-mono text-[11px] ${
                  isToday ? 'text-accent/70' : 'text-text-muted'
                }`}>
                  {formatDayLabel(day)}
                </span>
                {isToday && (
                  <span className="font-mono text-[9px] tracking-wider px-2 py-0.5 bg-accent/20 text-accent border border-accent/30">
                    TODAY
                  </span>
                )}
              </div>
              <span className={`font-mono text-[11px] tracking-wider ${
                dayEvents.length > 0 ? 'text-text-secondary' : 'text-text-muted'
              }`}>
                {dayEvents.length > 0
                  ? `${dayEvents.length} event${dayEvents.length !== 1 ? 's' : ''}`
                  : '—'}
              </span>
            </div>

            {/* Events list */}
            {dayEvents.length > 0 && (
              <div className="px-4 py-1">
                {dayEvents.map((ev) => {
                  const past = isPastEvent(ev.end_time)
                  const current = isCurrentEvent(ev.start_time, ev.end_time)
                  const priority = getPriority(ev.summary)
                  const isPriorityEvent = priority === 'priority'
                  const attendees = Array.isArray(ev.attendees)
                    ? ev.attendees.map((a: any) => typeof a === 'string' ? a : a.email || '')
                    : []
                  const attendeeLabel = getAttendeeLabel(attendees)

                  return (
                    <div
                      key={ev.id}
                      className={`flex items-center gap-3 py-2.5 border-b border-border/20 last:border-b-0 ${
                        past ? 'opacity-40' : ''
                      } ${current ? 'bg-accent/5 -mx-2 px-2 rounded' : ''}`}
                    >
                      <span className={`font-mono text-[12px] tracking-wide shrink-0 w-12 ${
                        current ? 'text-accent font-bold' : past ? 'text-text-muted' : 'text-text-secondary'
                      }`}>
                        {formatTime(ev.start_time)}
                      </span>
                      <div className={`w-0.5 h-4 shrink-0 ${
                        current ? 'bg-accent' : isPriorityEvent ? 'bg-accent/60' : 'bg-border'
                      }`} />
                      <div className="flex-1 min-w-0">
                        <span className={`text-[13px] ${
                          past ? 'text-text-muted' : 'text-text-primary'
                        }`}>
                          {ev.summary}
                          {current && (
                            <span className="ml-2 inline-block w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
                          )}
                        </span>
                        {attendeeLabel && (
                          <span className="ml-2 text-[11px] text-text-muted font-mono">
                            {attendeeLabel}
                          </span>
                        )}
                      </div>
                      {isPriorityEvent && !past && (
                        <span className="font-mono text-[9px] tracking-wider px-1.5 py-0.5 border border-accent/30 text-accent bg-accent/10 shrink-0">
                          PRI
                        </span>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// --- Main page ---

export function SchedulePage() {
  const [view, setView] = useState<ViewMode>('today')

  return (
    <div>
      <h3 className="section-title">SCHEDULE</h3>

      <ViewToggle active={view} onChange={setView} />

      {view === 'today' ? <TodayView /> : <WeekView />}
    </div>
  )
}
