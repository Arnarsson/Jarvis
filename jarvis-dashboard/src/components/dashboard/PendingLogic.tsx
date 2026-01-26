import { useQuery } from '@tanstack/react-query'
import { fetchWorkflowSuggestions } from '../../api/health.ts'
import { LoadingSkeleton } from '../ui/LoadingSkeleton.tsx'

export function PendingLogic() {
  const { data: suggestions, isLoading } = useQuery({
    queryKey: ['workflow', 'suggestions'],
    queryFn: fetchWorkflowSuggestions,
  })

  return (
    <div>
      <h3 className="section-title">PENDING LOGIC</h3>

      {isLoading ? (
        <LoadingSkeleton lines={3} />
      ) : suggestions && suggestions.length > 0 ? (
        <div className="space-y-0">
          {suggestions.map((item) => (
            <div
              key={item.id}
              className="flex items-center justify-between py-4 border-b border-border/50 last:border-b-0"
            >
              <div className="flex-1 min-w-0">
                <p className="text-[15px] text-text-primary font-medium">
                  {item.name}
                </p>
                <p className="text-[12px] text-text-secondary mt-1">
                  {item.description || `${item.pattern_type} / Confidence: ${Math.round(item.confidence * 100)}%`}
                </p>
              </div>
              <button className="ml-4 shrink-0 font-mono text-[12px] tracking-wider text-accent hover:text-accent-hover transition-colors font-bold">
                DECIDE
              </button>
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
