import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useAgenda } from '../../hooks/useAgenda.ts'
import { apiGet } from '../../api/client.ts'
import { LoadingSkeleton } from '../ui/LoadingSkeleton.tsx'
import type { CalendarEvent } from '../../api/calendar.ts'

/* ───────────────── Helpers ───────────────── */

function formatTime(isoString: string): string {
  const date = new Date(isoString)
  return date.toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
  })
}

function getAttendeeLabel(event: CalendarEvent): string {
  if (event.attendees && event.attendees.length > 0) {
    const first = event.attendees[0].split('@')[0].toUpperCase()
    const extra = event.attendees.length > 1 ? ` +${event.attendees.length - 1}` : ''
    return `${first}${extra}`
  }
  return event.location || ''
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

function isPastEvent(endTime: string): boolean {
  return new Date(endTime).getTime() < Date.now()
}

function isCurrentEvent(start: string, end: string): boolean {
  const now = Date.now()
  return new Date(start).getTime() <= now && new Date(end).getTime() > now
}

/** Deduplicate recurring events */
function deduplicateRecurring(events: CalendarEvent[]): CalendarEvent[] {
  const now = Date.now()
  const grouped = new Map<string, CalendarEvent[]>()

  for (const event of events) {
    const key = event.summary.toLowerCase().trim()
    if (!grouped.has(key)) grouped.set(key, [])
    grouped.get(key)!.push(event)
  }

  const result: CalendarEvent[] = []
  for (const [, group] of grouped) {
    if (group.length <= 1) {
      result.push(...group)
      continue
    }

    group.sort((a, b) => new Date(a.start).getTime() - new Date(b.start).getTime())
    const upcoming = group.filter((e) => new Date(e.end).getTime() >= now)
    if (upcoming.length > 0) {
      result.push(upcoming[0])
    } else {
      result.push(group[group.length - 1])
    }
  }

  result.sort((a, b) => new Date(a.start).getTime() - new Date(b.start).getTime())
  return result
}

/* ───────────────── NOW Indicator ───────────────── */

function NowIndicator() {
  const now = new Date()
  const timeStr = now.toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
  })
  return (
    <div className="flex items-center gap-3 py-1 my-1">
      <span className="font-mono text-[10px] text-accent tracking-wider font-bold shrink-0">
        {timeStr}
      </span>
      <div className="flex-1 flex items-center gap-1">
        <div className="w-2 h-2 rounded-full bg-accent shadow-[0_0_6px_theme(colors.accent)]" />
        <div className="flex-1 h-px bg-accent/50" />
      </div>
      <span className="font-mono text-[9px] text-accent tracking-wider shrink-0">NOW</span>
    </div>
  )
}

/* ───────────────── Meeting Brief ───────────────── */

interface MeetingBrief {
  event_id: string
  summary: string
  brief: string
  attendees?: string[]
  key_points?: string[]
}

