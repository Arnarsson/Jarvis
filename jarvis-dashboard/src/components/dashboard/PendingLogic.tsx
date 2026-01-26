import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { fetchWorkflowSuggestions } from '../../api/health.ts'
import { apiPost } from '../../api/client.ts'
import { LoadingSkeleton } from '../ui/LoadingSkeleton.tsx'
import { useNavigate } from 'react-router-dom'

export function PendingLogic() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const { data: suggestions, isLoading } = useQuery({
    queryKey: ['workflow', 'suggestions'],
    queryFn: fetchWorkflowSuggestions,
  })

  const approveMutation = useMutation({
    mutationFn: (id: string) =>
      apiPost(`/api/workflow/suggestions/${id}/approve`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflow', 'suggestions'] })
      queryClient.invalidateQueries({ queryKey: ['workflow', 'patterns'] })
      setExpandedId(null)
    },
  })

  const rejectMutation = useMutation({
    mutationFn: (id: string) =>
      apiPost(`/api/workflow/suggestions/${id}/reject`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflow', 'suggestions'] })
      setExpandedId(null)
    },
  })

  const isMutating = approveMutation.isPending || rejectMutation.isPending

  return (
    <div>
      <div className="flex items-center justify-between mb-0">
        <h3 className="section-title">PENDING LOGIC</h3>
        {suggestions && suggestions.length > 0 && (
          <button
            onClick={() => navigate('/tasks')}
            className="font-mono text-[11px] tracking-wider text-text-secondary hover:text-accent transition-colors"
          >
            VIEW ALL &rarr;
          </button>
        )}
      </div>

      {isLoading ? (
        <LoadingSkeleton lines={3} />
      ) : suggestions && suggestions.length > 0 ? (
        <div className="space-y-0">
          {suggestions.map((item) => (
            <div
              key={item.id}
              className="py-4 border-b border-border/50 last:border-b-0"
            >
              <div className="flex items-center justify-between">
                <div className="flex-1 min-w-0">
                  <p className="text-[15px] text-text-primary font-medium">
                    {item.name}
                  </p>
                  <p className="text-[12px] text-text-secondary mt-1">
                    {item.description || `${item.pattern_type} / Confidence: ${Math.round(item.confidence * 100)}%`}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() =>
                    setExpandedId(expandedId === item.id ? null : item.id)
                  }
                  className="ml-4 shrink-0 font-mono text-[12px] tracking-wider text-accent hover:text-accent-hover transition-colors font-bold"
                >
                  {expandedId === item.id ? 'CLOSE' : 'DECIDE'}
                </button>
              </div>

              {/* Inline approve/reject actions */}
              {expandedId === item.id && (
                <div className="mt-3 flex gap-2">
                  <button
                    type="button"
                    onClick={() => approveMutation.mutate(item.id)}
                    disabled={isMutating}
                    className="font-mono text-[11px] tracking-wider font-bold px-4 py-1.5 border border-accent text-accent hover:bg-accent/10 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {approveMutation.isPending && approveMutation.variables === item.id
                      ? 'APPROVING...'
                      : 'APPROVE'}
                  </button>
                  <button
                    type="button"
                    onClick={() => rejectMutation.mutate(item.id)}
                    disabled={isMutating}
                    className="font-mono text-[11px] tracking-wider font-bold px-4 py-1.5 border border-border text-text-secondary hover:text-text-primary hover:border-border-light transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {rejectMutation.isPending && rejectMutation.variables === item.id
                      ? 'REJECTING...'
                      : 'REJECT'}
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-text-secondary py-4">
          No pending decisions
        </p>
      )}
    </div>
  )
}
