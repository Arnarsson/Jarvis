import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { LoadingSkeleton } from '../ui/LoadingSkeleton.tsx'

/* ───────────────── Types ───────────────── */

interface Touchpoint {
  type: string
  timestamp: string
  summary: string
  snippet?: string
  url?: string
}

interface OpenLoop {
  type: string
  description: string
  owner: string
  due_date?: string
  status: string
}

interface AttendeeContext {
  name: string
  email: string
  touchpoints: Touchpoint[]
  open_loops: OpenLoop[]
}

interface TalkingPoint {
  point: string
  reason: string
  confidence: number
}

interface MeetingBriefData {
  event_id: string
  meeting_title: string
  meeting_time: string
  meeting_duration_minutes: number
  attendees: AttendeeContext[]
  talking_points: TalkingPoint[]
  recent_files: any[]
  preparation_time: string
  can_draft_email: boolean
  can_open_last_doc: boolean
  can_create_tasks: boolean
}

/* ───────────────── API ───────────────── */

async function fetchMeetingBrief(eventId: string): Promise<MeetingBriefData> {
  const res = await fetch(`/api/v2/meeting-brief/${eventId}`)
  if (!res.ok) throw new Error(`Failed to fetch meeting brief: ${res.statusText}`)
  return res.json()
}

/* ───────────────── Helpers ───────────────── */

function formatTime(iso: string): string {
  const date = new Date(iso)
  return date.toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatDate(iso: string): string {
  const date = new Date(iso)
  return date.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  })
}

function getConfidenceBadge(confidence: number): string {
  if (confidence >= 0.8) return '🟢 High'
  if (confidence >= 0.6) return '🟡 Medium'
  return '🔴 Low'
}

function formatRelativeTime(iso: string): string {
  const date = new Date(iso)
  const now = new Date()
  const diffHours = Math.round((now.getTime() - date.getTime()) / (1000 * 60 * 60))
  
  if (diffHours < 1) return 'just now'
  if (diffHours < 24) return `${diffHours}h ago`
  const diffDays = Math.floor(diffHours / 24)
  if (diffDays < 7) return `${diffDays}d ago`
  return formatDate(iso)
}

/* ───────────────── Components ───────────────── */

interface MeetingBriefModalProps {
  eventId: string
  onClose: () => void
}

