import { useState, useEffect } from 'react'
import { apiGet } from '../../api/client.ts'

/* ───────────────────────── Types ───────────────────────── */

interface MorningBriefingData {
  text: string
  sections: {
    calendar: Array<{
      summary: string
      start_time: string
      end_time: string
      location?: string
      attendees: string[]
    }>
    email_highlights: Array<{
      subject: string
      from_name: string
      from_address: string
      snippet: string
      received: string
      priority: string
    }>
    unfinished_business: Array<{
      topic: string
      description: string
      last_seen: string
      suggested_action: string
    }>
    follow_ups_due: Array<{
      text: string
      due_by?: string
      days_overdue?: number
    }>
    pattern_alerts: Array<{
      pattern_type: string
      key: string
      description: string
      suggested_action: string
    }>
    overnight_activity: Array<{
      hour: number
      summary: string
      apps: string[]
      topics: string[]
    }>
    linear_tasks: Array<{
      identifier: string
      title: string
      state: string
      priority: number
      priority_label: string
      due_date?: string
    }>
    daily3_suggestions: Array<{
      priority: string
      rationale: string
    }>
  }
  generated_at: string
}

/* ───────────────────────── Component ───────────────────────── */

export function MorningBriefing() {
  const [briefing, setBriefing] = useState<MorningBriefingData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    // Auto-load on mount
    fetchBriefing()
  }, [])

  const fetchBriefing = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await apiGet<MorningBriefingData>('/api/v2/briefing/morning')
      setBriefing(data)
      setExpanded(false) // Collapse after fresh generation
    } catch (e) {
      console.error('Failed to fetch morning briefing:', e)
      setError('Failed to load briefing')
    } finally {
      setLoading(false)
    }
  }

  const formatTime = (isoTime: string): string => {
    try {
      const date = new Date(isoTime)
      return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
    } catch {
      return ''
    }
  }

  const formatGeneratedTime = (isoTime: string): string => {
    try {
      const date = new Date(isoTime)
      const now = new Date()
      const diffMs = now.getTime() - date.getTime()
      const diffMins = Math.floor(diffMs / 60000)
      
      if (diffMins < 1) return 'just now'
      if (diffMins < 60) return `${diffMins}m ago`
      const diffHours = Math.floor(diffMins / 60)
      if (diffHours < 24) return `${diffHours}h ago`
      return date.toLocaleDateString()
    } catch {
      return ''
    }
  }

  return (
    <div className="mb-10">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-mono font-bold text-text-primary tracking-wider uppercase">
            ☀️ MORNING BRIEFING
          </h2>
          {briefing && (
            <span className="text-[10px] font-mono text-text-muted">
              Generated {formatGeneratedTime(briefing.generated_at)}
            </span>
          )}
        </div>
        <button
          onClick={fetchBriefing}
          disabled={loading}
          className="px-3 py-1.5 text-[11px] font-mono border border-border text-text-primary hover:border-accent hover:text-accent transition-colors disabled:opacity-50"
        >
          {loading ? 'GENERATING...' : 'REFRESH'}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="border border-red-500/20 rounded-lg p-4 bg-red-500/5 mb-4">
          <p className="text-red-400/70 text-xs font-mono">{error}</p>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="border border-border/30 rounded-lg p-6 bg-surface">
          <div className="flex items-center gap-2 text-text-muted text-xs font-mono">
            <span className="inline-block h-2 w-2 rounded-full bg-accent animate-pulse" />
            Generating briefing…
          </div>
        </div>
      )}

      {/* Briefing Card */}
      {!loading && briefing && (
        <div className="border border-border/30 rounded-lg bg-surface overflow-hidden">
          {/* Collapsible Text */}
          <div className="p-6">
            <button
              onClick={() => setExpanded(!expanded)}
              className="w-full text-left"
            >
              <div className="flex items-start justify-between gap-4">
                <div className={`text-xs font-mono text-text-secondary leading-relaxed whitespace-pre-line ${expanded ? '' : 'line-clamp-3'}`}>
                  {briefing.text}
                </div>
                <span className="text-text-muted text-xs flex-shrink-0">
                  {expanded ? '▲' : '▼'}
                </span>
              </div>
            </button>
          </div>

          {/* Summary Stats */}
          <div className="border-t border-border/30 bg-background/30 p-4">
            <div className="grid grid-cols-2 md:grid-cols-7 gap-4 text-center">
              {/* Calendar */}
              <div>
                <div className="text-xl font-mono font-bold text-accent">
                  {briefing.sections.calendar.length}
                </div>
                <div className="text-[10px] font-mono text-text-muted uppercase tracking-wider">
                  Events
                </div>
              </div>

              {/* Linear Tasks */}
              <div>
                <div className="text-xl font-mono font-bold text-green-400">
                  {briefing.sections.linear_tasks.length}
                </div>
                <div className="text-[10px] font-mono text-text-muted uppercase tracking-wider">
                  Tasks
                </div>
              </div>

              {/* Emails */}
              <div>
                <div className="text-xl font-mono font-bold text-blue-400">
                  {briefing.sections.email_highlights.length}
                </div>
                <div className="text-[10px] font-mono text-text-muted uppercase tracking-wider">
                  Emails
                </div>
              </div>

              {/* Overnight */}
              <div>
                <div className="text-xl font-mono font-bold text-yellow-400">
                  {briefing.sections.overnight_activity.length}
                </div>
                <div className="text-[10px] font-mono text-text-muted uppercase tracking-wider">
                  Overnight
                </div>
              </div>

              {/* Unfinished */}
              <div>
                <div className="text-xl font-mono font-bold text-orange-400">
                  {briefing.sections.unfinished_business.length}
                </div>
                <div className="text-[10px] font-mono text-text-muted uppercase tracking-wider">
                  Unfinished
                </div>
              </div>

              {/* Follow-ups */}
              <div>
                <div className="text-xl font-mono font-bold text-red-400">
                  {briefing.sections.follow_ups_due.length}
                </div>
                <div className="text-[10px] font-mono text-text-muted uppercase tracking-wider">
                  Follow-ups
                </div>
              </div>

              {/* Patterns */}
              <div>
                <div className="text-xl font-mono font-bold text-purple-400">
                  {briefing.sections.pattern_alerts.length}
                </div>
                <div className="text-[10px] font-mono text-text-muted uppercase tracking-wider">
                  Alerts
                </div>
              </div>
            </div>
          </div>

          {/* Expanded Details */}
          {expanded && (
            <div className="border-t border-border/30 p-6 space-y-6">
              {/* Calendar Events */}
              {briefing.sections.calendar.length > 0 && (
                <div>
                  <h3 className="text-[11px] font-mono font-bold text-text-primary uppercase tracking-wider mb-3">
                    📅 Calendar ({briefing.sections.calendar.length})
                  </h3>
                  <div className="space-y-2">
                    {briefing.sections.calendar.map((event, i) => (
                      <div key={i} className="text-xs font-mono text-text-secondary">
                        <span className="text-accent">{formatTime(event.start_time)}</span>
                        {' '}{event.summary}
                        {event.attendees.length > 0 && (
                          <span className="text-text-muted"> with {event.attendees.join(', ')}</span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Linear Tasks */}
              {briefing.sections.linear_tasks.length > 0 && (
                <div>
                  <h3 className="text-[11px] font-mono font-bold text-text-primary uppercase tracking-wider mb-3">
                    ✅ Linear Tasks ({briefing.sections.linear_tasks.length})
                  </h3>
                  <div className="space-y-2">
                    {briefing.sections.linear_tasks.map((task, i) => (
                      <div key={i} className="text-xs font-mono">
                        <div className="flex items-center gap-2">
                          <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                            task.state === 'In Progress' 
                              ? 'bg-blue-500/20 text-blue-400' 
                              : 'bg-border/30 text-text-muted'
                          }`}>
                            {task.state === 'In Progress' ? '🔵' : '⚪'}
                          </span>
                          <span className="text-text-muted">{task.identifier}</span>
                          <span className="text-text-primary flex-1">{task.title}</span>
                          <span className={`text-[9px] px-1.5 py-0.5 rounded ${
                            task.priority === 1 
                              ? 'bg-red-500/20 text-red-400' 
                              : task.priority === 2 
                              ? 'bg-orange-500/20 text-orange-400' 
                              : 'bg-border/20 text-text-muted'
                          }`}>
                            {task.priority_label}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Overnight Activity */}
              {briefing.sections.overnight_activity.length > 0 && (
                <div>
                  <h3 className="text-[11px] font-mono font-bold text-text-primary uppercase tracking-wider mb-3">
                    🌙 Overnight Activity ({briefing.sections.overnight_activity.length}h)
                  </h3>
                  <div className="space-y-2">
                    {briefing.sections.overnight_activity.map((activity, i) => (
                      <div key={i} className="text-xs font-mono">
                        <div className="text-text-primary">
                          <span className="text-yellow-400">{activity.hour.toString().padStart(2, '0')}:00</span>
                          {' — '}{activity.summary}
                        </div>
                        {activity.topics.length > 0 && (
                          <div className="text-[10px] text-text-muted mt-0.5">
                            {activity.topics.join(' · ')}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Email Highlights */}
              {briefing.sections.email_highlights.length > 0 && (
                <div>
                  <h3 className="text-[11px] font-mono font-bold text-text-primary uppercase tracking-wider mb-3">
                    📧 Email Highlights ({briefing.sections.email_highlights.length})
                  </h3>
                  <div className="space-y-2">
                    {briefing.sections.email_highlights.slice(0, 3).map((email, i) => (
                      <div key={i} className="text-xs font-mono">
                        <div className="text-text-primary">{email.from_name}: {email.subject}</div>
                        <div className="text-text-muted text-[10px] line-clamp-1">{email.snippet}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Unfinished Business */}
              {briefing.sections.unfinished_business.length > 0 && (
                <div>
                  <h3 className="text-[11px] font-mono font-bold text-text-primary uppercase tracking-wider mb-3">
                    ⚠️ Unfinished Business ({briefing.sections.unfinished_business.length})
                  </h3>
                  <div className="space-y-2">
                    {briefing.sections.unfinished_business.map((item, i) => (
                      <div key={i} className="text-xs font-mono">
                        <div className="text-text-primary">{item.topic}</div>
                        <div className="text-text-muted text-[10px]">{item.suggested_action}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Follow-ups */}
              {briefing.sections.follow_ups_due.length > 0 && (
                <div>
                  <h3 className="text-[11px] font-mono font-bold text-text-primary uppercase tracking-wider mb-3">
                    🔔 Follow-ups Due ({briefing.sections.follow_ups_due.length})
                  </h3>
                  <div className="space-y-2">
                    {briefing.sections.follow_ups_due.map((item, i) => (
                      <div key={i} className="text-xs font-mono">
                        <div className="text-text-primary line-clamp-2">{item.text}</div>
                        {item.days_overdue !== undefined && item.days_overdue > 0 && (
                          <div className="text-red-400 text-[10px]">
                            Overdue by {item.days_overdue} day{item.days_overdue !== 1 ? 's' : ''}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Pattern Alerts */}
              {briefing.sections.pattern_alerts.length > 0 && (
                <div>
                  <h3 className="text-[11px] font-mono font-bold text-text-primary uppercase tracking-wider mb-3">
                    🔍 Pattern Alerts ({briefing.sections.pattern_alerts.length})
                  </h3>
                  <div className="space-y-2">
                    {briefing.sections.pattern_alerts.map((alert, i) => (
                      <div key={i} className="text-xs font-mono">
                        <div className="text-text-primary">{alert.key}</div>
                        <div className="text-text-muted text-[10px]">{alert.suggested_action}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
