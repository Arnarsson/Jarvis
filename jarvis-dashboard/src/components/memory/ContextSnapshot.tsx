import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../../api/client.ts'

/* ───────────────── Types ───────────────── */

interface TimelineCapture {
  id: string
  timestamp: string
  filepath: string
  width: number
  height: number
  has_ocr: boolean
  text_preview?: string
  app?: string
  window_title?: string
}

interface TimelineResponse {
  captures: TimelineCapture[]
}

interface AppGroup {
  app: string
  lastSeen: Date
  captures: TimelineCapture[]
  timeAgo: string
}

/* ───────────────── Helpers ───────────────── */

function captureImageUrl(filepath: string): string {
  const stripped = filepath.replace(/^\/data\/captures\//, '')
  return `/captures/${stripped}`
}

function timeAgo(date: Date): string {
  const now = Date.now()
  const diffMs = now - date.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  const diffHr = Math.floor(diffMs / 3600000)
  const diffDay = Math.floor(diffMs / 86400000)

  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  if (diffHr < 24) return `${diffHr}h ago`
  if (diffDay === 1) return 'yesterday'
  if (diffDay < 7) return `${diffDay}d ago`
  return `${diffDay}d ago`
}

function groupByApp(captures: TimelineCapture[]): AppGroup[] {
  const groups = new Map<string, TimelineCapture[]>()

  for (const cap of captures) {
    const key = cap.app || cap.window_title || 'Unknown'
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key)!.push(cap)
  }

  return Array.from(groups.entries())
    .map(([app, caps]) => {
      const sorted = caps.sort(
        (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
      )
      const lastSeen = new Date(sorted[0].timestamp)
      return {
        app,
        lastSeen,
        captures: sorted.slice(0, 3), // keep latest 3 per app
        timeAgo: timeAgo(lastSeen),
      }
    })
    .sort((a, b) => b.lastSeen.getTime() - a.lastSeen.getTime())
}

/* ───────────────── Component ───────────────── */

export function ContextSnapshot() {
  const { data, isLoading } = useQuery({
    queryKey: ['timeline', 'context-snapshot'],
    queryFn: async () => {
      try {
        return await apiGet<TimelineResponse>('/api/timeline/')
      } catch {
        return { captures: [] }
      }
    },
    staleTime: 30_000,
  })

  const appGroups = useMemo(() => {
    if (!data?.captures?.length) return []
    return groupByApp(data.captures).slice(0, 5) // top 5 apps
  }, [data])

  // Latest 3 captures with OCR
  const latestWithOcr = useMemo(() => {
    if (!data?.captures?.length) return []
    return data.captures
      .filter((c) => c.has_ocr && c.text_preview)
      .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
      .slice(0, 3)
  }, [data])

  if (isLoading) {
    return (
      <section className="mb-10">
        <h2 className="text-xs font-mono tracking-widest text-text-muted uppercase mb-4">
          WHERE YOU LEFT OFF
        </h2>
        <div className="border border-border/30 rounded-lg p-6">
          <div className="animate-pulse space-y-3">
            <div className="h-3 w-48 bg-border/50 rounded" />
            <div className="h-3 w-64 bg-border/50 rounded" />
            <div className="h-3 w-40 bg-border/50 rounded" />
          </div>
        </div>
      </section>
    )
  }

  if (appGroups.length === 0 && latestWithOcr.length === 0) return null

  return (
    <section className="mb-10">
      <h2 className="text-xs font-mono tracking-widest text-text-muted uppercase mb-4">
        WHERE YOU LEFT OFF
      </h2>

      {/* Last seen working on summary */}
      {appGroups.length > 0 && (
        <div className="border border-border/40 rounded-lg bg-surface/30 p-4 mb-4">
          <p className="text-[13px] text-text-secondary mb-3">
            <span className="text-text-muted">Last seen working on: </span>
            {appGroups.slice(0, 3).map((g, i) => (
              <span key={g.app}>
                {i > 0 && ', '}
                <span className="text-text-primary font-medium">{g.app}</span>
                <span className="text-text-muted"> ({g.timeAgo})</span>
              </span>
            ))}
          </p>
        </div>
      )}

      {/* Latest captures with OCR */}
      {latestWithOcr.length > 0 && (
        <div className="space-y-3">
          {latestWithOcr.map((cap) => (
            <div
              key={cap.id}
              className="border border-border/30 rounded-lg overflow-hidden bg-surface/20 flex"
            >
              {/* Thumbnail */}
              <div className="w-32 sm:w-40 shrink-0 bg-neutral-900">
                <img
                  src={captureImageUrl(cap.filepath)}
                  alt={cap.app || 'Screen capture'}
                  loading="lazy"
                  className="w-full h-full object-cover"
                />
              </div>

              {/* Content */}
              <div className="flex-1 p-3 min-w-0">
                <div className="flex items-center justify-between mb-1.5">
                  <p className="text-[12px] font-mono text-text-primary font-medium truncate">
                    {cap.app || cap.window_title || 'Screen Capture'}
                  </p>
                  <span className="text-[10px] font-mono text-text-muted shrink-0 ml-2">
                    {timeAgo(new Date(cap.timestamp))}
                  </span>
                </div>
                {cap.text_preview && (
                  <p className="text-[11px] text-text-secondary leading-relaxed line-clamp-3">
                    {cap.text_preview.slice(0, 200)}
                    {cap.text_preview.length > 200 ? '…' : ''}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
