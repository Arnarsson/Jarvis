import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

// --- Types ---

interface PageVisit {
  path: string
  label: string
  timestamp: number
  context?: string // optional extra context like search query
}

// --- Storage ---

const STORAGE_KEY = 'jarvis-page-visits'
const MAX_TRACKED = 50

// Page metadata for display
const PAGE_META: Record<string, { label: string; icon: string; description: string }> = {
  '/': { label: 'Overview', icon: '◻', description: 'Dashboard overview' },
  '/daily3': { label: 'Daily 3', icon: '🎯', description: 'Today\'s priorities' },
  '/focus': { label: 'Focus Mode', icon: '⏱', description: 'Pomodoro timer' },
  '/capture': { label: 'Quick Capture', icon: '⚡', description: 'Thoughts & notes' },
  '/promises': { label: 'Promises', icon: '🤝', description: 'Commitments tracker' },
  '/patterns': { label: 'Patterns', icon: '🔍', description: 'Behavior patterns' },
  '/memory': { label: 'Memory', icon: '🧠', description: 'Search memory' },
  '/brain': { label: 'Brain Timeline', icon: '🧠', description: 'Knowledge timeline' },
  '/schedule': { label: 'Schedule', icon: '📅', description: 'Calendar & events' },
  '/comms': { label: 'Communications', icon: '✉️', description: 'Emails & messages' },
  '/tasks': { label: 'Tasks', icon: '✓', description: 'Task management' },
  '/command': { label: 'Eureka Terminal', icon: '◈', description: 'Chat with Eureka' },
  '/system': { label: 'System', icon: '⚙', description: 'System status' },
  '/catchup': { label: 'Catch Up', icon: '📋', description: 'Quick catch-up' },
}

export function trackPageVisit(path: string, context?: string) {
  // Don't track the overview page itself
  if (path === '/') return

  try {
    const existing: PageVisit[] = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
    const meta = PAGE_META[path]
    if (!meta) return // Unknown page, skip

    const visit: PageVisit = {
      path,
      label: meta.label,
      timestamp: Date.now(),
      context,
    }

    // Remove duplicate paths (keep only latest)
    const filtered = existing.filter((v) => v.path !== path)
    filtered.unshift(visit)

    // Trim to max
    const trimmed = filtered.slice(0, MAX_TRACKED)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed))
  } catch (err) {
    console.error('Failed to record page visit to localStorage:', err)
  }
}

function getRecentVisits(limit = 3): PageVisit[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const visits: PageVisit[] = JSON.parse(raw)
    return visits.slice(0, limit)
  } catch {
    return []
  }
}

function timeAgo(ts: number): string {
  const diff = Date.now() - ts
  const mins = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  if (hours < 24) return `${hours}h ago`
  if (days === 1) return 'yesterday'
  return `${days}d ago`
}

// --- Component ---

export function WhereYouLeftOff() {
  const [visits, setVisits] = useState<PageVisit[]>([])

  useEffect(() => {
    setVisits(getRecentVisits(3))
    // Refresh periodically
    const interval = setInterval(() => setVisits(getRecentVisits(3)), 15_000)
    return () => clearInterval(interval)
  }, [])

  if (visits.length === 0) return null

  return (
    <div className="mb-8">
      <h3 className="font-mono text-[11px] text-text-secondary tracking-widest uppercase mb-4">
        ↩ WHERE YOU LEFT OFF
      </h3>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {visits.map((visit, i) => {
          const meta = PAGE_META[visit.path]
          if (!meta) return null

          return (
            <Link
              key={`${visit.path}-${i}`}
              to={visit.path}
              className="group block p-4 bg-surface/60 border border-border/50 rounded-lg hover:border-accent/40 hover:bg-surface transition-all"
            >
              <div className="flex items-start gap-3">
                <span className="text-lg shrink-0">{meta.icon}</span>
                <div className="flex-1 min-w-0">
                  <p className="font-mono text-sm text-text-primary group-hover:text-accent transition-colors truncate">
                    Continue: {meta.label}
                  </p>
                  <p className="font-mono text-[11px] text-text-muted mt-1">
                    {meta.description}
                  </p>
                  <p className="font-mono text-[10px] text-text-muted mt-2">
                    {timeAgo(visit.timestamp)}
                  </p>
                </div>
                <svg
                  className="w-4 h-4 text-text-muted group-hover:text-accent shrink-0 mt-1 transition-colors"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={1.5}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                </svg>
              </div>
            </Link>
          )
        })}
      </div>
    </div>
  )
}
