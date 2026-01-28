import { useState, useEffect } from 'react'
import { apiGet } from '../../api/client.ts'
import { ContextHandoffModal } from '../ContextHandoffModal.tsx'

/* ───────────────────────── Types ───────────────────────── */

interface ProjectActivity {
  name: string
  activity_score: number
  status: string
  trend: string
  last_activity: string | null
  conversation_mentions_7d: number
  conversation_mentions_prev_7d: number
  github_commits_7d: number
  github_repo: string | null
  days_since_activity: number | null
  suggested_action: string | null
}

interface ProjectPulseData {
  projects: ProjectActivity[]
  total_projects: number
  active_count: number
  warming_count: number
  cooling_count: number
  stale_count: number
}

/* ───────────────────────── Helpers ───────────────────────── */

function timeAgo(isoDate: string | null): string {
  if (!isoDate) return 'unknown'
  try {
    const now = Date.now()
    const then = new Date(isoDate).getTime()
    const diffMs = now - then
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffDays === 0) return 'today'
    if (diffDays === 1) return 'yesterday'
    if (diffDays < 7) return `${diffDays}d ago`
    if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`
    if (diffDays < 365) return `${Math.floor(diffDays / 30)}mo ago`
    return `${Math.floor(diffDays / 365)}y ago`
  } catch {
    return 'unknown'
  }
}

/* ───────────────────────── Project Card ───────────────────────── */

function ProjectCard({ 
  project, 
  onClick 
}: { 
  project: ProjectActivity
  onClick?: () => void 
}) {
  const statusConfig = {
    active: {
      label: 'ACTIVE',
      color: 'text-green-400',
      bg: 'bg-green-500/10',
      border: 'border-green-500/30',
      icon: '🟢',
    },
    warming: {
      label: 'WARMING',
      color: 'text-blue-400',
      bg: 'bg-blue-500/10',
      border: 'border-blue-500/30',
      icon: '🔵',
    },
    cooling: {
      label: 'COOLING',
      color: 'text-yellow-400',
      bg: 'bg-yellow-500/10',
      border: 'border-yellow-500/30',
      icon: '🟡',
    },
    stale: {
      label: 'STALE',
      color: 'text-red-400',
      bg: 'bg-red-500/10',
      border: 'border-red-500/30',
      icon: '🔴',
    },
  }[project.status] || {
    label: project.status.toUpperCase(),
    color: 'text-text-muted',
    bg: 'bg-surface',
    border: 'border-border',
    icon: '⚪',
  }

  const trendIcon = {
    up: '📈',
    down: '📉',
    flat: '➡️',
  }[project.trend] || '➡️'

  return (
    <div
      onClick={onClick}
      className={`border rounded-lg p-4 ${statusConfig.bg} ${statusConfig.border} hover:border-accent/50 transition-colors ${onClick ? 'cursor-pointer' : ''}`}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2">
          <span className="text-base">{statusConfig.icon}</span>
          <h3 className="text-sm font-mono font-semibold text-text-primary">
            {project.name}
          </h3>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-base" title={`Trend: ${project.trend}`}>
            {trendIcon}
          </span>
          <span
            className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${statusConfig.color} bg-black/20 uppercase`}
          >
            {statusConfig.label}
          </span>
        </div>
      </div>

      {/* Activity Stats */}
      <div className="grid grid-cols-2 gap-3 mb-3 text-[11px] font-mono">
        <div>
          <div className="text-text-muted">Last 7d</div>
          <div className="text-text-primary">
            {project.conversation_mentions_7d} mentions
          </div>
        </div>
        <div>
          <div className="text-text-muted">Previous 7d</div>
          <div className="text-text-primary">
            {project.conversation_mentions_prev_7d} mentions
          </div>
        </div>
      </div>

      {/* GitHub Badge */}
      {project.github_repo && project.github_commits_7d > 0 && (
        <div className="mb-3 text-[11px] font-mono text-accent flex items-center gap-2">
          <span>🐙</span>
          <span>{project.github_commits_7d} commits (7d)</span>
        </div>
      )}

      {/* Last Activity */}
      <div className="text-[11px] font-mono text-text-muted mb-3">
        Last activity: {timeAgo(project.last_activity)}
      </div>

      {/* Suggested Action */}
      {project.suggested_action && (
        <div className="text-[11px] font-mono text-accent">
          💡 {project.suggested_action}
        </div>
      )}
    </div>
  )
}

