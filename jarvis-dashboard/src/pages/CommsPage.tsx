import { useState, useMemo, useEffect, useRef, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost } from '../api/client.ts'
import { LoadingSkeleton } from '../components/ui/LoadingSkeleton.tsx'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AuthStatusResponse {
  authenticated: boolean
  needs_credentials: boolean
}

interface EmailMessageResponse {
  id: string
  gmail_message_id: string
  thread_id: string
  subject: string | null
  from_address: string | null
  from_name: string | null
  snippet: string | null
  date_sent: string
  is_unread: boolean
  is_important: boolean
  category: string | null
}

interface EmailMessageDetailResponse extends EmailMessageResponse {
  to_addresses: string | null
  cc_addresses: string | null
  body_text: string | null
  labels_json: string | null
}

interface EmailListResponse {
  messages: EmailMessageResponse[]
  count: number
}

interface AuthStartResponse {
  status: string
  message: string
}

interface SyncResponse {
  status: string
  created: number
  updated: number
  deleted: number
}

interface SyncStatusResponse {
  status: string
  last_sync?: string
  syncing?: boolean
}

interface CategoryCount {
  name: string
  total: number
  unread: number
}

interface CategoryCountsResponse {
  categories: CategoryCount[]
}

type EmailCategory = 'all' | 'priority' | 'newsletter' | 'notification' | 'low_priority'

// ---------------------------------------------------------------------------
// Data fetchers
// ---------------------------------------------------------------------------

async function fetchAuthStatus(): Promise<AuthStatusResponse> {
  try {
    return await apiGet<AuthStatusResponse>('/api/email/auth/status')
  } catch {
    return { authenticated: false, needs_credentials: true }
  }
}

async function fetchMessages(category: EmailCategory): Promise<EmailListResponse> {
  const params = category === 'all'
    ? 'limit=50'
    : `limit=50&category=${category}`
  return apiGet<EmailListResponse>(`/api/email/messages?${params}`)
}

async function fetchMessageDetail(id: string): Promise<EmailMessageDetailResponse> {
  return apiGet<EmailMessageDetailResponse>(`/api/email/messages/${id}`)
}

async function fetchCategoryCounts(): Promise<CategoryCountsResponse> {
  return apiGet<CategoryCountsResponse>('/api/email/categories/counts')
}

