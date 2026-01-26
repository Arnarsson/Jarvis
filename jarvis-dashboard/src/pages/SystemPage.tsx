import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost } from '../api/client.ts'
import { LoadingSkeleton } from '../components/ui/LoadingSkeleton.tsx'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface HealthResponse {
  status: string
  version: string
  database: string
  storage: string
}

interface SearchHealth {
  status: string
  collection_exists?: boolean
  document_count?: number
  error?: string
}

interface AuthStatus {
  authenticated: boolean
  needs_credentials?: boolean
}

interface EmailAuthStatus extends AuthStatus {
  email?: string
}

interface EmailSyncStatus {
  last_sync: string | null
  history_id: string | null
  message_count: number
}

interface TimelineResponse {
  captures: unknown[]
  total: number
  has_more: boolean
}

interface PatternListResponse {
  patterns: unknown[]
  total: number
}

interface SyncResponse {
  status: string
  created?: number
  updated?: number
  deleted?: number
  job_id?: string
}

// ---------------------------------------------------------------------------
// Fetch helpers (with graceful error handling)
// ---------------------------------------------------------------------------

async function fetchHealth(): Promise<HealthResponse | null> {
  try {
    return await apiGet<HealthResponse>('/health/')
  } catch {
    return null
  }
}

async function fetchSearchHealth(): Promise<SearchHealth> {
  try {
    return await apiGet<SearchHealth>('/api/search/health')
  } catch {
    return { status: 'unavailable' }
  }
}

async function fetchCalendarAuth(): Promise<AuthStatus> {
  try {
    return await apiGet<AuthStatus>('/api/calendar/auth/status')
  } catch {
    return { authenticated: false }
  }
}

async function fetchEmailAuth(): Promise<EmailAuthStatus> {
  try {
    return await apiGet<EmailAuthStatus>('/api/email/auth/status')
  } catch {
    return { authenticated: false }
  }
}

async function fetchEmailSyncStatus(): Promise<EmailSyncStatus | null> {
  try {
    return await apiGet<EmailSyncStatus>('/api/email/sync/status')
  } catch {
    return null
  }
}

async function fetchTimeline(): Promise<TimelineResponse> {
  try {
    return await apiGet<TimelineResponse>('/api/timeline/?limit=1')
  } catch {
    return { captures: [], total: 0, has_more: false }
  }
}