/* ───────────────────────── Main Component ───────────────────────── */

export function ProjectPulse() {
  const [data, setData] = useState<ProjectPulseData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [handoffProject, setHandoffProject] = useState<string>('')
  const [showHandoffModal, setShowHandoffModal] = useState(false)

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await apiGet<ProjectPulseData>(
        '/api/v2/projects/pulse?min_mentions=3&include_github=true&limit=20'
      )
      setData(response)
    } catch (e) {
      console.error('Failed to fetch project pulse:', e)
      setError('Failed to load project pulse')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mb-10">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-mono font-bold text-text-primary tracking-wider uppercase">
            📊 PROJECT PULSE
          </h2>
          <p className="text-xs font-mono text-text-muted tracking-wide mt-1">
            Weekly activity scores & momentum tracking
          </p>
        </div>
        <button
          onClick={fetchData}
          disabled={loading}
          className="px-3 py-1.5 text-[11px] font-mono border border-border text-text-primary hover:border-accent hover:text-accent transition-colors disabled:opacity-50"
        >
          {loading ? 'LOADING...' : 'REFRESH'}
        </button>
      </div>

      {/* Stats Row */}
      {data && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
          <div className="border border-border rounded p-3 text-center">
            <div className="text-xl font-mono font-bold text-text-primary">
              {data.total_projects}
            </div>
            <div className="text-[10px] font-mono text-text-muted uppercase tracking-wider">
              Total Projects
            </div>
          </div>
          <div className="border border-green-500/30 rounded p-3 text-center bg-green-500/5">
            <div className="text-xl font-mono font-bold text-green-400">
              {data.active_count}
            </div>
            <div className="text-[10px] font-mono text-text-muted uppercase tracking-wider">
              Active
            </div>
          </div>
          <div className="border border-blue-500/30 rounded p-3 text-center bg-blue-500/5">
            <div className="text-xl font-mono font-bold text-blue-400">
              {data.warming_count}
            </div>
            <div className="text-[10px] font-mono text-text-muted uppercase tracking-wider">
              Warming
            </div>
          </div>
          <div className="border border-yellow-500/30 rounded p-3 text-center bg-yellow-500/5">
            <div className="text-xl font-mono font-bold text-yellow-400">
              {data.cooling_count}
            </div>
            <div className="text-[10px] font-mono text-text-muted uppercase tracking-wider">
              Cooling
            </div>
          </div>
          <div className="border border-red-500/30 rounded p-3 text-center bg-red-500/5">
            <div className="text-xl font-mono font-bold text-red-400">
              {data.stale_count}
            </div>
            <div className="text-[10px] font-mono text-text-muted uppercase tracking-wider">
              Stale
            </div>
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="border border-red-500/20 rounded-lg p-4 bg-red-500/5 mb-4">
          <p className="text-red-400/70 text-xs font-mono">{error}</p>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center gap-2 text-text-muted text-xs font-mono py-8">
          <span className="inline-block h-2 w-2 rounded-full bg-accent animate-pulse" />
          Calculating project pulse…
        </div>
      )}

      {/* Projects Grid */}
      {!loading && data && data.projects.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {data.projects.slice(0, 12).map((project) => (
            <ProjectCard 
              key={project.name} 
              project={project} 
              onClick={() => {
                setHandoffProject(project.name)
                setShowHandoffModal(true)
              }}
            />
          ))}
        </div>
      )}

      {/* Empty State */}
      {!loading && data && data.projects.length === 0 && (
        <div className="border border-border/30 rounded-lg p-10 text-center">
          <div className="text-3xl mb-4">📊</div>
          <p className="text-sm font-mono text-text-secondary">
            No active projects found
          </p>
        </div>
      )}

      {/* Context Handoff Modal */}
      <ContextHandoffModal
        isOpen={showHandoffModal}
        project={handoffProject}
        onClose={() => setShowHandoffModal(false)}
      />
    </div>
  )
}