async function fetchSyncStatus(): Promise<SyncStatusResponse> {
  try {
    return await apiGet<SyncStatusResponse>('/api/email/sync/status')
  } catch {
    return { status: 'unknown' }
  }
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value)
  useEffect(() => {
    const handler = setTimeout(() => setDebouncedValue(value), delay)
    return () => clearTimeout(handler)
  }, [value, delay])
  return debouncedValue
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function timeAgo(iso: string): string {
  const date = new Date(iso)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`

  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  })
}

function formatFullDate(iso: string): string {
  return new Date(iso).toLocaleString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

function decodeHtmlEntities(text: string): string {
  return text
    .replace(/&#39;/g, "'")
    .replace(/&#x27;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&nbsp;/g, ' ')
}

function parseAddresses(raw: string): string {
  try {
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed)) return parsed.join(', ')
  } catch {
    // not JSON
  }
  return raw
}

function cleanBodyText(text: string): string {
  return text
    .replace(/View image:\s*\(https?:\/\/[^\)]+\)/gi, '')
    .replace(/^Caption:\s*$/gm, '')
    .replace(/\(\s*https?:\/\/\S{60,}\s*\)/g, '')
    .replace(/^https?:\/\/\S{60,}$/gm, '')
    .replace(/^[*]{5,}\s*$/gm, '')
    .replace(/^[-=]{5,}\s*$/gm, '')
    .replace(/!\[[^\]]*\]\([^\)]+\)/g, '')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

function truncateLines(text: string, maxLines: number): string {
  const lines = text.split('\n').slice(0, maxLines)
  let result = lines.join(' ').trim()
  if (result.length > 160) result = result.slice(0, 160).trimEnd() + '\u2026'
  return result
}

/** Highlight search matches in text */
function HighlightText({ text, query }: { text: string; query: string }) {
  if (!query.trim()) return <>{text}</>

  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const regex = new RegExp(`(${escaped})`, 'gi')
  const parts = text.split(regex)

  return (
    <>
      {parts.map((part, i) =>
        regex.test(part) ? (
          <mark key={i} className="bg-accent/30 text-text-primary rounded-sm px-0.5">
            {part}
          </mark>
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </>
  )
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function AuthGate() {
  const [authMessage, setAuthMessage] = useState<string | null>(null)
  const [authError, setAuthError] = useState<string | null>(null)

  const authMutation = useMutation({
    mutationFn: () => apiPost<AuthStartResponse>('/api/email/auth/start'),
    onSuccess: (data) => {
      setAuthMessage(data.message)
      setAuthError(null)
    },
    onError: (err: Error) => {
      setAuthError(err.message || 'Failed to start authentication')
      setAuthMessage(null)
    },
  })

  return (
    <div className="border border-border p-8 text-center">
      <div className="inline-flex items-center justify-center w-12 h-12 border border-border mb-4">
        <svg className="w-5 h-5 text-text-secondary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
        </svg>
      </div>
      <p className="text-text-primary text-[15px] font-medium mb-2">
        Email not connected
      </p>
      <p className="text-text-secondary text-[13px] mb-5">
        Connect your Gmail account to view messages
      </p>
      <button
        onClick={() => authMutation.mutate()}
        disabled={authMutation.isPending}
        className="border border-accent text-accent font-mono text-[11px] tracking-wider px-5 py-2.5 hover:bg-accent/10 transition-colors disabled:opacity-50"
      >
        {authMutation.isPending ? 'CONNECTING...' : 'CONNECT GMAIL'}
      </button>
      {authMessage && (
        <p className="text-green-400 text-[12px] mt-3 font-mono">{authMessage}</p>
      )}
      {authError && (
        <p className="text-accent text-[12px] mt-3 font-mono">{authError}</p>
      )}
    </div>
  )
}

// --- Unread Header Banner ---

function UnreadBanner({ counts }: { counts: CategoryCount[] }) {
  const totalUnread = counts.reduce((sum, c) => sum + c.unread, 0)
  if (totalUnread === 0) return null

  const countMap = Object.fromEntries(counts.map((c) => [c.name, c]))
  const breakdowns = [
    { key: 'priority', label: 'PRIORITY', color: 'text-accent' },
    { key: 'newsletter', label: 'NEWS', color: 'text-text-secondary' },
    { key: 'notification', label: 'NOTIF', color: 'text-text-secondary' },
    { key: 'low_priority', label: 'LOW', color: 'text-text-muted' },
  ].filter((b) => (countMap[b.key]?.unread ?? 0) > 0)

  return (
    <div className="border border-accent/30 bg-accent/5 px-4 py-3 mb-5 flex items-center justify-between flex-wrap gap-2">
      <div className="flex items-center gap-3">
        <span className="font-mono text-[22px] font-bold text-accent tracking-tight">
          {totalUnread}
        </span>
        <span className="font-mono text-[11px] tracking-widest text-accent/80 uppercase">
          UNREAD
        </span>
      </div>
      <div className="flex items-center gap-3">
        {breakdowns.map((b) => (
          <span key={b.key} className={`font-mono text-[10px] tracking-wider ${b.color}`}>
            {countMap[b.key]?.unread ?? 0} {b.label}
          </span>
        ))}
      </div>
    </div>
  )
}

// --- Search Bar with debounce ---

function SearchBar({
  value,
  onChange,
  resultCount,
  isSearching,
}: {
  value: string
  onChange: (val: string) => void
  resultCount?: number
  isSearching?: boolean
}) {
  return (
    <div className="relative mb-5">
      <svg
        className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted pointer-events-none"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={1.5}
      >
        <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
      </svg>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Search emails by sender, subject, or content..."
        className="w-full bg-surface-alt border border-border text-text-primary text-[13px] pl-10 pr-20 py-2.5 font-mono placeholder:text-text-muted/50 focus:outline-none focus:border-accent/50 transition-colors"
      />
      <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-2">
        {isSearching && value && (
          <span className="font-mono text-[10px] text-text-muted animate-pulse">searching...</span>
        )}
        {!isSearching && value && resultCount !== undefined && (
          <span className="font-mono text-[10px] text-text-muted">
            {resultCount} result{resultCount !== 1 ? 's' : ''}
          </span>
        )}
        {value && (
          <button
            onClick={() => onChange('')}
            className="text-text-muted hover:text-text-primary transition-colors"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>
    </div>
  )
}

// --- Category Tabs (improved badges) ---

const CATEGORY_TABS: { key: EmailCategory; label: string }[] = [
  { key: 'all', label: 'ALL' },
  { key: 'priority', label: 'PRIORITY' },
  { key: 'newsletter', label: 'NEWSLETTERS' },
  { key: 'notification', label: 'NOTIFICATIONS' },
  { key: 'low_priority', label: 'LOW PRIO' },
]

function CategoryTabs({
  active,
  onChange,
  counts,
}: {
  active: EmailCategory
  onChange: (cat: EmailCategory) => void
  counts: CategoryCount[]
}) {
  const countMap = Object.fromEntries(counts.map((c) => [c.name, c]))
  const totalUnread = counts.reduce((sum, c) => sum + c.unread, 0)
  const totalCount = counts.reduce((sum, c) => sum + c.total, 0)
  const scrollRef = useRef<HTMLDivElement>(null)

  return (
    <div
      ref={scrollRef}
      className="flex gap-1.5 mb-5 overflow-x-auto scrollbar-none pb-1 -mx-1 px-1"
    >
      {CATEGORY_TABS.map((tab) => {
        const total = tab.key === 'all'
          ? totalCount
          : countMap[tab.key]?.total ?? 0
        const unread = tab.key === 'all'
          ? totalUnread
          : countMap[tab.key]?.unread ?? 0
        const isActive = active === tab.key

        return (
          <button
            key={tab.key}
            onClick={() => onChange(tab.key)}
            className={`relative font-mono text-[11px] tracking-wider px-4 py-2.5 border transition-all whitespace-nowrap flex items-center gap-2.5 shrink-0 ${
              isActive
                ? 'border-accent text-accent bg-accent/10 border-b-2 border-b-accent'
                : 'border-border text-text-secondary hover:text-text-primary hover:border-border-light'
            }`}
          >
            <span>{tab.label}</span>
            {total > 0 && (
              <span className={`text-[10px] tabular-nums ${
                isActive ? 'text-accent/60' : 'text-text-muted'
              }`}>
                {total}
              </span>
            )}
            {unread > 0 && (
              <span
                className={`text-[9px] tabular-nums min-w-[18px] text-center px-1.5 py-0.5 font-bold transition-colors ${
                  isActive
                    ? 'bg-accent text-white rounded-sm shadow-[0_0_8px_rgba(220,38,38,0.3)]'
                    : 'border border-accent/30 text-accent/70 rounded-sm'
                }`}
              >
                {unread}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}

// --- Sync Status + Button ---

function SyncStatusBar() {
  const queryClient = useQueryClient()

  const { data: syncStatus } = useQuery({
    queryKey: ['email', 'sync', 'status'],
    queryFn: fetchSyncStatus,
    refetchInterval: 10000,
  })

  const syncMutation = useMutation({
    mutationFn: () => apiPost<SyncResponse>('/api/email/sync'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['email'] })
    },
  })

  const isSyncing = syncMutation.isPending || syncStatus?.syncing === true
  const lastSync = syncStatus?.last_sync

  return (
    <div className="flex items-center gap-3">
      {/* Last sync time */}
      {lastSync && !isSyncing && (
        <span className="font-mono text-[10px] text-text-muted tracking-wide hidden sm:inline">
          synced {timeAgo(lastSync)}
        </span>
      )}

      {/* Syncing indicator */}
      {isSyncing && (
        <div className="flex items-center gap-1.5">
          <span className="block h-1.5 w-1.5 rounded-full bg-accent animate-pulse-dot" />
          <span className="font-mono text-[10px] text-accent tracking-wider">SYNCING</span>
        </div>
      )}

      {/* Sync button */}
      <button
        onClick={() => syncMutation.mutate()}
        disabled={isSyncing}
        className="font-mono text-[11px] tracking-wider border border-border text-text-secondary hover:text-accent hover:border-accent/50 px-3 py-1.5 transition-colors disabled:opacity-50 flex items-center gap-2"
      >
        <svg
          className={`h-3 w-3 ${isSyncing ? 'animate-spin' : ''}`}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path d="M21 12a9 9 0 1 1-6.219-8.56" />
        </svg>
        SYNC
      </button>
    </div>
  )
}

// --- Email Action Buttons (on hover) ---

function EmailActions({
  message,
  onOpenDetail,
}: {
  message: EmailMessageResponse
  onOpenDetail: () => void
}) {
  const queryClient = useQueryClient()

  const classifyMutation = useMutation({
    mutationFn: () =>
      apiPost('/api/email/classify', { message_id: message.id }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['email'] })
    },
  })

  return (
    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-150">
      {/* Open detail */}
      <button
        onClick={(e) => {
          e.stopPropagation()
          onOpenDetail()
        }}
        title="View details"
        className="p-1.5 text-text-muted hover:text-text-primary hover:bg-surface-alt transition-colors"
      >
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
        </svg>
      </button>

      {/* Classify */}
      <button
        onClick={(e) => {
          e.stopPropagation()
          classifyMutation.mutate()
        }}
        disabled={classifyMutation.isPending}
        title="Auto-classify"
        className="p-1.5 text-text-muted hover:text-accent hover:bg-accent/10 transition-colors disabled:opacity-50"
      >
        {classifyMutation.isPending ? (
          <svg className="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <path d="M21 12a9 9 0 1 1-6.219-8.56" />
          </svg>
        ) : (
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.568 3H5.25A2.25 2.25 0 003 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 005.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 009.568 3z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 6h.008v.008H6V6z" />
          </svg>
        )}
      </button>
    </div>
  )
}

// --- Email Card ---

function EmailCard({
  message,
  onOpenDetail,
  isPrioritySection,
  searchQuery,
}: {
  message: EmailMessageResponse
  onOpenDetail: (msg: EmailMessageResponse) => void
  isPrioritySection?: boolean
  searchQuery?: string
}) {
  const sender = message.from_name || message.from_address || 'Unknown'
  const senderEmail = message.from_address || ''
  const snippet = message.snippet ? decodeHtmlEntities(message.snippet) : null
  const subject = message.subject ? decodeHtmlEntities(message.subject) : '(no subject)'
  const isPriority = isPrioritySection || message.category === 'priority' || message.is_important
  const q = searchQuery || ''

  return (
    <div className={`group transition-colors ${isPriority ? 'border-l-2 border-l-accent' : ''}`}>
      <div
        onClick={() => onOpenDetail(message)}
        className="w-full text-left px-4 py-3.5 transition-colors hover:bg-surface-alt/60 cursor-pointer flex items-start gap-3"
      >
        {/* Unread indicator */}
        <div className="w-2.5 shrink-0 pt-2">
          {message.is_unread ? (
            <span className="block h-2 w-2 rounded-full bg-accent shadow-[0_0_6px_rgba(220,38,38,0.4)]" />
          ) : (
            <span className="block h-2 w-2 rounded-full border border-border-light/50" />
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          {/* Top row: sender + time */}
          <div className="flex items-baseline justify-between gap-3 mb-0.5">
            <div className="min-w-0 flex-1">
              <span
                className={`text-[14px] truncate block ${
                  message.is_unread
                    ? 'text-text-primary font-semibold'
                    : 'text-text-secondary font-medium'
                }`}
              >
                <HighlightText text={sender} query={q} />
              </span>
              {senderEmail && sender !== senderEmail && (
                <span className="text-[10px] text-text-muted font-mono block truncate mt-0">
                  <HighlightText text={senderEmail} query={q} />
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 shrink-0 pt-0.5">
              <EmailActions message={message} onOpenDetail={() => onOpenDetail(message)} />
              <span className="font-mono text-[10px] text-text-muted tracking-wide">
                {timeAgo(message.date_sent)}
              </span>
            </div>
          </div>

          {/* Subject */}
          <p
            className={`text-[13px] truncate mt-1 ${
              message.is_unread
                ? 'text-text-primary font-bold'
                : 'text-text-primary/70 font-medium'
            }`}
          >
            <HighlightText text={subject} query={q} />
          </p>

          {/* Snippet - 2 lines */}
          {snippet && (
            <p className="text-[11.5px] text-text-muted leading-[1.5] mt-1 line-clamp-2">
              <HighlightText text={truncateLines(snippet, 2)} query={q} />
            </p>
          )}

          {/* Category pill */}
          {message.category && message.category !== 'all' && (
            <span className={`inline-block mt-1.5 font-mono text-[9px] tracking-wider px-2 py-0.5 border ${
              message.category === 'priority'
                ? 'border-accent/30 text-accent/70 bg-accent/5'
                : message.category === 'newsletter'
                  ? 'border-blue-500/20 text-blue-400/60 bg-blue-500/5'
                  : message.category === 'notification'
                    ? 'border-yellow-500/20 text-yellow-400/60 bg-yellow-500/5'
                    : 'border-border text-text-muted bg-surface-alt/30'
            }`}>
              {message.category === 'low_priority' ? 'LOW' : message.category?.toUpperCase()}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

// --- Detail Slide-in Panel ---

function DetailPanel({
  message,
  onClose,
}: {
  message: EmailMessageResponse
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const panelRef = useRef<HTMLDivElement>(null)

  const { data: detail, isLoading, isError } = useQuery({
    queryKey: ['email', 'detail', message.id],
    queryFn: () => fetchMessageDetail(message.id),
  })

  // Close on Escape key
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleEsc)
    return () => window.removeEventListener('keydown', handleEsc)
  }, [onClose])

  // Action mutations
  const archiveMutation = useMutation({
    mutationFn: () => apiPost('/api/email/classify', { message_id: message.id, action: 'archive' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['email'] })
      onClose()
    },
  })

  const markReadMutation = useMutation({
    mutationFn: () => apiPost('/api/email/classify', { message_id: message.id, action: 'mark_read' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['email'] })
    },
  })

  const replyLaterMutation = useMutation({
    mutationFn: () => apiPost('/api/email/classify', { message_id: message.id, action: 'reply_later' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['email'] })
    },
  })

  const subject = message.subject ? decodeHtmlEntities(message.subject) : '(no subject)'

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 z-40 animate-fade-in-overlay"
        onClick={onClose}
      />

      {/* Panel */}
      <div
        ref={panelRef}
        className="fixed right-0 top-0 bottom-0 w-full max-w-[600px] bg-bg border-l border-border z-50 flex flex-col animate-slide-in-right"
      >
        {/* Panel header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            {message.is_unread && (
              <span className="block h-2 w-2 rounded-full bg-accent shadow-[0_0_6px_rgba(220,38,38,0.4)] shrink-0" />
            )}
            <span className="font-mono text-[11px] tracking-widest text-text-secondary uppercase truncate">
              MESSAGE DETAIL
            </span>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-text-muted hover:text-text-primary hover:bg-surface-alt transition-colors shrink-0"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Action bar */}
        <div className="flex items-center gap-2 px-5 py-3 border-b border-border/50 shrink-0">
          <button
            onClick={() => archiveMutation.mutate()}
            disabled={archiveMutation.isPending}
            className="font-mono text-[10px] tracking-wider border border-border text-text-secondary hover:text-accent hover:border-accent/50 px-3 py-1.5 transition-colors disabled:opacity-50 flex items-center gap-1.5"
          >
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5m8.25 3v6.75m0 0l-3-3m3 3l3-3M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z" />
            </svg>
            {archiveMutation.isPending ? 'ARCHIVING...' : 'ARCHIVE'}
          </button>

          <button
            onClick={() => replyLaterMutation.mutate()}
            disabled={replyLaterMutation.isPending}
            className="font-mono text-[10px] tracking-wider border border-border text-text-secondary hover:text-yellow-400 hover:border-yellow-400/50 px-3 py-1.5 transition-colors disabled:opacity-50 flex items-center gap-1.5"
          >
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {replyLaterMutation.isPending ? 'SAVING...' : 'REPLY LATER'}
          </button>

          <button
            onClick={() => markReadMutation.mutate()}
            disabled={markReadMutation.isPending}
            className="font-mono text-[10px] tracking-wider border border-border text-text-secondary hover:text-green-400 hover:border-green-400/50 px-3 py-1.5 transition-colors disabled:opacity-50 flex items-center gap-1.5"
          >
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {markReadMutation.isPending ? 'MARKING...' : 'MARK READ'}
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {/* Subject & Sender header */}
          <div className="px-5 pt-5 pb-4">
            <h2 className="text-[16px] font-semibold text-text-primary leading-snug mb-3">
              {subject}
            </h2>

            <div className="space-y-1.5 text-[11px] font-mono tracking-wide">
              <div className="flex items-baseline gap-2">
                <span className="text-text-muted w-10 shrink-0">FROM</span>
                <span className="text-text-primary/90">
                  {message.from_name
                    ? `${message.from_name} <${message.from_address}>`
                    : message.from_address || 'Unknown'}
                </span>
              </div>

              {detail?.to_addresses && (
                <div className="flex items-baseline gap-2">
                  <span className="text-text-muted w-10 shrink-0">TO</span>
                  <span className="text-text-primary/60">
                    {parseAddresses(detail.to_addresses)}
                  </span>
                </div>
              )}

              {detail?.cc_addresses && (
                <div className="flex items-baseline gap-2">
                  <span className="text-text-muted w-10 shrink-0">CC</span>
                  <span className="text-text-primary/60">
                    {parseAddresses(detail.cc_addresses)}
                  </span>
                </div>
              )}

              <div className="flex items-baseline gap-2">
                <span className="text-text-muted w-10 shrink-0">DATE</span>
                <span className="text-text-primary/60">
                  {formatFullDate(message.date_sent)}
                </span>
              </div>

              {message.category && (
                <div className="flex items-baseline gap-2">
                  <span className="text-text-muted w-10 shrink-0">TAG</span>
                  <span className={`px-2 py-0.5 border text-[9px] tracking-wider ${
                    message.category === 'priority'
                      ? 'border-accent/30 text-accent/70 bg-accent/5'
                      : message.category === 'newsletter'
                        ? 'border-blue-500/20 text-blue-400/60 bg-blue-500/5'
                        : message.category === 'notification'
                          ? 'border-yellow-500/20 text-yellow-400/60 bg-yellow-500/5'
                          : 'border-border text-text-muted bg-surface-alt/30'
                  }`}>
                    {message.category === 'low_priority' ? 'LOW PRIORITY' : message.category?.toUpperCase()}
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Separator */}
          <div className="border-t border-border/30 mx-5" />

          {/* Body */}
          <div className="px-5 py-4">
            {isLoading && <LoadingSkeleton lines={8} />}

            {isError && (
              <p className="text-[12px] text-text-secondary font-mono">
                Unable to load message body
              </p>
            )}

            {detail?.body_text ? (
              <div className="text-[13px] text-text-primary/85 leading-relaxed whitespace-pre-wrap">
                {decodeHtmlEntities(cleanBodyText(detail.body_text))}
              </div>
            ) : (
              !isLoading && (
                <p className="text-[12px] text-text-secondary italic font-mono">
                  No message body available
                </p>
              )
            )}
          </div>
        </div>

        {/* Panel footer with keyboard hint */}
        <div className="px-5 py-2.5 border-t border-border/30 shrink-0">
          <span className="font-mono text-[10px] text-text-muted tracking-wide">
            Press <kbd className="border border-border px-1.5 py-0.5 mx-0.5 text-text-secondary">ESC</kbd> to close
          </span>
        </div>
      </div>
    </>
  )
}

// --- Priority Section (shown on ALL tab) ---

function PrioritySection({
  messages,
  onOpenDetail,
  searchQuery,
}: {
  messages: EmailMessageResponse[]
  onOpenDetail: (msg: EmailMessageResponse) => void
  searchQuery?: string
}) {
  const priorityMessages = messages.filter(
    (m) => m.category === 'priority' || m.is_important
  )

  if (priorityMessages.length === 0) return null

  return (
    <div className="mb-5">
      <div className="flex items-center gap-2 mb-2 px-1">
        <svg className="w-3.5 h-3.5 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
        </svg>
        <span className="font-mono text-[11px] tracking-widest text-accent uppercase font-bold">
          ACTION REQUIRED
        </span>
        <span className="font-mono text-[10px] text-accent/50">
          {priorityMessages.length}
        </span>
      </div>
      <div className="border border-accent/20 bg-accent/[0.02] divide-y divide-border/30">
        {priorityMessages.slice(0, 5).map((msg) => (
          <EmailCard
            key={msg.id}
            message={msg}
            onOpenDetail={onOpenDetail}
            isPrioritySection
            searchQuery={searchQuery}
          />
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page component
// ---------------------------------------------------------------------------

export function CommsPage() {
  const [activeCategory, setActiveCategory] = useState<EmailCategory>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedMessage, setSelectedMessage] = useState<EmailMessageResponse | null>(null)

  // Debounced search
  const debouncedSearch = useDebounce(searchQuery, 300)
  const isSearchDebouncing = searchQuery !== debouncedSearch

  // Auth status
  const { data: auth, isLoading: authLoading } = useQuery({
    queryKey: ['email', 'auth'],
    queryFn: fetchAuthStatus,
  })

  const authenticated = auth?.authenticated === true

  // Category counts
  const { data: countsData } = useQuery({
    queryKey: ['email', 'categories', 'counts'],
    queryFn: fetchCategoryCounts,
    enabled: authenticated,
    refetchInterval: 60000,
  })

  // Messages for active category
  const { data: emailData, isLoading: messagesLoading } = useQuery({
    queryKey: ['email', 'messages', activeCategory],
    queryFn: () => fetchMessages(activeCategory),
    enabled: authenticated,
  })

  const messages = emailData?.messages ?? []
  const counts = countsData?.categories ?? []

  // Client-side search filter with debounced query
  const filteredMessages = useMemo(() => {
    if (!debouncedSearch.trim()) return messages
    const q = debouncedSearch.toLowerCase()
    return messages.filter(
      (m) =>
        (m.from_name && m.from_name.toLowerCase().includes(q)) ||
        (m.from_address && m.from_address.toLowerCase().includes(q)) ||
        (m.subject && m.subject.toLowerCase().includes(q)) ||
        (m.snippet && m.snippet.toLowerCase().includes(q))
    )
  }, [messages, debouncedSearch])

  // Handlers
  const handleCategoryChange = useCallback((cat: EmailCategory) => {
    setActiveCategory(cat)
    setSelectedMessage(null)
    setSearchQuery('')
  }, [])

  const handleOpenDetail = useCallback((msg: EmailMessageResponse) => {
    setSelectedMessage(msg)
  }, [])

  const handleCloseDetail = useCallback(() => {
    setSelectedMessage(null)
  }, [])

  // Split messages for ALL view: priority at top, rest below
  const priorityMessages = activeCategory === 'all'
    ? filteredMessages.filter((m) => m.category === 'priority' || m.is_important)
    : []
  const nonPriorityMessages = activeCategory === 'all'
    ? filteredMessages.filter((m) => m.category !== 'priority' && !m.is_important)
    : filteredMessages

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-4">
          <h3 className="section-title !mb-0">COMMUNICATIONS</h3>
        </div>
        {authenticated && <SyncStatusBar />}
      </div>

      {/* Loading state */}
      {authLoading && <LoadingSkeleton lines={4} />}

      {/* Auth gate */}
      {!authLoading && !authenticated && <AuthGate />}

      {/* Authenticated content */}
      {!authLoading && authenticated && (
        <>
          {/* Unread banner */}
          {counts.length > 0 && <UnreadBanner counts={counts} />}

          {/* Search bar */}
          <SearchBar
            value={searchQuery}
            onChange={setSearchQuery}
            resultCount={debouncedSearch ? filteredMessages.length : undefined}
            isSearching={isSearchDebouncing}
          />

          {/* Category tabs */}
          <CategoryTabs
            active={activeCategory}
            onChange={handleCategoryChange}
            counts={counts}
          />

          {messagesLoading ? (
            <LoadingSkeleton lines={8} />
          ) : filteredMessages.length === 0 ? (
            <div className="border border-border p-8 text-center">
              <p className="text-[13px] text-text-secondary font-mono">
                {searchQuery
                  ? 'No emails match your search.'
                  : 'No messages in this category.'}
              </p>
            </div>
          ) : (
            <>
              {/* Priority section on ALL tab */}
              {activeCategory === 'all' && !debouncedSearch && (
                <PrioritySection
                  messages={priorityMessages}
                  onOpenDetail={handleOpenDetail}
                  searchQuery={debouncedSearch}
                />
              )}

              {/* Search results header */}
              {debouncedSearch && (
                <div className="flex items-center gap-2 mb-2 px-1">
                  <svg className="w-3.5 h-3.5 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
                  </svg>
                  <span className="font-mono text-[11px] tracking-widest text-text-secondary uppercase">
                    SEARCH RESULTS
                  </span>
                  <span className="font-mono text-[10px] text-text-muted">
                    {filteredMessages.length} match{filteredMessages.length !== 1 ? 'es' : ''}
                  </span>
                </div>
              )}

              {/* Main email list */}
              <div>
                {activeCategory === 'all' && !debouncedSearch && nonPriorityMessages.length > 0 && (
                  <div className="flex items-center gap-2 mb-2 px-1">
                    <span className="font-mono text-[11px] tracking-widest text-text-secondary uppercase">
                      ALL MESSAGES
                    </span>
                    <span className="font-mono text-[10px] text-text-muted">
                      {nonPriorityMessages.length}
                    </span>
                  </div>
                )}
                <div className="border border-border divide-y divide-border/30">
                  {(activeCategory === 'all' && !debouncedSearch
                    ? nonPriorityMessages
                    : filteredMessages
                  ).map((msg) => (
                    <EmailCard
                      key={msg.id}
                      message={msg}
                      onOpenDetail={handleOpenDetail}
                      searchQuery={debouncedSearch}
                    />
                  ))}
                </div>
              </div>
            </>
          )}
        </>
      )}

      {/* Detail slide-in panel */}
      {selectedMessage && (
        <DetailPanel
          message={selectedMessage}
          onClose={handleCloseDetail}
        />
      )}
    </div>
  )
}
