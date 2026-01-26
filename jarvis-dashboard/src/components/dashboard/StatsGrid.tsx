import { useStats } from '../../hooks/useStats.ts'
import { StatCard } from '../ui/StatCard.tsx'

function padValue(n: number): string {
  return n.toString().padStart(2, '0')
}

export function StatsGrid() {
  const { stats, isLoading } = useStats()

  if (isLoading) {
    return (
      <div className="mb-10 grid grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="border border-border p-5">
            <div className="h-3 w-16 bg-border/50 rounded mb-3 animate-pulse" />
            <div className="h-9 w-12 bg-border/50 rounded animate-pulse" />
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="mb-10 grid grid-cols-2 lg:grid-cols-4">
      <StatCard
        label="MEETINGS"
        value={padValue(stats.meetingsToday)}
      />
      <StatCard
        label="INBOUND"
        value={padValue(stats.inboundCount)}
      />
      <StatCard
        label="ACTIONS"
        value={padValue(stats.pendingActions)}
        accent={stats.pendingActions > 0}
      />
      <StatCard
        label="VELOCITY"
        value={`${stats.velocity}%`}
      />
    </div>
  )
}
