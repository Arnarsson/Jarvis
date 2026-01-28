export interface ActionSuggestionProps {
  title: string
  reason: string
  confidence: number
  actions: {
    label: string
    onClick: () => void
    primary?: boolean
  }[]
}

export function ActionSuggestion({
  title,
  reason,
  confidence,
  actions,
}: ActionSuggestionProps) {
  return (
    <div className="p-4 border border-accent/30 rounded-lg bg-surface">
      <div className="flex justify-between items-start">
        <div>
          <h4 className="font-mono text-sm font-bold">{title}</h4>
          <p className="text-text-secondary text-xs mt-1">{reason}</p>
        </div>
        <span className="text-xs text-text-secondary">
          {Math.round(confidence * 100)}%
        </span>
      </div>
      <div className="flex gap-2 mt-3 flex-wrap">
        {actions.map((action, i) => (
          <button
            key={i}
            onClick={action.onClick}
            className={`px-3 py-1 text-xs rounded ${
              action.primary
                ? 'bg-accent text-white'
                : 'border border-border hover:bg-surface-hover'
            }`}
          >
            {action.label}
          </button>
        ))}
      </div>
    </div>
  )
}
