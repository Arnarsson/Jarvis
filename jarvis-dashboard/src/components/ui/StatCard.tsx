import { useNavigate } from 'react-router-dom'

interface StatCardProps {
  label: string
  value: string | number
  accent?: boolean
  to?: string
}

export function StatCard({ label, value, accent, to }: StatCardProps) {
  const navigate = useNavigate()

  const handleClick = () => {
    if (to) navigate(to)
  }

  return (
    <div
      onClick={handleClick}
      className={`border border-border p-5 transition-colors ${
        to ? 'cursor-pointer hover:border-accent/50 hover:bg-surface/30' : ''
      }`}
    >
      <p className="font-mono-header text-[11px] text-text-secondary mb-3">
        {label}
      </p>
      <p
        className={`text-3xl sm:text-4xl font-bold tracking-tight ${
          accent ? 'text-accent' : 'text-text-primary'
        }`}
      >
        {value}
      </p>
    </div>
  )
}
