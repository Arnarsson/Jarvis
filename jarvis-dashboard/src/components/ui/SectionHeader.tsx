interface SectionHeaderProps {
  title: string
  action?: {
    label: string
    onClick: () => void
  }
}

export function SectionHeader({ title, action }: SectionHeaderProps) {
  return (
    <div className="flex items-center justify-between mb-4">
      <h3 className="section-title">{title}</h3>
      {action && (
        <button
          onClick={action.onClick}
          className="font-mono text-[11px] tracking-wider text-accent hover:text-accent-hover transition-colors"
        >
          {action.label}
        </button>
      )}
    </div>
  )
}
