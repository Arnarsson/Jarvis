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
  // getDay(): 0=Sun, 1=Mon ... 6=Sat  -> shift so Monday=0
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

const DAY_LABELS = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'] as const

// --- Data hooks ---

function useTodayEvents() {
  return useQuery<CalendarEvent[]>({
    queryKey: ['schedule', 'today'],
    queryFn: async () => {
      try {
        const data = await apiGet<UpcomingEventsResponse>(
          '/api/calendar/events/upcoming?limit=50',
        )
        const now = new Date()
        return (data.events ?? []).filter((e) => {
          const start = new Date(e.start)
          return isSameDay(start, now)
        })
      } catch {
        return []
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

function EventCard({ event }: { event: CalendarEvent }) {
  const priority = getPriority(event.summary)
  const attendeeLabel = getAttendeeLabel(event.attendees)
  const isPriority = priority === 'priority'

  return (
    <div
      className={`flex items-start gap-4 py-4 border-b border-border/50 last:border-b-0`}
    >
      {/* Time column */}
      <div className="shrink-0 w-14 pt-0.5">
        <span className="font-mono text-[13px] text-text-secondary tracking-wide">
          {formatTime(event.start)}
        </span>
      </div>

      {/* Event card with left border */}
      <div
        className={`flex-1 min-w-0 pl-4 border-l-2 ${
          isPriority ? 'border-accent' : 'border-border'
        }`}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <p className="text-[15px] text-text-primary font-medium">
              {event.summary}
            </p>
            <div className="flex flex-wrap items-center gap-x-3 mt-1">
              <span className="text-[12px] text-text-secondary font-mono tracking-wide">
                {formatTime(event.start)} &mdash; {formatTime(event.end)}
              </span>
              {event.location && (
                <span className="text-[12px] text-text-secondary truncate">
                  {event.location}
                </span>
              )}
              {attendeeLabel && (
                <span className="text-[12px] text-text-secondary font-mono tracking-wide">
                  {attendeeLabel}
                </span>
              )}
            </div>
          </div>
          <span
            className={`shrink-0 font-mono text-[10px] tracking-wider px-2.5 py-1 border ${
              isPriority
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
      <p className="text-sm text-text-secondary py-6">
        No events scheduled for today
      </p>
    )
  }

  const sorted = [...events].sort(
    (a, b) => new Date(a.start).getTime() - new Date(b.start).getTime(),
  )

  return (
    <div>
      {sorted.map((event) => (
        <EventCard key={event.id} event={event} />
      ))}
    </div>
  )
}

function WeekView() {
  const { data: storedEvents, isLoading, isError } = useWeekEvents()
  const [selectedDayIndex, setSelectedDayIndex] = useState<number | null>(null)

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

  // Group events by day index (0=Mon, 6=Sun)
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
    }

    return grouped
  }, [storedEvents, days])

  // Find today's index in the week
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
    <div>
      {/* Desktop: 7-column grid */}
      <div className="hidden md:grid grid-cols-7 gap-px bg-border/30 border border-border rounded overflow-hidden">
        {/* Header row */}
        {DAY_LABELS.map((label, i) => (
          <div
            key={label}
            className={`px-2 py-2 text-center font-mono text-[11px] tracking-wider uppercase bg-surface ${
              i === todayIndex
                ? 'text-accent border-b-2 border-accent'
                : 'text-text-secondary border-b border-border'
            }`}
          >
            {label}
            <span className="block text-[10px] text-text-muted mt-0.5">
              {days[i].getDate()}
            </span>
          </div>
        ))}

        {/* Day cells */}
        {days.map((_day, i) => {
          const dayEvents = eventsByDay.get(i) || []
          const isToday = i === todayIndex
          const isSelected = selectedDayIndex === i

          return (
            <button
              key={i}
              onClick={() => setSelectedDayIndex(isSelected ? null : i)}
              className={`min-h-[100px] px-2 py-2 text-left bg-surface transition-colors cursor-pointer ${
                isSelected
                  ? 'ring-1 ring-accent/50 bg-accent/5'
                  : isToday
                    ? 'bg-accent/5'
                    : 'hover:bg-surface-alt'
              }`}
            >
              {dayEvents.length > 0 ? (
                <div>
                  <span className="font-mono text-[11px] text-text-secondary tracking-wider">
                    {dayEvents.length} EVENT{dayEvents.length !== 1 ? 'S' : ''}
                  </span>
                  <div className="mt-2 space-y-1">
                    {dayEvents.slice(0, 2).map((ev) => (
                      <p
                        key={ev.id}
                        className="text-[12px] text-text-primary truncate leading-tight"
                      >
                        {ev.summary}
                      </p>
                    ))}
                    {dayEvents.length > 2 && (
                      <p className="text-[11px] text-text-muted font-mono">
                        +{dayEvents.length - 2} more
                      </p>
                    )}
                  </div>
                </div>
              ) : (
                <span className="text-[11px] text-text-muted font-mono">
                  --
                </span>
              )}
            </button>
          )
        })}
      </div>

      {/* Mobile: stacked list */}
      <div className="md:hidden space-y-3">
        {days.map((_day, i) => {
          const dayEvents = eventsByDay.get(i) || []
          const isToday = i === todayIndex
          const isSelected = selectedDayIndex === i

          return (
            <button
              key={i}
              onClick={() => setSelectedDayIndex(isSelected ? null : i)}
              className={`w-full text-left px-4 py-3 border transition-colors ${
                isSelected
                  ? 'border-accent/50 bg-accent/5'
                  : isToday
                    ? 'border-accent/30 bg-surface'
                    : 'border-border bg-surface'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span
                  className={`font-mono text-[12px] tracking-wider uppercase ${
                    isToday ? 'text-accent' : 'text-text-secondary'
                  }`}
                >
                  {DAY_LABELS[i]} {days[i].getDate()}
                </span>
                <span className="font-mono text-[11px] text-text-muted tracking-wider">
                  {dayEvents.length} EVENT{dayEvents.length !== 1 ? 'S' : ''}
                </span>
              </div>
              {dayEvents.length > 0 && (
                <div className="space-y-1 mt-1">
                  {dayEvents.slice(0, 2).map((ev) => (
                    <p
                      key={ev.id}
                      className="text-[13px] text-text-primary truncate"
                    >
                      {ev.summary}
                    </p>
                  ))}
                  {dayEvents.length > 2 && (
                    <p className="text-[11px] text-text-muted font-mono">
                      +{dayEvents.length - 2} more
                    </p>
                  )}
                </div>
              )}
            </button>
          )
        })}
      </div>
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
