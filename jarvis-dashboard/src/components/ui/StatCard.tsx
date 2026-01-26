interface StatCardProps {
  label: string
  value: string | number
  accent?: boolean
}

export function StatCard({ label, value, accent }: StatCardProps) {
  return (
    <div className="border border-border p-5">
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
