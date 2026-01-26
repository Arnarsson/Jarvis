interface StatusDotProps {
  status: 'operational' | 'degraded' | 'down'
}

const statusColors: Record<StatusDotProps['status'], string> = {
  operational: 'bg-success',
  degraded: 'bg-warning',
  down: 'bg-accent',
}

export function StatusDot({ status }: StatusDotProps) {
  return (
    <span
      className={`inline-block h-2 w-2 rounded-full ${statusColors[status]} ${
        status === 'operational' ? 'animate-pulse-dot' : ''
      }`}
    />
  )
}
