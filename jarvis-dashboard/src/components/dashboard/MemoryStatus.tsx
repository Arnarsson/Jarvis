import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../../api/client.ts'
import { StatusDot } from '../ui/StatusDot.tsx'
import { LoadingSkeleton } from '../ui/LoadingSkeleton.tsx'

interface SearchHealth {
  status: string
  document_count?: number
  collection_count?: number
}

interface HealthResponse {
  status: string
}

async function fetchSearchHealth(): Promise<SearchHealth> {
  try {
    return await apiGet<SearchHealth>('/api/search/health')
  } catch {
    return { status: 'unavailable' }
  }
}

async function fetchServerHealth(): Promise<HealthResponse> {
  try {
    return await apiGet<HealthResponse>('/health/')
  } catch {
    return { status: 'down' }
  }
}

export function MemoryStatus() {
  const { data: search, isLoading: searchLoading } = useQuery({
    queryKey: ['search', 'health'],
    queryFn: fetchSearchHealth,
    refetchInterval: 60_000,
  })

  const { data: health } = useQuery({
    queryKey: ['server', 'health'],
    queryFn: fetchServerHealth,
    refetchInterval: 30_000,
  })

  const serverUp = health?.status === 'ok' || health?.status === 'healthy'
  const searchUp = search?.status === 'ok' || search?.status === 'healthy'

  if (searchLoading) {
    return (
      <div>
        <h3 className="section-title">Memory Status</h3>
        <LoadingSkeleton lines={4} />
      </div>
    )
  }

  return (
    <div>
      <h3 className="section-title">Memory Status</h3>

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-sm text-text-secondary">Documents indexed</span>
          <span className="font-mono text-sm text-text-primary">
            {(search?.document_count ?? 0).toLocaleString()}
          </span>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-sm text-text-secondary">Collections</span>
          <span className="font-mono text-sm text-text-primary">
            {search?.collection_count ?? 0}
          </span>
        </div>

        <div className="border-t border-border" />

        <div className="flex items-center justify-between">
          <span className="text-sm text-text-secondary">Server</span>
          <div className="flex items-center gap-2">
            <StatusDot status={serverUp ? 'operational' : 'down'} />
            <span className={`text-sm ${serverUp ? 'text-success' : 'text-accent'}`}>
              {serverUp ? 'Healthy' : 'Down'}
            </span>
          </div>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-sm text-text-secondary">Search engine</span>
          <div className="flex items-center gap-2">
            <StatusDot status={searchUp ? 'operational' : 'down'} />
            <span className={`text-sm ${searchUp ? 'text-success' : 'text-accent'}`}>
              {searchUp ? 'Connected' : 'Unavailable'}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
