import { useAgenda } from '../../hooks/useAgenda.ts'
import { LoadingSkeleton } from '../ui/LoadingSkeleton.tsx'
import type { CalendarEvent } from '../../api/calendar.ts'

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

export function AgendaList() {
  const { data: meetings, isLoading, isError } = useAgenda()

  return (
    <div>
      <h3 className="section-title">AGENDA</h3>

      {isLoading && <LoadingSkeleton lines={4} />}

      {isError && (
        <p className="text-sm text-text-secondary">
          Unable to load calendar events
        </p>
      )}

      {!isLoading && !isError && meetings?.length === 0 && (
        <p className="text-sm text-text-secondary py-4">
          No meetings scheduled today
        </p>
      )}

      {!isLoading && meetings && meetings.length > 0 && (
        <div className="space-y-0">
          {meetings.map((event) => {
            const priority = getPriority(event.summary)
            const attendee = getAttendeeLabel(event)
            return (
              <div
                key={event.id}
                className="flex items-center justify-between py-4 border-b border-border/50 last:border-b-0"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-[15px] text-text-primary font-medium">
                    {event.summary}
                  </p>
                  <p className="text-[12px] text-text-secondary mt-1 font-mono tracking-wide">
                    {formatTime(event.start)} &mdash; {formatTime(event.end)}
                    {attendee && (
                      <span> / {attendee}</span>
                    )}
                  </p>
                </div>
                <span
                  className={`ml-4 shrink-0 font-mono text-[10px] tracking-wider px-2.5 py-1 border ${
                    priority === 'priority'
                      ? 'border-accent/40 text-accent bg-accent/10'
                      : 'border-border text-text-secondary bg-border/30'
                  }`}
                >
                  {priority === 'priority' ? 'PRIORITY' : 'ROUTINE'}
                </span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
