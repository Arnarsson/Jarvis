import { useState, useCallback } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { apiGet, apiPost } from '../api/client.ts'

// --- Types ---

interface Meeting {
  time: string
  title: string
  attendees: string[]
}

interface MorningBriefResponse {
  date: string
  meetings_today: Meeting[]
  unread_emails: number
  pending_actions: number
  recent_captures: number
  summary: string
}

interface QuickCatchUpResponse {
  summary: string
}

// --- Helpers ---

function formatDate(dateStr: string): string {
  try {
    const d = new Date(dateStr + 'T00:00:00')
    return d.toLocaleDateString('en-US', {
      weekday: 'long',
      month: 'long',
      day: 'numeric',
      year: 'numeric',
    })
  } catch {
    return dateStr
  }
}

function formatTime(timeStr: string): string {
  // Accept "09:00", "9:00 AM", etc. — just return as-is if already formatted
  return timeStr
}

// --- Components ---

function StatBox({ label, value, accent }: { label: string; value: number | string; accent?: boolean }) {
  return (
    <div className="border border-border bg-surface rounded px-4 py-3 text-center">
      <div className={`font-mono text-2xl font-bold ${accent ? 'text-accent' : 'text-text-primary'}`}>
        {value}
      </div>
      <div className="font-mono text-[10px] tracking-widest text-text-secondary uppercase mt-1">
        {label}
      </div>
    </div>
  )
}