function MeetingBriefPanel({ eventId }: { eventId: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['meeting', 'brief', eventId],
    queryFn: async () => {
      return await apiGet<MeetingBrief>(`/api/meetings/brief/${eventId}`)
    },
    staleTime: 5 * 60_000,
    retry: 1,
  })

  if (isLoading) {
    return (
      <div className="mt-2 ml-0 pl-4 border-l-2 border-border/40 py-2">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 border border-accent/50 border-t-transparent rounded-full animate-spin" />
          <span className="font-mono text-[11px] text-text-muted">Loading brief…</span>
        </div>
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div className="mt-2 ml-0 pl-4 border-l-2 border-border/30 py-2">
        <p className="font-mono text-[11px] text-text-muted">No brief available</p>
      </div>
    )
  }

  return (
    <div className="mt-2 ml-0 pl-4 border-l-2 border-accent/30 py-2 space-y-1.5">
      {data.brief && (
        <p className="text-[12px] text-text-secondary leading-relaxed">{data.brief}</p>
      )}
      {data.key_points && data.key_points.length > 0 && (
        <ul className="space-y-0.5">
          {data.key_points.map((point, i) => (
            <li key={i} className="text-[11px] text-text-muted font-mono flex items-start gap-1.5">
              <span className="text-accent shrink-0 mt-0.5">›</span>
              <span>{point}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/* ───────────────── Agenda Event Row ───────────────── */

function AgendaEventRow({ event, showNowBefore }: { event: CalendarEvent; showNowBefore: boolean }) {
  const [expanded, setExpanded] = useState(false)
  const priority = getPriority(event.summary)
  const attendee = getAttendeeLabel(event)
  const past = isPastEvent(event.end)
  const current = isCurrentEvent(event.start, event.end)

  const handleJoinMeeting = (e: React.MouseEvent) => {
    e.stopPropagation()
    // TODO: Implement join meeting logic (check for meet link, zoom, etc.)
    console.log('Join meeting:', event.id, event.summary)
    if (event.location && event.location.includes('http')) {
      window.open(event.location, '_blank')
    }
  }

  const handlePrepBrief = (e: React.MouseEvent) => {
    e.stopPropagation()
    setExpanded(!expanded)
  }

  return (
    <div>
      {showNowBefore && <NowIndicator />}
      <div
        className={`py-4 border-b border-border/50 last:border-b-0 transition-opacity ${
          past ? 'opacity-35' : ''
        } ${current ? 'bg-accent/5 -mx-2 px-2 rounded' : ''}`}
      >
        <div className="flex items-start justify-between gap-4">
          <div 
            className="flex-1 min-w-0 cursor-pointer"
            onClick={() => !past && setExpanded(!expanded)}
          >
            <p className={`text-[15px] font-medium ${
              past ? 'text-text-muted line-through decoration-border/50' : 'text-text-primary'
            }`}>
              {event.summary}
              {current && (
                <span className="ml-2 inline-block w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
              )}
              {!past && (
                <span className="ml-2 text-[10px] text-text-muted font-mono">
                  {expanded ? '▾' : '▸'}
                </span>
              )}
            </p>
            <p className={`text-[12px] mt-1 font-mono tracking-wide ${
              past ? 'text-text-muted' : 'text-text-secondary'
            }`}>
              {formatTime(event.start)} &mdash; {formatTime(event.end)}
              {attendee && (
                <span> / {attendee}</span>
              )}
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span
              className={`font-mono text-[10px] tracking-wider px-2.5 py-1 border ${
                past
                  ? 'border-border/30 text-text-muted bg-border/10'
                  : priority === 'priority'
                    ? 'border-accent/40 text-accent bg-accent/10'
                    : 'border-border text-text-secondary bg-border/30'
              }`}
            >
              {past ? 'DONE' : priority === 'priority' ? 'PRIORITY' : 'ROUTINE'}
            </span>
          </div>
        </div>

        {/* Action Buttons (only for upcoming/current meetings) */}
        {!past && (
          <div className="flex gap-2 mt-3">
            {(current || new Date(event.start).getTime() - Date.now() < 15 * 60 * 1000) && (
              <button 
                onClick={handleJoinMeeting}
                className="px-3 py-1.5 text-xs bg-accent text-black rounded hover:bg-accent/80 transition-colors font-mono"
              >
                🔗 Join
              </button>
            )}
            <button 
              onClick={handlePrepBrief}
              className="px-3 py-1.5 text-xs border border-border rounded hover:bg-surface-hover transition-colors font-mono text-text-primary"
            >
              📋 {expanded ? 'Hide' : 'Prep'}
            </button>
            <button 
              onClick={(e) => {
                e.stopPropagation()
                // TODO: Implement skip/cancel action
                console.log('Skip meeting:', event.id)
              }}
              className="px-3 py-1.5 text-xs border border-border rounded hover:bg-surface-hover transition-colors font-mono text-text-muted"
            >
              ⏭️ Skip
            </button>
          </div>
        )}
      </div>
      {expanded && !past && (
        <MeetingBriefPanel eventId={event.id} />
      )}
    </div>
  )
}

/* ───────────────── Main Component ───────────────── */

export function AgendaList() {
  const { data: meetings, isLoading, isError } = useAgenda()

  const processedMeetings = useMemo(() => {
    if (!meetings) return []
    return deduplicateRecurring(meetings)
  }, [meetings])

  // Determine where to insert the NOW indicator
  const [baseTime] = useState(() => Date.now())
  const nowInsertIndex = useMemo(() => {
    if (!processedMeetings.length) return -1
    const now = baseTime
    for (let i = 0; i < processedMeetings.length; i++) {
      const eventStart = new Date(processedMeetings[i].start).getTime()
      if (eventStart > now) return i
    }
    return processedMeetings.length
  }, [processedMeetings, baseTime])

  // Check if all events are past
  const allEventsPast = useMemo(() => {
    if (!processedMeetings.length) return false
    return processedMeetings.every((e) => isPastEvent(e.end))
  }, [processedMeetings])

  return (
    <div>
      <h3 className="section-title">AGENDA</h3>

      {isLoading && <LoadingSkeleton lines={4} />}

      {isError && (
        <p className="text-sm text-text-secondary">
          Unable to load calendar events
        </p>
      )}

      {!isLoading && !isError && processedMeetings.length === 0 && (
        <p className="text-sm text-text-secondary py-4">
          No meetings scheduled today
        </p>
      )}

      {!isLoading && processedMeetings.length > 0 && (
        <div className="space-y-0">
          {processedMeetings.map((event, i) => (
            <AgendaEventRow
              key={event.id}
              event={event}
              showNowBefore={nowInsertIndex === i}
            />
          ))}
          {/* NOW indicator at the end if all events are past */}
          {nowInsertIndex === processedMeetings.length && <NowIndicator />}

          {/* No more events message */}
          {allEventsPast && (
            <div className="flex items-center gap-3 py-4 mt-2">
              <span className="text-lg">✓</span>
              <p className="font-mono text-[12px] text-text-muted tracking-wide">
                No more events today
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
