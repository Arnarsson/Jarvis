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

/* ───────────────── Smart Card ───────────────── */

interface SmartCardProps {
  emoji: string
  text: string
  subtext?: string
  accent?: boolean
}

function SmartCard({ emoji, text, subtext, accent }: SmartCardProps) {
  return (
    <div className={`flex items-start gap-3 py-3.5 border-b border-border/30 last:border-b-0 ${accent ? '' : ''}`}>
      <span className="text-lg shrink-0 mt-0.5">{emoji}</span>
      <div className="min-w-0">
        <p className={`text-[14px] leading-snug ${accent ? 'text-accent font-medium' : 'text-text-primary'}`}>
          {text}
        </p>
        {subtext && (
          <p className="text-[11px] text-text-muted mt-0.5">{subtext}</p>
        )}
      </div>
    </div>
  )
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

  // Next meetings — use distinct key to avoid cache collision with useAgenda
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

  // Build smart cards
  const cards: SmartCardProps[] = []

  // Email insight
  if (emailData?.categories) {
    const priority = emailData.categories.find((c) => c.name === 'priority')
    const totalUnread = emailData.categories.reduce((s, c) => s + c.unread, 0)

    if (priority && priority.unread > 0) {
      cards.push({
        emoji: '📧',
        text: `${priority.unread} priority email${priority.unread !== 1 ? 's' : ''} need your reply`,
        subtext: totalUnread > priority.unread ? `${totalUnread} total unread` : undefined,
        accent: priority.unread >= 3,
      })
    } else if (totalUnread > 0) {
      cards.push({
        emoji: '📧',
        text: `${totalUnread} unread email${totalUnread !== 1 ? 's' : ''}`,
      })
    } else {
      cards.push({
        emoji: '📧',
        text: 'Inbox clear — no unread emails',
        subtext: 'Nice work',
      })
    }
  }

  // Calendar insight — next meeting
  if (calendarData?.events?.length) {
    const now = Date.now()
    const upcoming = calendarData.events
      .filter((e) => new Date(e.start).getTime() > now)
      .sort((a, b) => new Date(a.start).getTime() - new Date(b.start).getTime())

    if (upcoming.length > 0) {
      const next = upcoming[0]
      const timeStr = formatTimeUntil(next.start)
      cards.push({
        emoji: '📅',
        text: `Next meeting in ${timeStr}: ${next.summary}`,
        subtext: upcoming.length > 1
          ? `${upcoming.length - 1} more today`
          : undefined,
      })
    } else {
      // All meetings are in the past or happening now
      const todayEvents = calendarData.events.filter((e) => {
        const d = new Date(e.start)
        const today = new Date()
        return d.getDate() === today.getDate() && d.getMonth() === today.getMonth()
      })
      if (todayEvents.length > 0) {
        cards.push({
          emoji: '📅',
          text: `${todayEvents.length} meeting${todayEvents.length !== 1 ? 's' : ''} done today`,
          subtext: 'No more scheduled',
        })
      } else {
        cards.push({
          emoji: '📅',
          text: 'No meetings today',
          subtext: 'Clear calendar',
        })
      }
    }
  }

  if (cards.length === 0) return null

  return (
    <div className="mb-10 border border-border/50 rounded-lg bg-surface/30 px-5 py-1">
      {cards.map((card, i) => (
        <SmartCard key={i} {...card} />
      ))}
    </div>
  )
}
