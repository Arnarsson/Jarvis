import { useQuery } from '@tanstack/react-query'
import { fetchMorningBriefing } from '../../api/briefing.ts'
import { useAgenda } from '../../hooks/useAgenda.ts'
import { LoadingSkeleton } from '../ui/LoadingSkeleton.tsx'
import { MeetingBriefButton } from './MeetingBrief.tsx'
import './MeetingBrief.css'

/* ───────────────── Helpers ───────────────── */

function formatTime(iso: string): string {
  const date = new Date(iso)
  return date.toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
  })
}

function isUpcoming(start: string): boolean {
  return new Date(start).getTime() > Date.now()
}

function isCurrent(start: string, end: string): boolean {
  const now = Date.now()
  return new Date(start).getTime() <= now && new Date(end).getTime() > now
}

function minutesUntil(iso: string): number {
  return Math.round((new Date(iso).getTime() - Date.now()) / 60000)
}

function getAttendeeNames(attendees: string[]): string {
  if (!attendees.length) return ''
  return attendees
    .map((a) => a.split('@')[0])
    .filter((name) => !name.includes('sven'))
    .slice(0, 3)
    .join(', ')
}

/* ───────────────── Component ───────────────── */

export function WhatsComingUp() {
  const { data: meetings, isLoading: agendaLoading } = useAgenda()
  const { data: briefing, isLoading: briefingLoading } = useQuery({
    queryKey: ['briefing', 'morning'],
    queryFn: fetchMorningBriefing,
    staleTime: 5 * 60_000,
    retry: 1,
  })

  const isLoading = agendaLoading || briefingLoading

  if (isLoading) {
    return (
      <div>
        <h2 className="section-title">📅 WHAT'S COMING UP?</h2>
        <LoadingSkeleton lines={4} />
      </div>
    )
  }

  // Get calendar events from briefing (includes today's full schedule)
  const calendarEvents = briefing?.sections.calendar ?? []
  // Also get events from agenda hook
  const agendaEvents = meetings ?? []

  // Merge and deduplicate by summary + start time
  const allEvents = [...calendarEvents.map((e) => ({
    id: e.event_id || e.summary, // fallback to summary if no event_id
    summary: e.summary,
    start: e.start_time,
    end: e.end_time,
    location: e.location ?? null,
    attendees: e.attendees,
    source: 'briefing' as const,
  })), ...agendaEvents.map((e) => ({
    id: e.id,
    summary: e.summary,
    start: e.start,
    end: e.end,
    location: e.location ?? null,
    attendees: e.attendees,
    source: 'agenda' as const,
  }))]

  // Deduplicate by matching summary + close start time
  const seen = new Set<string>()
  const dedupEvents = allEvents.filter((e) => {
    const key = `${e.summary.toLowerCase().trim()}-${new Date(e.start).toISOString().slice(0, 13)}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })

  // Sort by start time
  dedupEvents.sort((a, b) => new Date(a.start).getTime() - new Date(b.start).getTime())

  // Split into current/upcoming vs past
  const upcomingEvents = dedupEvents.filter(
    (e) => isUpcoming(e.start) || isCurrent(e.start, e.end)
  )
  const pastEvents = dedupEvents.filter(
    (e) => !isUpcoming(e.start) && !isCurrent(e.start, e.end)
  )

  const hasEvents = dedupEvents.length > 0

  if (!hasEvents) {
    return (
      <div>
        <h2 className="section-title">📅 WHAT'S COMING UP?</h2>
        <div className="border border-border/30 border-dashed rounded-lg p-6 text-center">
          <p className="text-2xl mb-2">🎉</p>
          <p className="font-mono text-xs text-text-muted">Clear calendar — deep work time</p>
        </div>
      </div>
    )
  }

  return (
    <div>
      <h2 className="section-title">📅 WHAT'S COMING UP?</h2>

      <div className="space-y-2">
        {/* Upcoming / Current events */}
        {upcomingEvents.map((event, i) => {
          const current = isCurrent(event.start, event.end)
          const mins = minutesUntil(event.start)
          const attendeeStr = getAttendeeNames(event.attendees)
          const imminent = mins > 0 && mins <= 15

          return (
            <div
              key={`upcoming-${i}`}
              className={`flex items-center gap-4 p-4 rounded-lg border transition-all ${
                current
                  ? 'border-accent/40 bg-accent/5'
                  : imminent
                    ? 'border-orange-500/30 bg-orange-500/5'
                    : 'border-border/30 bg-surface/30'
              }`}
            >
              {/* Time column */}
              <div className="shrink-0 w-20 text-right">
                <p className={`font-mono text-sm font-bold ${
                  current ? 'text-accent' : imminent ? 'text-orange-400' : 'text-text-primary'
                }`}>
                  {formatTime(event.start)}
                </p>
                <p className="font-mono text-[10px] text-text-muted">
                  {formatTime(event.end)}
                </p>
              </div>

              {/* Divider */}
              <div className={`w-0.5 self-stretch rounded-full ${
                current ? 'bg-accent' : imminent ? 'bg-orange-500' : 'bg-border/50'
              }`} />

              {/* Event details */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-medium text-text-primary truncate">
                    {event.summary}
                  </p>
                  {current && (
                    <span className="shrink-0 inline-flex items-center gap-1 font-mono text-[9px] tracking-wider text-accent bg-accent/10 px-2 py-0.5 rounded-full">
                      <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
                      NOW
                    </span>
                  )}
                  {imminent && !current && (
                    <span className="shrink-0 font-mono text-[9px] tracking-wider text-orange-400 bg-orange-500/10 px-2 py-0.5 rounded-full">
                      IN {mins}m
                    </span>
                  )}
                </div>
                {attendeeStr && (
                  <p className="text-[11px] text-text-muted mt-0.5 font-mono truncate">
                    with {attendeeStr}
                  </p>
                )}
                {event.location && (
                  <p className="text-[10px] text-text-muted mt-0.5">
                    📍 {event.location}
                  </p>
                )}
              </div>

              {/* Meeting Brief Button */}
              {imminent && (
                <div className="shrink-0">
                  <MeetingBriefButton 
                    eventId={event.id}
                    meetingTitle={event.summary}
                  />
                </div>
              )}

              {/* Countdown */}
              {!current && mins > 0 && (
                <div className="shrink-0 text-right">
                  <p className={`font-mono text-xs font-bold ${
                    imminent ? 'text-orange-400' : 'text-text-muted'
                  }`}>
                    {mins < 60 ? `${mins}m` : `${Math.floor(mins / 60)}h ${mins % 60}m`}
                  </p>
                  <p className="font-mono text-[9px] text-text-muted">until</p>
                </div>
              )}
            </div>
          )
        })}

        {/* Past events — collapsed */}
        {pastEvents.length > 0 && (
          <div className="pt-2">
            <p className="font-mono text-[10px] text-text-muted tracking-wider mb-2">
              ✓ {pastEvents.length} COMPLETED TODAY
            </p>
            <div className="space-y-1">
              {pastEvents.map((event, i) => (
                <div
                  key={`past-${i}`}
                  className="flex items-center gap-3 py-1.5 opacity-40"
                >
                  <span className="font-mono text-[11px] text-text-muted w-14 text-right shrink-0">
                    {formatTime(event.start)}
                  </span>
                  <span className="text-xs text-text-muted line-through truncate">
                    {event.summary}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* End of day message */}
        {upcomingEvents.length === 0 && pastEvents.length > 0 && (
          <div className="border border-green-500/20 rounded-lg bg-green-500/5 p-4 text-center mt-2">
            <p className="text-lg mb-1">✓</p>
            <p className="font-mono text-xs text-green-400">All meetings done for today</p>
          </div>
        )}
      </div>
    </div>
  )
}
