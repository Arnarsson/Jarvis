import { useQuery } from '@tanstack/react-query'
import { fetchWorkflowSuggestions } from '../../api/health.ts'
import { LoadingSkeleton } from '../ui/LoadingSkeleton.tsx'

// Static fallback data matching the design
const fallbackItems = [
  {
    id: '1',
    title: 'Q1 Marketing Budget',
    subtitle: 'Value: $2.5M / From: CMO',
  },
  {
    id: '2',
    title: 'Partnership: Microsoft',
    subtitle: 'Reviewing Legal Clauses',
  },
  {
    id: '3',
    title: 'Senior Engineer Hire',
    subtitle: 'Hiring Pipeline / V.P. ENG',
  },
]

export function PendingLogic() {
  const { data: suggestions, isLoading } = useQuery({
    queryKey: ['workflow', 'suggestions'],
    queryFn: fetchWorkflowSuggestions,
  })

  const items =
    suggestions && suggestions.length > 0
      ? suggestions.map((s) => ({
          id: s.id,
          title: s.title,
          subtitle: `${s.type} / ${s.priority}`,
        }))
      : fallbackItems

  return (
    <div>
      <h3 className="section-title">PENDING LOGIC</h3>

      {isLoading ? (
        <LoadingSkeleton lines={3} />
      ) : (
        <div className="space-y-0">
          {items.map((item) => (
            <div
              key={item.id}
              className="flex items-center justify-between py-4 border-b border-border/50 last:border-b-0"
            >
              <div className="flex-1 min-w-0">
                <p className="text-[15px] text-text-primary font-medium">
                  {item.title}
                </p>
                <p className="text-[12px] text-text-secondary mt-1">
                  {item.subtitle}
                </p>
              </div>
              <button className="ml-4 shrink-0 font-mono text-[12px] tracking-wider text-accent hover:text-accent-hover transition-colors font-bold">
                DECIDE
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
