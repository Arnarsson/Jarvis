import { useQuery } from '@tanstack/react-query'
import { fetchUpcomingMeetings } from '../api/calendar.ts'
import { fetchWorkflowSuggestions } from '../api/health.ts'

export interface DashboardStats {
  meetingsToday: number
  inboundCount: number
  pendingActions: number
  velocity: number
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

  const isLoading = meetingsQuery.isLoading || workflowQuery.isLoading

  const stats: DashboardStats = {
    meetingsToday: meetingsQuery.data?.length ?? 0,
    inboundCount: 45,
    pendingActions: workflowQuery.data?.length ?? 0,
    velocity: 92,
  }

  return {
    stats,
    isLoading,
    isError: meetingsQuery.isError && workflowQuery.isError,
  }
}
