import { useState, useMemo } from 'react'
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

// --- Search Bar ---

function SearchBar({
  value,
  onChange,
}: {
  value: string
  onChange: (val: string) => void
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
        className="w-full bg-surface-alt border border-border text-text-primary text-[13px] pl-10 pr-4 py-2.5 font-mono placeholder:text-text-muted/50 focus:outline-none focus:border-accent/50 transition-colors"
      />
      {value && (
        <button
          onClick={() => onChange('')}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary transition-colors"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      )}
    </div>
  )
}

// --- Category Tabs ---

const CATEGORY_TABS: { key: EmailCategory; label: string }[] = [
  { key: 'all', label: 'ALL' },
  { key: 'priority', label: 'PRIORITY' },
  { key: 'newsletter', label: 'NEWSLETTERS' },
  { key: 'notification', label: 'NOTIFICATIONS' },
  { key: 'low_priority', label: 'LOW PRIORITY' },
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

  return (
    <div className="flex gap-1 mb-5 overflow-x-auto scrollbar-none pb-0.5">
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
            className={`relative font-mono text-[11px] tracking-wider px-4 py-2 border transition-all whitespace-nowrap flex items-center gap-2 ${
              isActive
                ? 'border-accent text-accent bg-accent/10 border-b-2 border-b-accent'
                : 'border-border text-text-secondary hover:text-text-primary hover:border-border-light'
            }`}
          >
            <span>{tab.label}</span>
            {total > 0 && (
              <span className={`text-[10px] ${isActive ? 'text-accent/70' : 'text-text-muted'}`}>
                ({total})
              </span>
            )}
            {unread > 0 && (
              <span
                className={`text-[9px] px-1.5 py-0.5 rounded-sm font-bold ${
                  isActive
                    ? 'bg-accent/25 text-accent'
                    : 'bg-accent/15 text-accent/80'
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

// --- Message Detail (expanded) ---

function MessageDetail({ messageId }: { messageId: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['email', 'detail', messageId],
    queryFn: () => fetchMessageDetail(messageId),
  })

  if (isLoading) {
    return (
      <div className="px-5 py-4 bg-surface-alt border-t border-border/30">
        <LoadingSkeleton lines={4} />
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div className="px-5 py-3 bg-surface-alt border-t border-border/30">
        <p className="text-[12px] text-text-secondary">Unable to load message</p>
      </div>
    )
  }

  return (
    <div className="px-5 py-4 bg-[#0d0d0d] border-t border-border/20">
      {/* Metadata */}
      <div className="space-y-1 mb-4 text-[11px] text-text-secondary font-mono tracking-wide">
        {data.from_address && (
          <p>
            <span className="text-text-muted mr-2">FROM</span>
            <span className="text-text-primary/80">{data.from_name ? `${data.from_name} <${data.from_address}>` : data.from_address}</span>
          </p>
        )}
        {data.to_addresses && (
          <p>
            <span className="text-text-muted mr-2">TO</span>
            <span className="text-text-primary/60">{parseAddresses(data.to_addresses)}</span>
          </p>
        )}
        {data.cc_addresses && (
          <p>
            <span className="text-text-muted mr-2">CC</span>
            <span className="text-text-primary/60">{parseAddresses(data.cc_addresses)}</span>
          </p>
        )}
        <p>
          <span className="text-text-muted mr-2">DATE</span>
          <span className="text-text-primary/60">
            {new Date(data.date_sent).toLocaleString('en-US', {
              weekday: 'short',
              month: 'short',
              day: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
              hour12: false,
            })}
          </span>
        </p>
      </div>

      {/* Separator */}
      <div className="border-t border-border/20 my-3" />

      {/* Body */}
      {data.body_text ? (
        <div className="text-[13px] text-text-primary/85 leading-relaxed whitespace-pre-wrap max-h-[500px] overflow-y-auto pr-2 scrollbar-thin">
          {decodeHtmlEntities(cleanBodyText(data.body_text))}
        </div>
      ) : (
        <p className="text-[12px] text-text-secondary italic">No message body available</p>
      )}
    </div>
  )
}

// --- Email Card ---

function EmailCard({
  message,
  isExpanded,
  onToggle,
  isPrioritySection,
}: {
  message: EmailMessageResponse
  isExpanded: boolean
  onToggle: () => void
  isPrioritySection?: boolean
}) {
  const sender = message.from_name || message.from_address || 'Unknown'
  const senderEmail = message.from_address || ''
  const snippet = message.snippet ? decodeHtmlEntities(message.snippet) : null
  const subject = message.subject ? decodeHtmlEntities(message.subject) : '(no subject)'
  const isPriority = isPrioritySection || message.category === 'priority' || message.is_important

  return (
    <div className={`group transition-colors ${isPriority ? 'border-l-2 border-l-accent' : ''}`}>
      <button
        onClick={onToggle}
        className={`w-full text-left px-4 py-3.5 transition-colors hover:bg-surface-alt/60 ${
          isExpanded ? 'bg-surface-alt/40' : ''
        }`}
      >
        <div className="flex items-start gap-3">
          {/* Unread indicator */}
          <div className="w-2.5 shrink-0 pt-2">
            {message.is_unread && (
              <span className="block h-2 w-2 rounded-full bg-accent shadow-[0_0_6px_rgba(220,38,38,0.4)]" />
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
                  {sender}
                </span>
                {senderEmail && sender !== senderEmail && (
                  <span className="text-[10px] text-text-muted font-mono block truncate mt-0">
                    {senderEmail}
                  </span>
                )}
              </div>
              <span className="font-mono text-[10px] text-text-muted tracking-wide shrink-0 pt-0.5">
                {timeAgo(message.date_sent)}
              </span>
            </div>

            {/* Subject */}
            <p
              className={`text-[13px] truncate mt-1 ${
                message.is_unread
                  ? 'text-text-primary font-bold'
                  : 'text-text-primary/70 font-medium'
              }`}
            >
              {subject}
            </p>

            {/* Snippet - 2 lines */}
            {snippet && (
              <p className="text-[11.5px] text-text-muted leading-[1.5] mt-1 line-clamp-2">
                {truncateLines(snippet, 2)}
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
      </button>

      {/* Expanded detail */}
      {isExpanded && <MessageDetail messageId={message.id} />}
    </div>
  )
}

// --- Priority Section (shown on ALL tab) ---

function PrioritySection({
  messages,
  expandedId,
  onToggle,
}: {
  messages: EmailMessageResponse[]
  expandedId: string | null
  onToggle: (id: string) => void
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
            isExpanded={expandedId === msg.id}
            onToggle={() => onToggle(msg.id)}
            isPrioritySection
          />
        ))}
      </div>
    </div>
  )
}

// --- Sync Button ---

function SyncButton() {
  const queryClient = useQueryClient()

  const syncMutation = useMutation({
    mutationFn: () => apiPost<SyncResponse>('/api/email/sync'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['email'] })
    },
  })

  return (
    <button
      onClick={() => syncMutation.mutate()}
      disabled={syncMutation.isPending}
      className="font-mono text-[11px] tracking-wider border border-border text-text-secondary hover:text-accent hover:border-accent/50 px-3 py-1.5 transition-colors disabled:opacity-50 flex items-center gap-2"
    >
      <svg
        className={`h-3 w-3 ${syncMutation.isPending ? 'animate-spin' : ''}`}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path d="M21 12a9 9 0 1 1-6.219-8.56" />
      </svg>
      {syncMutation.isPending ? 'SYNCING...' : 'SYNC'}
    </button>
  )
}

// ---------------------------------------------------------------------------
// Main page component
// ---------------------------------------------------------------------------

export function CommsPage() {
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [activeCategory, setActiveCategory] = useState<EmailCategory>('all')
  const [searchQuery, setSearchQuery] = useState('')

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

  // Client-side search filter
  const filteredMessages = useMemo(() => {
    if (!searchQuery.trim()) return messages
    const q = searchQuery.toLowerCase()
    return messages.filter(
      (m) =>
        (m.from_name && m.from_name.toLowerCase().includes(q)) ||
        (m.from_address && m.from_address.toLowerCase().includes(q)) ||
        (m.subject && m.subject.toLowerCase().includes(q)) ||
        (m.snippet && m.snippet.toLowerCase().includes(q))
    )
  }, [messages, searchQuery])

  // Handlers
  const handleCategoryChange = (cat: EmailCategory) => {
    setActiveCategory(cat)
    setExpandedId(null)
    setSearchQuery('')
  }

  const handleToggle = (id: string) => {
    setExpandedId((prev) => (prev === id ? null : id))
  }

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
        {authenticated && <SyncButton />}
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
          <SearchBar value={searchQuery} onChange={setSearchQuery} />

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
              {activeCategory === 'all' && !searchQuery && (
                <PrioritySection
                  messages={priorityMessages}
                  expandedId={expandedId}
                  onToggle={handleToggle}
                />
              )}

              {/* Main email list */}
              <div>
                {activeCategory === 'all' && !searchQuery && nonPriorityMessages.length > 0 && (
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
                  {(activeCategory === 'all' && !searchQuery
                    ? nonPriorityMessages
                    : filteredMessages
                  ).map((msg) => (
                    <EmailCard
                      key={msg.id}
                      message={msg}
                      isExpanded={expandedId === msg.id}
                      onToggle={() => handleToggle(msg.id)}
                    />
                  ))}
                </div>
              </div>
            </>
          )}
        </>
      )}
    </div>
  )
}
