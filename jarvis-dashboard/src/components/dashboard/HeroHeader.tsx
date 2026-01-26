import { useState, useEffect } from 'react'
import { useAppStore } from '../../stores/app.ts'

function formatDateHeader(date: Date): string {
  const day = date.getDate().toString().padStart(2, '0')
  const month = date.toLocaleDateString('en-US', { month: 'short' }).toUpperCase()
  const year = date.getFullYear()
  const weekday = date.toLocaleDateString('en-US', { weekday: 'long' }).toUpperCase()
  return `${day} ${month} ${year} / ${weekday}`
}

function formatClock(date: Date): string {
  return date.toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function HeroHeader() {
  const { userName, systemStatus } = useAppStore()
  const [now, setNow] = useState(new Date())

  useEffect(() => {
    const interval = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="mb-8">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between">
        {/* Left: date + name */}
        <div>
          <p className="font-mono text-[11px] text-text-secondary tracking-wider mb-1">
            {formatDateHeader(now)}
          </p>
          <h1 className="text-4xl sm:text-5xl lg:text-[3.5rem] font-bold text-text-primary tracking-tight leading-none">
            {userName.toUpperCase()}
          </h1>
        </div>

        {/* Right: clock + status */}
        <div className="flex flex-col items-end mt-3 sm:mt-0">
          <span className="font-mono text-3xl sm:text-4xl text-text-primary tabular-nums tracking-wide">
            {formatClock(now)}
          </span>
          <div className="flex items-center gap-2 mt-1">
            <span
              className={`inline-block h-2 w-2 rounded-full ${
                systemStatus === 'operational'
                  ? 'bg-accent animate-pulse-dot'
                  : systemStatus === 'degraded'
                    ? 'bg-warning'
                    : 'bg-text-muted'
              }`}
            />
            <span className="font-mono text-[11px] text-accent tracking-wider">
              {systemStatus === 'operational'
                ? 'SYSTEM ACTIVE'
                : systemStatus === 'degraded'
                  ? 'SYSTEM DEGRADED'
                  : 'SYSTEM DOWN'}
            </span>
          </div>
        </div>
      </div>

      {/* Divider */}
      <div className="border-t border-border mt-6" />
    </div>
  )
}