function MeetingTimeline({ meetings }: { meetings: Meeting[] }) {
  if (meetings.length === 0) {
    return (
      <div className="text-center py-6">
        <p className="font-mono text-sm text-text-muted tracking-wider">NO MEETINGS TODAY</p>
        <p className="text-xs text-text-muted mt-1">Your calendar is clear</p>
      </div>
    )
  }

  return (
    <div className="relative pl-6 space-y-0">
      {/* Timeline line */}
      <div className="absolute left-[9px] top-2 bottom-2 w-px bg-border" />

      {meetings.map((meeting, i) => (
        <div key={i} className="relative pb-5 last:pb-0">
          {/* Timeline dot */}
          <div className="absolute left-[-15px] top-1.5 w-[9px] h-[9px] rounded-full border-2 border-accent bg-bg" />

          {/* Meeting card */}
          <div className="border border-border bg-surface/50 rounded px-4 py-3 hover:border-border-light transition-colors">
            <div className="flex items-baseline justify-between gap-3 mb-1">
              <span className="font-mono text-xs text-accent tracking-wider font-bold">
                {formatTime(meeting.time)}
              </span>
            </div>
            <h4 className="text-sm text-text-primary font-medium">
              {meeting.title}
            </h4>
            {meeting.attendees && meeting.attendees.length > 0 && (
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {meeting.attendees.map((attendee, j) => (
                  <span
                    key={j}
                    className="inline-block px-2 py-0.5 text-[10px] font-mono tracking-wider text-text-secondary border border-border rounded"
                  >
                    {attendee}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

function BriefingCard({ data }: { data: MorningBriefResponse }) {
  return (
    <div className="space-y-6">
      {/* Date header */}
      <div className="border-b border-border pb-3">
        <h2 className="font-mono text-xs tracking-widest text-accent uppercase">
          {formatDate(data.date)}
        </h2>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-3">
        <StatBox label="Unread Emails" value={data.unread_emails} accent />
        <StatBox label="Pending Actions" value={data.pending_actions} />
        <StatBox label="Recent Captures" value={data.recent_captures} />
      </div>

      {/* Summary */}
      {data.summary && (
        <div className="border border-border bg-surface rounded px-5 py-4">
          <h3 className="font-mono text-[11px] tracking-widest text-text-secondary uppercase mb-3">
            SUMMARY
          </h3>
          <p className="text-sm text-text-primary leading-relaxed whitespace-pre-line">
            {data.summary}
          </p>
        </div>
      )}

      {/* Meetings timeline */}
      <div>
        <h3 className="font-mono text-[11px] tracking-widest text-text-secondary uppercase mb-4">
          TODAY&apos;S MEETINGS ({data.meetings_today.length})
        </h3>
        <MeetingTimeline meetings={data.meetings_today} />
      </div>
    </div>
  )
}

// --- Page ---

export function CatchUpPage() {
  const [catchUpHours, setCatchUpHours] = useState(4)
  const [catchUpResult, setCatchUpResult] = useState<string | null>(null)

  // Fetch morning brief on mount
  const briefQuery = useQuery({
    queryKey: ['morning-brief'],
    queryFn: () => apiGet<MorningBriefResponse>('/api/catchup/morning'),
    retry: 1,
    staleTime: 5 * 60 * 1000, // 5 min
  })

  // Quick catch up mutation
  const catchUpMutation = useMutation({
    mutationFn: (hours: number) =>
      apiPost<QuickCatchUpResponse>('/api/catchup/quick', { hours }),
    onSuccess: (data) => {
      setCatchUpResult(data.summary)
    },
    onError: (err) => {
      setCatchUpResult(
        `Error: ${err instanceof Error ? err.message : 'Failed to fetch catch-up'}`
      )
    },
  })

  const handleCatchUp = useCallback(() => {
    setCatchUpResult(null)
    catchUpMutation.mutate(catchUpHours)
  }, [catchUpHours, catchUpMutation])

  const hourOptions = [1, 2, 4, 8, 12, 24]

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      {/* Page header */}
      <div>
        <h3 className="section-title">CATCH ME UP</h3>
        <p className="text-xs text-text-muted font-mono tracking-wider mt-1">
          Morning briefing &amp; quick catch-up
        </p>
      </div>

      {/* Quick Catch Up section */}
      <div className="border border-border bg-surface rounded px-5 py-5 space-y-4">
        <h3 className="font-mono text-[11px] tracking-widest text-text-secondary uppercase">
          QUICK CATCH UP
        </h3>

        <div className="flex flex-wrap items-center gap-3">
          <span className="text-xs text-text-secondary font-mono">LAST</span>
          <div className="flex flex-wrap gap-1.5">
            {hourOptions.map((h) => (
              <button
                key={h}
                onClick={() => setCatchUpHours(h)}
                className={`px-3 py-1.5 font-mono text-[11px] tracking-wider border rounded transition-colors ${
                  catchUpHours === h
                    ? 'border-accent text-accent bg-accent/10'
                    : 'border-border text-text-secondary hover:border-accent hover:text-accent'
                }`}
              >
                {h}H
              </button>
            ))}
          </div>
          <button
            onClick={handleCatchUp}
            disabled={catchUpMutation.isPending}
            className="px-5 py-2 bg-accent/10 border border-accent/40 text-accent font-mono text-xs tracking-wider uppercase hover:bg-accent/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {catchUpMutation.isPending ? 'LOADING...' : 'CATCH ME UP'}
          </button>
        </div>

        {/* Result */}
        {catchUpResult && (
          <div className="border border-border rounded px-4 py-3 mt-3 bg-bg">
            <p className="text-sm text-text-primary leading-relaxed whitespace-pre-line">
              {catchUpResult}
            </p>
          </div>
        )}
      </div>

      {/* Morning Brief section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-mono text-[11px] tracking-widest text-text-secondary uppercase">
            MORNING BRIEF
          </h3>
          <button
            onClick={() => briefQuery.refetch()}
            disabled={briefQuery.isFetching}
            className="px-3 py-1 border border-border text-text-secondary font-mono text-[10px] tracking-wider uppercase hover:border-accent hover:text-accent transition-colors disabled:opacity-50"
          >
            {briefQuery.isFetching ? '...' : 'REFRESH'}
          </button>
        </div>

        {/* Loading state */}
        {briefQuery.isLoading && (
          <div className="border border-border bg-surface rounded px-5 py-10 text-center">
            <p className="font-mono text-sm text-text-muted animate-pulse tracking-wider">
              LOADING MORNING BRIEF...
            </p>
          </div>
        )}

        {/* Error state */}
        {briefQuery.isError && (
          <div className="border border-accent/30 bg-accent/5 rounded px-5 py-4">
            <p className="font-mono text-xs text-accent tracking-wider mb-2">
              FAILED TO LOAD BRIEF
            </p>
            <p className="text-sm text-text-secondary">
              {briefQuery.error instanceof Error
                ? briefQuery.error.message
                : 'Could not reach the server'}
            </p>
          </div>
        )}

        {/* Success state */}
        {briefQuery.data && <BriefingCard data={briefQuery.data} />}
      </div>
    </div>
  )
}