export function MeetingBriefModal({ eventId, onClose }: MeetingBriefModalProps) {
  const { data: brief, isLoading, error } = useQuery({
    queryKey: ['meeting-brief', eventId],
    queryFn: () => fetchMeetingBrief(eventId),
    staleTime: 2 * 60_000, // 2 minutes
    retry: 2,
  })

  if (error) {
    return (
      <div className="modal-overlay" onClick={onClose}>
        <div className="modal-content meeting-brief" onClick={(e) => e.stopPropagation()}>
          <div className="modal-header">
            <h2>⚠️ Error Loading Brief</h2>
            <button onClick={onClose} className="close-btn">✕</button>
          </div>
          <p className="error-message">
            {error instanceof Error ? error.message : 'Failed to load meeting brief'}
          </p>
        </div>
      </div>
    )
  }

  if (isLoading || !brief) {
    return (
      <div className="modal-overlay" onClick={onClose}>
        <div className="modal-content meeting-brief" onClick={(e) => e.stopPropagation()}>
          <div className="modal-header">
            <h2>🔍 Loading Brief...</h2>
            <button onClick={onClose} className="close-btn">✕</button>
          </div>
          <LoadingSkeleton lines={10} />
        </div>
      </div>
    )
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content meeting-brief" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="modal-header">
          <div>
            <h2>📋 Meeting Brief</h2>
            <p className="meeting-title">{brief.meeting_title}</p>
            <p className="meeting-time">
              {formatDate(brief.meeting_time)} · {formatTime(brief.meeting_time)} · {brief.meeting_duration_minutes}min
            </p>
          </div>
          <button onClick={onClose} className="close-btn">✕</button>
        </div>

        {/* Quick Actions */}
        <div className="quick-actions">
          {brief.can_draft_email && (
            <button className="action-btn" disabled>
              ✉️ Draft Email
            </button>
          )}
          {brief.can_open_last_doc && (
            <button className="action-btn">
              📄 Open Last Doc
            </button>
          )}
          {brief.can_create_tasks && (
            <button className="action-btn" disabled>
              ✅ Create Tasks
            </button>
          )}
        </div>

        {/* Talking Points */}
        {brief.talking_points.length > 0 && (
          <section className="brief-section">
            <h3>💡 Suggested Talking Points</h3>
            <div className="talking-points">
              {brief.talking_points.map((point, idx) => (
                <div key={idx} className="talking-point">
                  <div className="point-header">
                    <span className="confidence-badge">{getConfidenceBadge(point.confidence)}</span>
                  </div>
                  <p className="point-text">{point.point}</p>
                  <p className="point-reason">{point.reason}</p>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Attendee Context */}
        {brief.attendees.length > 0 && (
          <section className="brief-section">
            <h3>👥 Attendee Context ({brief.attendees.length})</h3>
            {brief.attendees.map((attendee, idx) => (
              <AttendeeCard key={idx} attendee={attendee} />
            ))}
          </section>
        )}

        {/* Footer */}
        <div className="brief-footer">
          <p className="prep-time">
            Brief generated at {formatTime(brief.preparation_time)}
          </p>
        </div>
      </div>
    </div>
  )
}

function AttendeeCard({ attendee }: { attendee: AttendeeContext }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="attendee-card">
      <div className="attendee-header" onClick={() => setExpanded(!expanded)}>
        <div>
          <h4>{attendee.name}</h4>
          <p className="attendee-email">{attendee.email}</p>
        </div>
        <div className="attendee-stats">
          <span className="stat-badge">{attendee.touchpoints.length} touchpoints</span>
          <span className="stat-badge">{attendee.open_loops.length} open loops</span>
          <button className="expand-btn">{expanded ? '▼' : '▶'}</button>
        </div>
      </div>

      {expanded && (
        <div className="attendee-details">
          {/* Recent Touchpoints */}
          {attendee.touchpoints.length > 0 && (
            <div className="touchpoints">
              <h5>Recent Touchpoints</h5>
              {attendee.touchpoints.map((touch, idx) => (
                <div key={idx} className="touchpoint">
                  <div className="touchpoint-header">
                    <span className="touchpoint-type">{touch.type}</span>
                    <span className="touchpoint-time">{formatRelativeTime(touch.timestamp)}</span>
                  </div>
                  <p className="touchpoint-summary">{touch.summary}</p>
                  {touch.snippet && (
                    <p className="touchpoint-snippet">{touch.snippet}</p>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Open Loops */}
          {attendee.open_loops.length > 0 && (
            <div className="open-loops">
              <h5>Open Loops</h5>
              {attendee.open_loops.map((loop, idx) => (
                <div key={idx} className={`open-loop ${loop.status}`}>
                  <div className="loop-header">
                    <span className="loop-type">{loop.type}</span>
                    <span className="loop-owner">{loop.owner}</span>
                    {loop.status === 'overdue' && <span className="overdue-badge">⚠️ OVERDUE</span>}
                  </div>
                  <p className="loop-description">{loop.description}</p>
                  {loop.due_date && (
                    <p className="loop-due">Due: {formatDate(loop.due_date)}</p>
                  )}
                </div>
              ))}
            </div>
          )}

          {attendee.touchpoints.length === 0 && attendee.open_loops.length === 0 && (
            <p className="no-context">No recent context available</p>
          )}
        </div>
      )}
    </div>
  )
}

/* ───────────────── Quick Brief Button ───────────────── */

interface MeetingBriefButtonProps {
  eventId: string
  className?: string
}

export function MeetingBriefButton({ eventId, className = '' }: MeetingBriefButtonProps) {
  const [showBrief, setShowBrief] = useState(false)

  return (
    <>
      <button
        className={`meeting-brief-btn ${className}`}
        onClick={(e) => {
          e.stopPropagation()
          setShowBrief(true)
        }}
        title="Prepare for this meeting"
      >
        📋 Prep
      </button>

      {showBrief && (
        <MeetingBriefModal
          eventId={eventId}
          onClose={() => setShowBrief(false)}
        />
      )}
    </>
  )
}