async function fetchPatterns(): Promise<PatternListResponse> {
  try {
    return await apiGet<PatternListResponse>('/api/workflow/patterns?active_only=false')
  } catch {
    return { patterns: [], total: 0 }
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

type ServiceStatus = 'operational' | 'degraded' | 'down' | 'disconnected'

function statusColor(s: ServiceStatus): string {
  switch (s) {
    case 'operational':
      return 'bg-success'
    case 'degraded':
      return 'bg-warning'
    case 'down':
      return 'bg-accent'
    case 'disconnected':
      return 'bg-text-muted'
  }
}

function statusTextColor(s: ServiceStatus): string {
  switch (s) {
    case 'operational':
      return 'text-success'
    case 'degraded':
      return 'text-warning'
    case 'down':
      return 'text-accent'
    case 'disconnected':
      return 'text-text-muted'
  }
}

function statusLabel(s: ServiceStatus): string {
  switch (s) {
    case 'operational':
      return 'Healthy'
    case 'degraded':
      return 'Degraded'
    case 'down':
      return 'Down'
    case 'disconnected':
      return 'Disconnected'
  }
}

function deriveServiceStatus(value: string | undefined | null): ServiceStatus {
  if (!value) return 'disconnected'
  const v = value.toLowerCase()
  if (v === 'healthy' || v === 'ok' || v === 'connected') return 'operational'
  if (v === 'degraded' || v === 'read-only') return 'degraded'
  if (v === 'unhealthy' || v === 'down' || v === 'unavailable' || v === 'not-configured')
    return 'down'
  return 'disconnected'
}

function formatNumber(n: number): string {
  return n.toLocaleString()
}

function formatSyncTime(iso: string | null | undefined): string {
  if (!iso) return 'Never'
  try {
    const d = new Date(iso)
    const now = new Date()
    const diffMs = now.getTime() - d.getTime()
    const diffMin = Math.floor(diffMs / 60_000)
    if (diffMin < 1) return 'Just now'
    if (diffMin < 60) return `${diffMin}m ago`
    const diffHr = Math.floor(diffMin / 60)
    if (diffHr < 24) return `${diffHr}h ago`
    const diffDay = Math.floor(diffHr / 24)
    return `${diffDay}d ago`
  } catch {
    return 'Unknown'
  }
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatusDotPulsing({ status }: { status: ServiceStatus }) {
  return (
    <span
      className={`inline-block h-2.5 w-2.5 rounded-full ${statusColor(status)} ${
        status === 'operational' ? 'animate-pulse-dot' : ''
      }`}
    />
  )
}

function ServiceCard({
  name,
  status,
  detail,
}: {
  name: string
  status: ServiceStatus
  detail?: string
}) {
  return (
    <div className="border border-border p-4">
      <p className="font-mono-header text-[11px] text-text-secondary tracking-wider mb-3">
        {name}
      </p>
      <div className="flex items-center gap-2">
        <StatusDotPulsing status={status} />
        <span className={`text-sm font-medium ${statusTextColor(status)}`}>
          {statusLabel(status)}
        </span>
      </div>
      {detail && (
        <p className="mt-2 text-xs text-text-secondary font-mono">{detail}</p>
      )}
    </div>
  )
}

function SyncRow({
  label,
  lastSync,
  isSyncing,
  onSync,
}: {
  label: string
  lastSync: string | null | undefined
  isSyncing: boolean
  onSync: () => void
}) {
  return (
    <div className="flex items-center justify-between border border-border p-4">
      <div>
        <p className="font-mono-header text-[11px] text-text-secondary tracking-wider mb-1">
          {label}
        </p>
        <p className="text-sm text-text-primary">
          Last sync: <span className="font-mono text-text-secondary">{formatSyncTime(lastSync)}</span>
        </p>
      </div>
      <button
        onClick={onSync}
        disabled={isSyncing}
        className="font-mono text-[11px] tracking-wider border border-border px-4 py-2 text-text-primary hover:border-accent hover:text-accent transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {isSyncing ? (
          <span className="flex items-center gap-2">
            <svg
              className="animate-spin h-3 w-3"
              viewBox="0 0 24 24"
              fill="none"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
              />
            </svg>
            SYNCING
          </span>
        ) : (
          'SYNC NOW'
        )}
      </button>
    </div>
  )
}

function DataMetric({ value, label }: { value: string | number; label: string }) {
  return (
    <div className="border border-border p-5 text-center">
      <p className="text-3xl sm:text-4xl font-bold tracking-tight font-mono text-text-primary mb-2">
        {typeof value === 'number' ? formatNumber(value) : value}
      </p>
      <p className="font-mono-header text-[11px] text-text-secondary tracking-wider">
        {label}
      </p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function SystemPage() {
  const queryClient = useQueryClient()

  // --- Data fetching ---

  const healthQuery = useQuery({
    queryKey: ['system', 'health'],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
  })

  const searchQuery = useQuery({
    queryKey: ['system', 'search-health'],
    queryFn: fetchSearchHealth,
    refetchInterval: 60_000,
  })

  const calendarAuthQuery = useQuery({
    queryKey: ['system', 'calendar-auth'],
    queryFn: fetchCalendarAuth,
    staleTime: 60_000,
  })

  const emailAuthQuery = useQuery({
    queryKey: ['system', 'email-auth'],
    queryFn: fetchEmailAuth,
    staleTime: 60_000,
  })

  const emailSyncQuery = useQuery({
    queryKey: ['system', 'email-sync-status'],
    queryFn: fetchEmailSyncStatus,
    staleTime: 30_000,
  })

  const timelineQuery = useQuery({
    queryKey: ['system', 'timeline-total'],
    queryFn: fetchTimeline,
    staleTime: 120_000,
  })

  const patternsQuery = useQuery({
    queryKey: ['system', 'patterns'],
    queryFn: fetchPatterns,
    staleTime: 120_000,
  })

  // --- Mutations ---

  const calendarSync = useMutation({
    mutationFn: () => apiPost<SyncResponse>('/api/calendar/sync'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['system', 'calendar-auth'] })
      queryClient.invalidateQueries({ queryKey: ['calendar'] })
    },
  })

  const emailSync = useMutation({
    mutationFn: () => apiPost<SyncResponse>('/api/email/sync'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['system', 'email-sync-status'] })
      queryClient.invalidateQueries({ queryKey: ['system', 'email-auth'] })
      queryClient.invalidateQueries({ queryKey: ['email'] })
    },
  })

  // --- Derived state ---

  const health = healthQuery.data
  const search = searchQuery.data
  const calAuth = calendarAuthQuery.data
  const emailAuth = emailAuthQuery.data
  const emailSyncStatus = emailSyncQuery.data

  const isLoading =
    healthQuery.isLoading &&
    searchQuery.isLoading &&
    calendarAuthQuery.isLoading &&
    emailAuthQuery.isLoading

  // Overall status
  const serverStatus: ServiceStatus = health
    ? deriveServiceStatus(health.status)
    : healthQuery.isLoading
      ? 'disconnected'
      : 'down'

  const dbStatus: ServiceStatus = health
    ? deriveServiceStatus(health.database)
    : 'disconnected'

  const searchStatus: ServiceStatus = search
    ? deriveServiceStatus(search.status)
    : 'disconnected'

  // Qdrant is healthy if search is healthy (search depends on qdrant)
  const qdrantStatus: ServiceStatus =
    search?.status === 'healthy'
      ? 'operational'
      : search?.status === 'degraded'
        ? 'degraded'
        : search?.error
          ? 'down'
          : 'disconnected'

  const calendarStatus: ServiceStatus = calAuth?.authenticated
    ? 'operational'
    : 'disconnected'

  const emailStatus: ServiceStatus = emailAuth?.authenticated
    ? 'operational'
    : 'disconnected'

  // Overall banner status
  const overallStatus: ServiceStatus =
    serverStatus === 'down'
      ? 'down'
      : [dbStatus, searchStatus, qdrantStatus].some((s) => s === 'down')
        ? 'degraded'
        : [dbStatus, searchStatus, qdrantStatus].some((s) => s === 'degraded')
          ? 'degraded'
          : serverStatus

  const overallLabel =
    overallStatus === 'operational'
      ? 'OPERATIONAL'
      : overallStatus === 'degraded'
        ? 'DEGRADED'
        : 'DOWN'

  // Data overview numbers
  const documentCount = search?.document_count ?? 0
  const captureCount = timelineQuery.data?.total ?? 0
  const patternCount = patternsQuery.data?.total ?? 0
  const emailMessageCount = emailSyncStatus?.message_count ?? 0

  // --- Loading state ---

  if (isLoading) {
    return (
      <div>
        <h2 className="section-title">System</h2>
        <LoadingSkeleton lines={6} />
      </div>
    )
  }

  // --- Render ---

  return (
    <div>
      {/* Page header */}
      <h2 className="section-title">System</h2>

      {/* System Status Banner */}
      <div className="border border-border py-4 px-6 mb-8 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <StatusDotPulsing status={overallStatus} />
          <span
            className={`text-xl font-bold font-mono tracking-wider ${statusTextColor(overallStatus)}`}
          >
            {overallLabel}
          </span>
        </div>
        {health?.version && (
          <span className="font-mono text-xs text-text-secondary">
            v{health.version}
          </span>
        )}
      </div>

      {/* Service Health Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-10">
        <ServiceCard
          name="SERVER"
          status={serverStatus}
          detail={health?.version ? `v${health.version}` : undefined}
        />
        <ServiceCard
          name="DATABASE"
          status={dbStatus}
          detail={health?.database !== 'unknown' ? health?.database : undefined}
        />
        <ServiceCard
          name="REDIS"
          status={
            // Redis status is not exposed by current health endpoint;
            // infer from server being up (Redis is required for ARQ)
            serverStatus === 'operational' ? 'operational' : 'disconnected'
          }
        />
        <ServiceCard
          name="QDRANT (VECTOR DB)"
          status={qdrantStatus}
          detail={
            search?.collection_exists
              ? 'Collection active'
              : search?.error
                ? search.error.slice(0, 60)
                : undefined
          }
        />
        <ServiceCard
          name="SEARCH ENGINE"
          status={searchStatus}
          detail={
            search?.document_count !== undefined
              ? `${formatNumber(search.document_count)} documents`
              : undefined
          }
        />
        <ServiceCard
          name="CALENDAR"
          status={calendarStatus}
          detail={calAuth?.authenticated ? 'Authenticated' : 'Not connected'}
        />
        <ServiceCard
          name="EMAIL"
          status={emailStatus}
          detail={
            emailAuth?.authenticated
              ? emailAuth.email ?? 'Authenticated'
              : 'Not connected'
          }
        />
      </div>

      {/* Data Sync Section */}
      <h3 className="section-title">Data Sync</h3>
      <div className="space-y-3 mb-10">
        <SyncRow
          label="CALENDAR"
          lastSync={null}
          isSyncing={calendarSync.isPending}
          onSync={() => calendarSync.mutate()}
        />
        <SyncRow
          label="EMAIL"
          lastSync={emailSyncStatus?.last_sync}
          isSyncing={emailSync.isPending}
          onSync={() => emailSync.mutate()}
        />
      </div>

      {/* Data Overview Section */}
      <h3 className="section-title">Data Overview</h3>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <DataMetric value={documentCount} label="DOCUMENTS INDEXED" />
        <DataMetric value={captureCount} label="CAPTURES" />
        <DataMetric value={patternCount} label="WORKFLOW PATTERNS" />
        <DataMetric value={emailMessageCount} label="EMAIL MESSAGES" />
      </div>
    </div>
  )
}
