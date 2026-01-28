import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../../api/client.ts'
import { LoadingSkeleton } from '../ui/LoadingSkeleton.tsx'

interface EmailAuthStatus {
  authenticated: boolean
  email?: string
}

interface CategoryCount {
  name: string
  total: number
  unread: number
}

interface CategoryCountsResponse {
  categories: CategoryCount[]
}

async function fetchEmailAuth(): Promise<EmailAuthStatus> {
  try {
    return await apiGet<EmailAuthStatus>('/api/email/auth/status')
  } catch {
    return { authenticated: false }
  }
}

async function fetchCategoryCounts(): Promise<CategoryCountsResponse> {
  return apiGet<CategoryCountsResponse>('/api/email/categories/counts')
}

export function Communications() {
  const navigate = useNavigate()
  const { data: auth } = useQuery({
    queryKey: ['email', 'auth'],
    queryFn: fetchEmailAuth,
  })

  const { data: countsData, isLoading } = useQuery({
    queryKey: ['email', 'categories', 'counts'],
    queryFn: fetchCategoryCounts,
    enabled: auth?.authenticated === true,
  })

  const counts = countsData?.categories ?? []
  const priorityCount = counts.find((c) => c.name === 'priority')
  const totalUnread = counts.reduce((sum, c) => sum + c.unread, 0)
  const totalMessages = counts.reduce((sum, c) => sum + c.total, 0)

  return (
    <div>
      <h3 className="section-title">COMMUNICATIONS</h3>

      {isLoading ? (
        <LoadingSkeleton lines={3} />
      ) : !auth?.authenticated ? (
        <p className="text-sm text-text-secondary py-4">
          Email not connected
        </p>
      ) : (
        <div className="space-y-0">
          <div
            onClick={() => navigate('/comms?filter=priority')}
            className="flex items-center justify-between py-3.5 border-b border-border/50 cursor-pointer hover:bg-surface/30 transition-colors rounded px-2 -mx-2"
          >
            <div>
              <p className="text-[14px] text-text-primary">Priority Unread</p>
              <p className="text-[11px] text-text-secondary mt-0.5">
                {totalUnread} total unread / {totalMessages} messages
              </p>
            </div>
            <span className="font-mono text-xl font-bold text-accent">
              {priorityCount?.unread ?? 0}
            </span>
          </div>
          <div
            onClick={() => navigate('/comms')}
            className="flex items-center justify-between py-3.5 cursor-pointer hover:bg-surface/30 transition-colors rounded px-2 -mx-2"
          >
            <div>
              <p className="text-[14px] text-text-primary">Priority Threads</p>
              <p className="text-[11px] text-text-secondary mt-0.5">
                {priorityCount?.total ?? 0} direct messages
              </p>
            </div>
            <span className="font-mono text-xl font-bold text-text-primary">
              {priorityCount?.total ?? 0}
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
