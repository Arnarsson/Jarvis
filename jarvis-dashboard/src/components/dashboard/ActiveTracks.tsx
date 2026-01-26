import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../../api/client.ts'
import { LoadingSkeleton } from '../ui/LoadingSkeleton.tsx'

interface WorkflowPattern {
  id: string
  name: string
  status: string
  confidence: number
}

async function fetchPatterns(): Promise<WorkflowPattern[]> {
  try {
    return await apiGet<WorkflowPattern[]>('/api/workflow/patterns')
  } catch {
    return []
  }
}

function ProgressBar({ progress, status }: { progress: number; status: string }) {
  const color =
    status === 'suspended'
      ? 'bg-warning'
      : progress >= 80
        ? 'bg-success'
        : 'bg-accent'

  return (
    <div className="w-full bg-border/50 h-1.5 rounded-full overflow-hidden">
      <div
        className={`h-full rounded-full transition-all ${color}`}
        style={{ width: `${progress}%` }}
      />
    </div>
  )
}

function statusLabel(status: string): string {
  switch (status) {
    case 'active': return 'ACTIVE'
    case 'promoted': return 'PROMOTED'
    case 'suspended': return 'SUSPENDED'
    case 'candidate': return 'CANDIDATE'
    default: return status.toUpperCase()
  }
}

function statusColor(status: string): string {
  switch (status) {
    case 'suspended': return 'text-warning'
    case 'promoted': return 'text-success'
    case 'active': return 'text-accent'
    default: return 'text-text-secondary'
  }
}

export function ActiveTracks() {
  const { data: patterns, isLoading } = useQuery({
    queryKey: ['workflow', 'patterns'],
    queryFn: fetchPatterns,
  })

  return (
    <div>
      <h3 className="section-title">ACTIVE TRACKS</h3>

      {isLoading ? (
        <LoadingSkeleton lines={3} />
      ) : patterns && patterns.length > 0 ? (
        <div className="space-y-0">
          {patterns.slice(0, 5).map((pattern) => {
            const progress = Math.round(pattern.confidence * 100)
            return (
              <div
                key={pattern.id}
                className="py-3.5 border-b border-border/50 last:border-b-0"
              >
                <div className="flex items-center justify-between mb-2">
                  <p className="text-[14px] text-text-primary">{pattern.name}</p>
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-[12px] text-text-secondary">
                      {progress}%
                    </span>
                    <span className={`text-[11px] font-mono tracking-wider ${statusColor(pattern.status)}`}>
                      {statusLabel(pattern.status)}
                    </span>
                  </div>
                </div>
                <ProgressBar progress={progress} status={pattern.status} />
              </div>
            )
          })}
        </div>
      ) : (
        <p className="text-sm text-text-secondary py-4">
          No active workflow patterns
        </p>
      )}
    </div>
  )
}
