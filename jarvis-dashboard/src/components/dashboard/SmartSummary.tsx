import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../../api/client.ts'

/* ───────────────── Types ───────────────── */

interface CategoryCount {
  name: string
  total: number
  unread: number
}

interface CategoryCountsResponse {
  categories: CategoryCount[]
}

interface CalendarEvent {
  id: string
  summary: string
  start: string
  end: string
}

interface CalendarResponse {
  events: CalendarEvent[]
  count: number
}

/* ───────────────── Time helpers ───────────────── */

type TimeOfDay = 'morning' | 'afternoon' | 'evening'

function getTimeOfDay(): TimeOfDay {
  const hour = new Date().getHours()
  if (hour < 12) return 'morning'
  if (hour < 18) return 'afternoon'
  return 'evening'
}

function getGreeting(): string {
  const tod = getTimeOfDay()
  switch (tod) {
    case 'morning': return 'Good morning, Sven.'
    case 'afternoon': return 'Good afternoon, Sven.'
    case 'evening': return 'Good evening, Sven.'
  }
}

function formatEventTime(isoString: string): string {
  return new Date(isoString).toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatTimeUntil(isoString: string): string {
  const now = Date.now()
  const then = new Date(isoString).getTime()
  const diffMs = then - now

  if (diffMs < 0) return 'now'
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 60) return `${diffMin}m`
  const diffHr = Math.floor(diffMin / 60)
  const remainMin = diffMin % 60
  if (remainMin === 0) return `${diffHr}h`
  return `${diffHr}h ${remainMin}m`
}

/* ───────────────── Component ───────────────── */

export function SmartSummary() {
  // Email priority count
  const { data: emailData } = useQuery({
    queryKey: ['email', 'categories', 'counts'],
    queryFn: async () => {
      try {
        return await apiGet<CategoryCountsResponse>('/api/email/categories/counts')
      } catch {
        return null
      }
    },
    staleTime: 60_000,
  })

  // Next meetings
  const { data: calendarData } = useQuery({
    queryKey: ['calendar', 'upcoming', 'raw'],
    queryFn: async () => {
      try {
        return await apiGet<CalendarResponse>('/api/calendar/events/upcoming')
      } catch {
        return null
      }
    },
    staleTime: 60_000,
  })

  // Build time-of-day aware summary
  const timeOfDay = getTimeOfDay()
  const greeting = getGreeting()
  const [now] = useState(() => Date.now())

  // Parse calendar data
  const todayEvents = (calendarData?.events ?? []).filter((e) => {
    const d = new Date(e.start)
    const today = new Date()
    return d.getDate() === today.getDate() && d.getMonth() === today.getMonth() && d.getFullYear() === today.getFullYear()
  })

  const upcomingEvents = todayEvents
    .filter((e) => new Date(e.start).getTime() > now)
    .sort((a, b) => new Date(a.start).getTime() - new Date(b.start).getTime())

  const pastEvents = todayEvents.filter((e) => new Date(e.end).getTime() <= now)

  // Parse email data
  const priority = emailData?.categories?.find((c) => c.name === 'priority')
  const priorityCount = priority?.unread ?? 0
  const totalUnread = emailData?.categories?.reduce((s, c) => s + c.unread, 0) ?? 0

  // Build summary lines based on time of day
  let mainLine = greeting
  let detailLine = ''
  let emailLine = ''

  switch (timeOfDay) {
    case 'morning': {
      const parts: string[] = []
      if (todayEvents.length > 0) {
        parts.push(`${todayEvents.length} meeting${todayEvents.length !== 1 ? 's' : ''} today`)
      }
      if (priorityCount > 0) {
        parts.push(`${priorityCount} priority email${priorityCount !== 1 ? 's' : ''}`)
      } else if (totalUnread > 0) {
        parts.push(`${totalUnread} unread email${totalUnread !== 1 ? 's' : ''}`)
      }
      mainLine = `${greeting} ${parts.join(', ')}.`

      if (upcomingEvents.length > 0) {
        detailLine = `First meeting at ${formatEventTime(upcomingEvents[0].start)}: ${upcomingEvents[0].summary}`
      }
      break
    }

    case 'afternoon': {
      if (upcomingEvents.length > 0) {
        mainLine = `${greeting} ${upcomingEvents.length} meeting${upcomingEvents.length !== 1 ? 's' : ''} left today.`
        detailLine = `Next in ${formatTimeUntil(upcomingEvents[0].start)}: ${upcomingEvents[0].summary}`
      } else {
        mainLine = `${greeting} No more meetings today.`
        if (pastEvents.length > 0) {
          detailLine = `${pastEvents.length} meeting${pastEvents.length !== 1 ? 's' : ''} completed`
        }
      }
      if (priorityCount > 0) {
        emailLine = `${priorityCount} priority email${priorityCount !== 1 ? 's' : ''} need your reply`
      } else if (totalUnread > 0) {
        emailLine = `${totalUnread} new email${totalUnread !== 1 ? 's' : ''} since this morning`
      }
      break
    }

    case 'evening': {
      mainLine = `${greeting} Day winding down.`
      if (pastEvents.length > 0) {
        detailLine = `${pastEvents.length} meeting${pastEvents.length !== 1 ? 's' : ''} completed today`
      }
      // TODO: show tomorrow's events when API supports it
      if (priorityCount > 0) {
        emailLine = `${priorityCount} priority email${priorityCount !== 1 ? 's' : ''} remaining`
      }
      break
    }
  }

  return (
    <div className="mb-10 border border-border/50 rounded-lg bg-surface/30 px-5 py-4">
      <p className="text-[15px] text-text-primary font-medium leading-relaxed">
        {mainLine}
      </p>
      {detailLine && (
        <p className="text-[13px] text-text-secondary mt-1.5 font-mono">
          {detailLine}
        </p>
      )}
      {emailLine && (
        <p className="text-[12px] text-text-muted mt-1 font-mono">
          📧 {emailLine}
        </p>
      )}
    </div>
  )
}
