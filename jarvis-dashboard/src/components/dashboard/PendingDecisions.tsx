import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../../api/client.ts'
import { LoadingSkeleton } from '../ui/LoadingSkeleton.tsx'
import { Badge } from '../ui/Badge.tsx'

interface DecisionItem {
  id: string
  subject: string | null
  from_address: string | null
  from_name: string | null
  date_sent: string
  snippet: string | null
  decision_type: string
  urgency: string
}

interface DecisionsResponse {
  decisions: DecisionItem[]
  count: number
}

async function fetchPendingDecisions(): Promise<DecisionsResponse> {
  return apiGet<DecisionsResponse>('/api/email/v2/decisions')
}

function formatDate(isoDate: string): string {
  const date = new Date(isoDate)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))
  
  if (diffDays === 0) return 'Today'
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return `${diffDays}d ago`
  
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function DecisionTypeLabel({ type }: { type: string }) {
  const labels: Record<string, string> = {
    approval: 'APPROVAL',
    confirmation: 'CONFIRM',
    deadline: 'DEADLINE',
    'sign-off': 'SIGN-OFF',
    action: 'ACTION',
  }
  
  return (
    <span className="font-mono text-[10px] tracking-wider text-text-muted">
      {labels[type] || type.toUpperCase()}
    </span>
  )
}

export function PendingDecisions() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['email', 'decisions'],
    queryFn: fetchPendingDecisions,
  })
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const decisions = data?.decisions ?? []

  return (
    <div>
      <h3 className="section-title">PENDING DECISIONS</h3>

      {isLoading ? (
        <LoadingSkeleton lines={3} />
      ) : error ? (
        <p className="text-sm text-text-secondary py-4">
          Failed to load decisions
        </p>
      ) : decisions.length === 0 ? (
        <p className="text-sm text-text-secondary py-4">
          No pending decisions
        </p>
      ) : (
        <div className="space-y-4">
          {decisions.slice(0, 5).map((decision) => {
            const isExpanded = expandedId === decision.id
            return (
              <div
                key={decision.id}
                className="p-4 bg-background-elevated border border-border rounded-lg hover:border-accent/40 transition-colors"
              >
                {/* Header: From + Date */}
                <div className="flex items-start justify-between gap-4 mb-2">
                  <div 
                    className="flex-1 min-w-0 cursor-pointer"
                    onClick={() => setExpandedId(isExpanded ? null : decision.id)}
                  >
                    <p className="text-[13px] font-medium text-text-primary truncate">
                      {decision.from_name || decision.from_address || 'Unknown'}
                    </p>
                    <p className="text-[11px] text-text-secondary mt-0.5">
                      {formatDate(decision.date_sent)}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <DecisionTypeLabel type={decision.decision_type} />
                    {decision.urgency === 'high' && (
                      <Badge label="HIGH" variant="warning" />
                    )}
                  </div>
                </div>

                {/* Subject */}
                <h4 
                  className="text-[14px] font-medium text-text-primary mb-2 line-clamp-2 cursor-pointer"
                  onClick={() => setExpandedId(isExpanded ? null : decision.id)}
                >
                  {decision.subject || '(No subject)'}
                </h4>

                {/* Snippet — expanded shows full text */}
                {decision.snippet && (
                  <p 
                    className={`text-[12px] text-text-secondary mb-3 cursor-pointer ${isExpanded ? '' : 'line-clamp-2'}`}
                    onClick={() => setExpandedId(isExpanded ? null : decision.id)}
                  >
                    {decision.snippet}
                  </p>
                )}

                {/* Action Buttons */}
                <div className="flex gap-2 flex-wrap mt-3">
                  <button 
                    onClick={(e) => {
                      e.stopPropagation()
                      // TODO: Implement reply action
                      console.log('Reply to:', decision.id)
                    }}
                    className="px-3 py-1.5 text-xs bg-accent text-black rounded hover:bg-accent/80 transition-colors font-mono"
                  >
                    ✉️ Reply
                  </button>
                  {(decision.decision_type === 'approval' || decision.decision_type === 'sign-off') && (
                    <button 
                      onClick={(e) => {
                        e.stopPropagation()
                        // TODO: Implement approve action
                        console.log('Approve:', decision.id)
                      }}
                      className="px-3 py-1.5 text-xs border border-green-500/50 text-green-400 rounded hover:bg-green-500/10 transition-colors font-mono"
                    >
                      ✓ Approve
                    </button>
                  )}
                  <button 
                    onClick={(e) => {
                      e.stopPropagation()
                      // TODO: Implement snooze action
                      console.log('Snooze:', decision.id)
                    }}
                    className="px-3 py-1.5 text-xs border border-border rounded hover:bg-surface-hover transition-colors font-mono text-text-secondary"
                  >
                    ⏰ Snooze
                  </button>
                  <button 
                    onClick={(e) => {
                      e.stopPropagation()
                      // TODO: Implement mark read action
                      console.log('Mark done:', decision.id)
                    }}
                    className="px-3 py-1.5 text-xs border border-border rounded hover:bg-surface-hover transition-colors font-mono text-text-muted"
                  >
                    ✓ Done
                  </button>
                </div>
              </div>
            )
          })}

          {decisions.length > 5 && (
            <p className="text-[11px] text-text-muted text-center pt-2">
              +{decisions.length - 5} more decisions pending
            </p>
          )}
        </div>
      )}
    </div>
  )
}
