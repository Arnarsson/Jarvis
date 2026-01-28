import { Link } from 'react-router-dom'
import { useState, useEffect } from 'react'

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   COMMAND CENTER — Actionable Dashboard (No Guilt Stats)
   Replaces anxiety-inducing counters with actionable sections
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */

// ─────────────────────────────────────────────────────────────────
// RESUME SECTION — Where you left off
// ─────────────────────────────────────────────────────────────────

interface ResumeCardProps {
  projectName?: string
  lastActive?: string
  nextStep?: string
  filesOpen?: number
}

function ResumeCard({ 
  projectName = 'Jarvis Command Center',
  lastActive = '2h ago',
  nextStep = 'Review UI implementation',
  filesOpen = 3
}: ResumeCardProps) {
  return (
    <div className="bg-surface/60 border border-border/50 rounded-lg p-6 mb-6 hover:border-accent/40 transition-colors">
      <h3 className="font-mono text-[11px] text-text-secondary tracking-widest uppercase mb-4">
        ↩ RESUME
      </h3>
      
      <div className="mb-4">
        <h2 className="text-2xl font-semibold text-text-primary mb-2">
          {projectName}
        </h2>
        <p className="font-mono text-sm text-text-muted">
          Last active: {lastActive} · {filesOpen} files open
        </p>
      </div>

      <div className="mb-6">
        <p className="text-sm text-text-secondary mb-1">Next step:</p>
        <p className="text-base text-text-primary">{nextStep}</p>
      </div>

      <div className="flex gap-3 flex-wrap">
        <button className="px-4 py-2 bg-accent text-black font-mono text-sm rounded hover:bg-accent/80 transition-colors">
          Resume Workspace
        </button>
        <button className="px-4 py-2 border border-border text-text-primary font-mono text-sm rounded hover:border-accent/40 hover:text-accent transition-colors">
          View Brief
        </button>
        <button className="px-4 py-2 border border-border text-text-muted font-mono text-sm rounded hover:border-text-secondary hover:text-text-secondary transition-colors">
          Wrong → Choose
        </button>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// TODAY'S 3 SECTION — Daily priorities
// ─────────────────────────────────────────────────────────────────

interface Daily3Item {
  text: string
  done: boolean
}

function getTodayKey(): string {
  const d = new Date()
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `jarvis-daily3-${yyyy}-${mm}-${dd}`
}

function loadDaily3(): Daily3Item[] {
  try {
    const raw = localStorage.getItem(getTodayKey())
    if (raw) return JSON.parse(raw)
  } catch (err) {
    console.error('Failed to load daily3:', err)
  }
  return []
}

function Todays3Section() {
  const [items, setItems] = useState<Daily3Item[]>(loadDaily3)

  useEffect(() => {
    const interval = setInterval(() => {
      setItems(loadDaily3())
    }, 10_000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="bg-surface/60 border border-border/50 rounded-lg p-6 mb-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-mono text-[11px] text-text-secondary tracking-widest uppercase">
          🎯 TODAY'S 3
        </h3>
        <Link
          to="/daily3"
          className="font-mono text-xs text-accent hover:text-accent/80 transition-colors"
        >
          + Add
        </Link>
      </div>

      {items.length === 0 ? (
        <div className="space-y-2">
          <div className="flex items-center gap-3 text-text-muted">
            <div className="w-4 h-4 border border-text-muted/50 rounded" />
            <span className="font-mono text-sm">Set your first priority...</span>
          </div>
          <div className="flex items-center gap-3 text-text-muted">
            <div className="w-4 h-4 border border-text-muted/50 rounded" />
            <span className="font-mono text-sm">Add second priority...</span>
          </div>
          <div className="flex items-center gap-3 text-text-muted">
            <div className="w-4 h-4 border border-text-muted/50 rounded" />
            <span className="font-mono text-sm">Add third priority...</span>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((item, i) => (
            <div key={i} className="flex items-center gap-3">
              <div
                className={`shrink-0 w-4 h-4 rounded border flex items-center justify-center ${
                  item.done
                    ? 'border-green-400 bg-green-400'
                    : 'border-text-muted'
                }`}
              >
                {item.done && (
                  <svg
                    className="w-3 h-3 text-black"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={3}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M5 13l4 4L19 7"
                    />
                  </svg>
                )}
              </div>
              <span
                className={`font-mono text-sm ${
                  item.done
                    ? 'text-text-muted line-through'
                    : 'text-text-primary'
                }`}
              >
                {item.text}
              </span>
            </div>
          ))}
          {/* Fill remaining slots */}
          {Array.from({ length: Math.max(0, 3 - items.length) }).map((_, i) => (
            <div key={`empty-${i}`} className="flex items-center gap-3 text-text-muted">
              <div className="w-4 h-4 border border-text-muted/50 rounded" />
              <span className="font-mono text-sm">Add priority...</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// OPEN LOOPS SECTION — Commitments & waiting-on
// ─────────────────────────────────────────────────────────────────

interface Loop {
  type: 'waiting' | 'commitment'
  description: string
  person?: string
  thing?: string
  daysOverdue?: number
  dueText?: string
}

function OpenLoopsSection() {
  // Mock data for now - will be replaced with real API
  const loops: Loop[] = [
    {
      type: 'waiting',
      person: 'Thomas',
      thing: 'pricing doc',
      daysOverdue: 3,
      description: 'Waiting on: Thomas pricing doc'
    },
    {
      type: 'commitment',
      thing: 'Send Avnit proposal',
      dueText: 'due today',
      description: 'Your commitment: Send Avnit proposal'
    },
    {
      type: 'waiting',
      person: 'Sarah',
      thing: 'design review',
      daysOverdue: 1,
      description: 'Waiting on: Sarah design review'
    },
    {
      type: 'commitment',
      thing: 'Update Linear roadmap',
      dueText: 'due tomorrow',
      description: 'Your commitment: Update Linear roadmap'
    },
    {
      type: 'waiting',
      person: 'Team',
      thing: 'PR approvals',
      description: 'Waiting on: Team PR approvals'
    }
  ]

  return (
    <div className="bg-surface/60 border border-border/50 rounded-lg p-6 mb-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-mono text-[11px] text-text-secondary tracking-widest uppercase">
          🔄 OPEN LOOPS ({loops.length})
        </h3>
        <Link
          to="/promises"
          className="font-mono text-xs text-accent hover:text-accent/80 transition-colors"
        >
          View All →
        </Link>
      </div>

      <div className="space-y-3">
        {loops.slice(0, 5).map((loop, i) => (
          <div key={i} className="flex items-start gap-3 text-sm">
            <span className="text-text-muted shrink-0 mt-0.5">•</span>
            <div className="flex-1">
              {loop.type === 'waiting' ? (
                <span className="text-text-primary">
                  Waiting on: <span className="text-accent">{loop.person}</span>{' '}
                  <span className="text-text-secondary">{loop.thing}</span>
                  {loop.daysOverdue !== undefined && (
                    <span className="ml-2 text-orange-400 font-mono text-xs">
                      ({loop.daysOverdue}d overdue)
                    </span>
                  )}
                </span>
              ) : (
                <span className="text-text-primary">
                  Your commitment: <span className="text-text-secondary">{loop.thing}</span>
                  {loop.dueText && (
                    <span className="ml-2 text-accent font-mono text-xs">
                      ({loop.dueText})
                    </span>
                  )}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// NEXT MEETING SECTION — Upcoming meeting prep
// ─────────────────────────────────────────────────────────────────

function NextMeetingSection() {
  // Mock data - will be replaced with real calendar API
  const nextMeeting = {
    title: 'Thomas Sync — Jarvis Review',
    minutesUntil: 45,
    hasPrep: true
  }

  if (!nextMeeting) {
    return (
      <div className="bg-surface/60 border border-border/50 rounded-lg p-6 mb-6">
        <h3 className="font-mono text-[11px] text-text-secondary tracking-widest uppercase mb-4">
          📅 NEXT MEETING
        </h3>
        <p className="text-sm text-text-muted">No upcoming meetings today</p>
      </div>
    )
  }

  return (
    <div className="bg-surface/60 border border-border/50 rounded-lg p-6 mb-6 hover:border-accent/40 transition-colors">
      <h3 className="font-mono text-[11px] text-text-secondary tracking-widest uppercase mb-4">
        📅 NEXT MEETING
      </h3>
      
      <div className="mb-4">
        <p className="text-base text-text-primary mb-2">"{nextMeeting.title}"</p>
        <p className="font-mono text-sm text-text-muted">
          in {nextMeeting.minutesUntil} min
        </p>
      </div>

      {nextMeeting.hasPrep && (
        <button className="px-4 py-2 bg-accent text-black font-mono text-sm rounded hover:bg-accent/80 transition-colors">
          Prep in 60s
        </button>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// FOCUS INBOX SECTION — Priority triage
// ─────────────────────────────────────────────────────────────────

function FocusInboxSection() {
  // Mock data - will be replaced with real comms API
  const priorityCount = 4
  const restCount = 127

  return (
    <div className="bg-surface/60 border border-border/50 rounded-lg p-6 mb-6">
      <h3 className="font-mono text-[11px] text-text-secondary tracking-widest uppercase mb-4">
        ✉️ FOCUS INBOX
      </h3>
      
      <div className="mb-4">
        <p className="text-sm text-text-secondary mb-2">
          <span className="text-accent font-semibold">Priority ({priorityCount})</span>
          {' · '}
          <span className="text-text-muted">Rest ({restCount} — auto-filtered)</span>
        </p>
      </div>

      <Link 
        to="/comms"
        className="inline-block px-4 py-2 border border-border text-text-primary font-mono text-sm rounded hover:border-accent/40 hover:text-accent transition-colors"
      >
        Open Triage →
      </Link>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// MAIN COMMAND CENTER COMPONENT
// ─────────────────────────────────────────────────────────────────

export function CommandCenter() {
  return (
    <div className="max-w-4xl mx-auto">
      <ResumeCard />
      <Todays3Section />
      <OpenLoopsSection />
      <NextMeetingSection />
      <FocusInboxSection />
    </div>
  )
}
