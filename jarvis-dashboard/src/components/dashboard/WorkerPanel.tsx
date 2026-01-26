import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'

/* ───────────────── Types ───────────────── */

interface WorkerSession {
  sessionKey: string
  label?: string
  status: 'running' | 'completed' | 'error' | 'idle'
  task?: string
  startedAt: string
  completedAt?: string
  model?: string
  agentId?: string
}

interface EurekaStatus {
  online: boolean
  model: string
  activeWorkers: WorkerSession[]
  recentWorkers: WorkerSession[]
  uptime?: string
}

/* ───────────────── API ───────────────── */

async function fetchEurekaStatus(): Promise<EurekaStatus> {
  // Try Clawdbot gateway API for session/worker info
  try {
    const resp = await fetch('/api/eureka/status')
    if (resp.ok) return resp.json()
  } catch { /* fallback below */ }

  // Fallback: return a placeholder that the backend can populate
  return {
    online: true,
    model: 'claude-opus-4-5',
    activeWorkers: [],
    recentWorkers: [],
  }
}

/* ───────────────── Helpers ───────────────── */

function timeAgo(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime()
  const sec = Math.floor(ms / 1000)
  if (sec < 60) return `${sec}s ago`
  const min = Math.floor(sec / 60)
  if (min < 60) return `${min}m ago`
  const hr = Math.floor(min / 60)
  return `${hr}h ago`
}

function statusDot(status: WorkerSession['status']): string {
  switch (status) {
    case 'running': return 'bg-blue-400 animate-pulse'
    case 'completed': return 'bg-success'
    case 'error': return 'bg-accent'
    case 'idle': return 'bg-text-muted'
  }
}

function statusLabel(status: WorkerSession['status']): string {
  switch (status) {
    case 'running': return 'ACTIVE'
    case 'completed': return 'DONE'
    case 'error': return 'ERROR'
    case 'idle': return 'IDLE'
  }
}

/* ───────────────── Live pulse animation ───────────────── */

function PulseRing({ active }: { active: boolean }) {
  if (!active) return null
  return (
    <span className="relative flex h-3 w-3">
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
      <span className="relative inline-flex rounded-full h-3 w-3 bg-blue-500" />
    </span>
  )
}

/* ───────────────── Worker Row ───────────────── */

function WorkerRow({ worker }: { worker: WorkerSession }) {
  const label = worker.label || worker.sessionKey.slice(0, 8)
  const taskPreview = worker.task
    ? worker.task.length > 80
      ? worker.task.slice(0, 77) + '...'
      : worker.task
    : 'No task description'

  return (
    <div className="border border-border p-3 space-y-2 hover:border-border-light transition-colors">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`inline-block h-2 w-2 rounded-full ${statusDot(worker.status)}`} />
          <span className="font-mono text-xs font-bold text-text-primary tracking-wider">
            {label.toUpperCase()}
          </span>
        </div>
        <span className="font-mono text-[10px] text-text-muted tracking-wider">
          {statusLabel(worker.status)}
        </span>
      </div>
      <p className="text-xs text-text-secondary leading-relaxed">
        {taskPreview}
      </p>
      <div className="flex items-center justify-between">
        <span className="font-mono text-[10px] text-text-muted">
          {worker.model || 'opus'}
        </span>
        <span className="font-mono text-[10px] text-text-muted">
          {timeAgo(worker.startedAt)}
        </span>
      </div>
    </div>
  )
}

/* ───────────────── Simulated Workers (demo data from SSE/polling) ───────────────── */

// This connects to Clawdbot's session events via SSE or polling
function useWorkerStream() {
  const [workers, setWorkers] = useState<WorkerSession[]>([])
  const eventSourceRef = useRef<EventSource | null>(null)

  useEffect(() => {
    // Try SSE endpoint first
    try {
      const es = new EventSource('/api/eureka/workers/stream')
      eventSourceRef.current = es

      es.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as WorkerSession[]
          setWorkers(data)
        } catch { /* ignore parse errors */ }
      }

      es.onerror = () => {
        es.close()
        eventSourceRef.current = null
      }
    } catch {
      // SSE not available, will use polling fallback
    }

    return () => {
      eventSourceRef.current?.close()
    }
  }, [])

  return workers
}

/* ───────────────── Main Component ───────────────── */

export function WorkerPanel() {
  const { data: eurekaStatus } = useQuery({
    queryKey: ['eureka', 'status'],
    queryFn: fetchEurekaStatus,
    refetchInterval: 10_000,
    staleTime: 5_000,
  })

  const streamWorkers = useWorkerStream()

  // Merge polled + streamed workers, prefer streamed
  const activeWorkers = streamWorkers.length > 0
    ? streamWorkers.filter(w => w.status === 'running')
    : (eurekaStatus?.activeWorkers ?? [])

  const recentWorkers = streamWorkers.length > 0
    ? streamWorkers.filter(w => w.status !== 'running').slice(0, 5)
    : (eurekaStatus?.recentWorkers ?? []).slice(0, 5)

  const totalActive = activeWorkers.length
  const isOnline = eurekaStatus?.online ?? false

  return (
    <div className="space-y-4">
      {/* Eureka Status Header */}
      <div className="border border-border p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <PulseRing active={isOnline} />
            {!isOnline && (
              <span className="inline-block h-3 w-3 rounded-full bg-text-muted" />
            )}
            <div>
              <h4 className="font-mono text-xs font-bold text-text-primary tracking-widest">
                EUREKA
              </h4>
              <p className="font-mono text-[10px] text-text-muted tracking-wider mt-0.5">
                {eurekaStatus?.model || 'claude-opus-4-5'}
              </p>
            </div>
          </div>
          <div className="text-right">
            <span className={`font-mono text-[11px] tracking-wider font-bold ${
              isOnline ? 'text-success' : 'text-text-muted'
            }`}>
              {isOnline ? 'ONLINE' : 'OFFLINE'}
            </span>
          </div>
        </div>

        {/* Worker count bar */}
        <div className="flex items-center gap-3">
          <div className="flex-1 h-1.5 bg-surface rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 rounded-full transition-all duration-500"
              style={{ width: `${Math.min(totalActive / 8 * 100, 100)}%` }}
            />
          </div>
          <span className="font-mono text-[11px] text-text-secondary shrink-0">
            {totalActive}/8 WORKERS
          </span>
        </div>
      </div>

      {/* Active Workers */}
      {activeWorkers.length > 0 && (
        <div>
          <h5 className="font-mono-header text-[11px] text-text-secondary tracking-wider mb-2">
            ACTIVE WORKERS
          </h5>
          <div className="space-y-2">
            {activeWorkers.map((w) => (
              <WorkerRow key={w.sessionKey} worker={w} />
            ))}
          </div>
        </div>
      )}

      {/* Recent Workers */}
      {recentWorkers.length > 0 && (
        <div>
          <h5 className="font-mono-header text-[11px] text-text-secondary tracking-wider mb-2">
            RECENT
          </h5>
          <div className="space-y-2">
            {recentWorkers.map((w) => (
              <WorkerRow key={w.sessionKey} worker={w} />
            ))}
          </div>
        </div>
      )}

      {/* Empty state */}
      {activeWorkers.length === 0 && recentWorkers.length === 0 && (
        <div className="border border-border border-dashed p-6 text-center">
          <p className="font-mono text-xs text-text-muted tracking-wider">
            NO ACTIVE WORKERS
          </p>
          <p className="text-[11px] text-text-muted mt-1">
            Sub-agents appear here when Eureka spawns them
          </p>
        </div>
      )}
    </div>
  )
}
