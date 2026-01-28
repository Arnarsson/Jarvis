import { useQuery } from '@tanstack/react-query'
import { fetchUpcomingMeetings } from '../api/calendar.ts'
import { fetchWorkflowSuggestions } from '../api/health.ts'
import { apiGet } from '../api/client.ts'

export interface DashboardStats {
  meetingsToday: number
  inboundCount: number
  pendingActions: number
  velocity: number
}

interface CategoryCount {
  name: string
  total: number
  unread: number
}

interface CategoryCountsResponse {
  categories: CategoryCount[]
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

async function fetchEmailUnreadCount(): Promise<number> {
  try {
    const data = await apiGet<CategoryCountsResponse>('/api/email/categories/counts')
    return (data.categories ?? []).reduce((sum, c) => sum + c.unread, 0)
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
    queryFn: fetchEmailUnreadCount,
    staleTime: 60_000,
  })

  const isLoading = meetingsQuery.isLoading || workflowQuery.isLoading

  const meetingsData = Array.isArray(meetingsQuery.data) ? meetingsQuery.data : []
  const todaysMeetings = meetingsData.filter((e) => isToday(e.start))
  const suggestions = Array.isArray(workflowQuery.data) ? workflowQuery.data : []
  const totalSuggestions = suggestions.length
  const approvedSuggestions = suggestions.filter(
    (s) => (s as unknown as Record<string, unknown>).status === 'approved' || (s as unknown as Record<string, unknown>).approved === true
  ).length
  const velocity = totalSuggestions > 0
    ? Math.round((approvedSuggestions / totalSuggestions) * 100)
    : 0

  const stats: DashboardStats = {
    meetingsToday: todaysMeetings.length,
    inboundCount: emailQuery.data ?? 0,
    pendingActions: suggestions.length,
    velocity,
  }

  return {
    stats,
    isLoading,
    isError: meetingsQuery.isError && workflowQuery.isError,
  }
}
