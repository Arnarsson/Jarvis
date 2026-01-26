import { useQuery } from '@tanstack/react-query'
import { fetchUpcomingMeetings } from '../api/calendar.ts'
import { fetchWorkflowSuggestions, fetchEmailAuthStatus } from '../api/health.ts'
import { apiGet } from '../api/client.ts'

// Removed unused fetchSearchHealth - velocity now derived from workflow suggestions

export interface DashboardStats {
  meetingsToday: number
  inboundCount: number
  pendingActions: number
  velocity: number
}

interface EmailMessage {
  id: string
  is_read: boolean
  is_unread?: boolean
}

interface EmailListResponse {
  messages: EmailMessage[]
  count: number
}

function isToday(isoString: string): boolean {
  const eventDate = new Date(isoString)
  const now = new Date()
  return (
    eventDate.getFullYear() === now.getFullYear() &&
    eventDate.getMonth() === now.getMonth() &&
    eventDate.getDate() === now.getDate()
  )
}

async function fetchEmailCount(): Promise<number> {
  try {
    const auth = await fetchEmailAuthStatus()
    if (!auth.authenticated) return 0
    const data = await apiGet<EmailListResponse>('/api/email/messages')
    return data.messages.filter((m) => m.is_read === false).length
  } catch {
    return 0
  }
}

export function useStats() {
  const meetingsQuery = useQuery({
    queryKey: ['calendar', 'upcoming'],
    queryFn: fetchUpcomingMeetings,
  })

  const workflowQuery = useQuery({
    queryKey: ['workflow', 'suggestions'],
    queryFn: fetchWorkflowSuggestions,
  })

  const emailQuery = useQuery({
    queryKey: ['email', 'unread-count'],
    queryFn: fetchEmailCount,
    staleTime: 60_000,
  })

  const isLoading = meetingsQuery.isLoading || workflowQuery.isLoading

  const todaysMeetings = meetingsQuery.data?.filter((e) => isToday(e.start)) ?? []
  const suggestions = workflowQuery.data ?? []
  const totalSuggestions = suggestions.length
  const approvedSuggestions = suggestions.filter(
    (s) => (s as Record<string, unknown>).status === 'approved' || (s as Record<string, unknown>).approved === true
  ).length
  const velocity = totalSuggestions > 0
    ? Math.round((approvedSuggestions / totalSuggestions) * 100)
    : 0

  const stats: DashboardStats = {
    meetingsToday: todaysMeetings.length,
    inboundCount: emailQuery.data ?? 0,
    pendingActions: workflowQuery.data?.length ?? 0,
    velocity,
  }

  return {
    stats,
    isLoading,
    isError: meetingsQuery.isError && workflowQuery.isError,
  }
}
