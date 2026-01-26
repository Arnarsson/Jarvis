interface BadgeProps {
  label: string
  variant?: 'default' | 'priority' | 'success' | 'warning'
}

const variantClasses: Record<NonNullable<BadgeProps['variant']>, string> = {
  default: 'border-border text-text-secondary bg-border/30',
  priority: 'border-accent/40 text-accent bg-accent/10',
  success: 'border-success/40 text-success bg-success/10',
  warning: 'border-warning/40 text-warning bg-warning/10',
}

export function Badge({ label, variant = 'default' }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center font-mono text-[10px] tracking-wider px-2.5 py-1 border ${variantClasses[variant]}`}
    >
      {label}
    </span>
  )
}
