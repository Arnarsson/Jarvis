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

interface WorkflowExecution {
  id: string
  status: string
}

interface ExecutionsResponse {
  executions: WorkflowExecution[]
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

async function fetchWorkflowExecutions(): Promise<WorkflowExecution[]> {
  try {
    const data = await apiGet<ExecutionsResponse>('/api/workflow/executions')
    return data.executions ?? []
  } catch {
    return []
  }
}

export function useStats() {
  const meetingsQuery = useQuery({
    queryKey: ['calendar', 'upcoming'],
    queryFn: fetchUpcomingMeetings,
    retry: 1,
    staleTime: 60_000,
  })

  const workflowQuery = useQuery({
    queryKey: ['workflow', 'suggestions'],
    queryFn: fetchWorkflowSuggestions,
    retry: 1,
    staleTime: 60_000,
  })

  const emailQuery = useQuery({
    queryKey: ['email', 'unread-count'],
    queryFn: fetchEmailUnreadCount,
    retry: 1,
    staleTime: 60_000,
  })

  const executionsQuery = useQuery({
    queryKey: ['workflow', 'executions'],
    queryFn: fetchWorkflowExecutions,
    retry: 1,
    staleTime: 60_000,
  })

  const isLoading = meetingsQuery.isPending || workflowQuery.isPending || 
                    emailQuery.isPending || executionsQuery.isPending

  const meetingsData = Array.isArray(meetingsQuery.data) ? meetingsQuery.data : []
  const todaysMeetings = meetingsData.filter((e) => isToday(e.start))
  const suggestions = Array.isArray(workflowQuery.data) ? workflowQuery.data : []

  // Velocity: completed executions / total executions
  const executions = Array.isArray(executionsQuery.data) ? executionsQuery.data : []
  const totalExecs = executions.length
  const completedExecs = executions.filter((e) => e.status === 'completed').length
  const velocity = totalExecs > 0 ? Math.round((completedExecs / totalExecs) * 100) : 0

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
