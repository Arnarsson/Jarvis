import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../../api/client.ts'
import { StatCard } from '../ui/StatCard.tsx'

interface DashboardStats {
  conversations_today?: number
  tasks_completed_today?: number
  active_projects?: number
  total_captures?: number
  meetings_today?: number
  unread_emails?: number
}

function padValue(n: number): string {
  return n.toString().padStart(2, '0')
}

async function fetchDashboardStats(): Promise<DashboardStats> {
  try {
    // Try to fetch from a unified stats endpoint
    const data = await apiGet<DashboardStats>('/api/v2/stats/dashboard')
    return data
  } catch {
    // Fallback: fetch from individual endpoints
    const [conversations, tasks, emails] = await Promise.allSettled([
      apiGet<{ count: number }>('/api/v2/conversations/today').then(r => r.count).catch(() => 0),
      apiGet<{ count: number }>('/api/v2/tasks/completed/today').then(r => r.count).catch(() => 0),
      apiGet<{ unread: number }>('/api/email/categories/counts')
        .then((r: any) => r.categories?.reduce((sum: number, c: any) => sum + c.unread, 0) || 0)
        .catch(() => 0),
    ])

    return {
      conversations_today: conversations.status === 'fulfilled' ? conversations.value : 0,
      tasks_completed_today: tasks.status === 'fulfilled' ? tasks.value : 0,
      unread_emails: emails.status === 'fulfilled' ? emails.value : 0,
      meetings_today: 0,
      active_projects: 0,
      total_captures: 0,
    }
  }
}

export function StatsGrid() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ['dashboard', 'stats'],
    queryFn: fetchDashboardStats,
    staleTime: 60_000,
    retry: 1,
  })

  if (isLoading) {
    return (
      <div className="mb-8 grid grid-cols-2 lg:grid-cols-4 gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="border border-border/30 rounded bg-surface/20 p-4">
            <div className="h-3 w-16 bg-border/50 rounded mb-3 animate-pulse" />
            <div className="h-9 w-12 bg-border/50 rounded animate-pulse" />
          </div>
        ))}
      </div>
    )
  }

  const {
    conversations_today = 0,
    tasks_completed_today = 0,
    unread_emails = 0,
    meetings_today = 0,
  } = stats || {}

  return (
    <div className="mb-8 grid grid-cols-2 lg:grid-cols-4 gap-3">
      <StatCard
        label="MEETINGS"
        value={padValue(meetings_today)}
        to="/schedule"
      />
      <StatCard
        label="CONVERSATIONS"
        value={padValue(conversations_today)}
        to="/comms"
      />
      <StatCard
        label="TASKS DONE"
        value={padValue(tasks_completed_today)}
        accent={tasks_completed_today > 0}
        to="/tasks"
      />
      <StatCard
        label="INBOUND"
        value={padValue(unread_emails)}
        accent={unread_emails > 0}
        to="/comms"
      />
    </div>
  )
}
