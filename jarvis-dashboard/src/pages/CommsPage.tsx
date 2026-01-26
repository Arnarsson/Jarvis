import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost } from '../api/client.ts'
import { LoadingSkeleton } from '../components/ui/LoadingSkeleton.tsx'

// ---------------------------------------------------------------------------
// Types matching the server's response models
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

async function fetchMessages(): Promise<EmailListResponse> {
  return apiGet<EmailListResponse>('/api/email/messages?limit=25')
}

async function fetchMessageDetail(id: string): Promise<EmailMessageDetailResponse> {
  return apiGet<EmailMessageDetailResponse>(`/api/email/messages/${id}`)
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(iso: string): string {
  const date = new Date(iso)
  const now = new Date()
  const isToday =
    date.getDate() === now.getDate() &&
    date.getMonth() === now.getMonth() &&
    date.getFullYear() === now.getFullYear()

  if (isToday) {
    return date.toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
    })
  }

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
  // Handle JSON array format: ["addr@example.com"]
  try {
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed)) return parsed.join(', ')
  } catch {
    // not JSON, return as-is
  }
  return raw
}

function cleanBodyText(text: string): string {
  return text
    // Strip "View image: (url)" blocks
    .replace(/View image:\s*\(https?:\/\/[^\)]+\)/gi, '')
    // Strip "Caption:" on its own line
    .replace(/^Caption:\s*$/gm, '')
    // Strip URLs wrapped in parens: ( https://...long... )
    .replace(/\(\s*https?:\/\/\S{60,}\s*\)/g, '')
    // Strip standalone long URLs on their own line
    .replace(/^https?:\/\/\S{60,}$/gm, '')
    // Strip asterisk/star divider lines
    .replace(/^[*]{5,}\s*$/gm, '')
    // Strip dash/equals divider lines
    .replace(/^[-=]{5,}\s*$/gm, '')
    // Strip markdown image syntax ![alt](url)
    .replace(/!\[[^\]]*\]\([^\)]+\)/g, '')
    // Convert markdown headers to plain text
    .replace(/^#{1,6}\s+/gm, '')
    // Collapse 3+ consecutive newlines to 2
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

function truncate(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text
  return text.slice(0, maxLen).trimEnd() + '…'
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
    <div className="border border-border p-6">
      <p className="text-text-primary text-[15px] font-medium mb-2">
        Email not connected
      </p>
      <p className="text-text-secondary text-[13px] mb-5">
        Connect your Gmail account to view messages
      </p>

      <button
        onClick={() => authMutation.mutate()}
        disabled={authMutation.isPending}
        className="border border-accent text-accent font-mono text-[11px] tracking-wider px-4 py-2 hover:bg-accent/10 transition-colors disabled:opacity-50"
      >
        {authMutation.isPending ? 'CONNECTING...' : 'CONNECT'}
      </button>

      {authMessage && (
        <p className="text-success text-[12px] mt-3 font-mono">{authMessage}</p>
      )}
      {authError && (
        <p className="text-accent text-[12px] mt-3 font-mono">{authError}</p>
      )}
    </div>
  )
}

function StatsBar({ messages }: { messages: EmailMessageResponse[] }) {
  const unread = messages.filter((m) => m.is_unread).length
  const important = messages.filter((m) => m.is_important).length
  const total = messages.length

  const stats = [
    { label: 'UNREAD', value: unread, accent: unread > 0 },
    { label: 'IMPORTANT', value: important, accent: important > 0 },
    { label: 'TOTAL', value: total, accent: false },
  ]

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-6">
      {stats.map((s) => (
        <div key={s.label} className="border border-border py-3 px-4">
          <p
            className={`font-mono text-2xl font-bold tracking-tight ${
              s.accent ? 'text-accent' : 'text-text-primary'
            }`}
          >
            {s.value}
          </p>
          <p className="font-mono text-[10px] tracking-wider text-text-secondary mt-1">
            {s.label}
          </p>
        </div>
      ))}
    </div>
  )
}

function MessageDetail({ messageId }: { messageId: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['email', 'detail', messageId],
    queryFn: () => fetchMessageDetail(messageId),
  })

  if (isLoading) {
    return (
      <div className="px-4 py-4 bg-surface-alt border-t border-border/30">
        <LoadingSkeleton lines={4} />
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div className="px-4 py-3 bg-surface-alt border-t border-border/30">
        <p className="text-[12px] text-text-secondary">
          Unable to load message
        </p>
      </div>
    )
  }

  return (
    <div className="px-4 py-4 bg-surface-alt border-t border-border/30">
      {/* Meta row */}
      <div className="space-y-1 mb-4 text-[11px] text-text-secondary font-mono tracking-wide">
        {data.from_address && (
          <p>
            <span className="text-text-muted">FROM</span>{' '}
            {data.from_name || data.from_address}
          </p>
        )}
        {data.to_addresses && (
          <p>
            <span className="text-text-muted">TO</span>{' '}
            {parseAddresses(data.to_addresses)}
          </p>
        )}
        {data.cc_addresses && (
          <p>
            <span className="text-text-muted">CC</span>{' '}
            {parseAddresses(data.cc_addresses)}
          </p>
        )}
      </div>

      {/* Body */}
      {data.body_text ? (
        <div className="text-[13px] text-text-primary/90 leading-relaxed whitespace-pre-wrap max-h-96 overflow-y-auto pr-2">
          {decodeHtmlEntities(cleanBodyText(data.body_text))}
        </div>
      ) : (
        <p className="text-[12px] text-text-secondary italic">
          No message body available
        </p>
      )}
    </div>
  )
}

function MessageRow({
  message,
  isExpanded,
  onToggle,
}: {
  message: EmailMessageResponse
  isExpanded: boolean
  onToggle: () => void
}) {
  const sender = message.from_name || message.from_address || 'Unknown'
  const snippet = message.snippet ? decodeHtmlEntities(message.snippet) : null
  const subject = message.subject ? decodeHtmlEntities(message.subject) : null

  return (
    <div>
      <button
        onClick={onToggle}
        className={`w-full text-left flex items-start gap-3 py-3 border-b border-border/50 transition-colors hover:bg-surface-alt/50 ${
          message.is_important ? 'border-l-2 border-l-accent pl-3' : 'pl-4'
        } pr-4`}
      >
        {/* Unread dot */}
        <div className="w-2 shrink-0 pt-1.5">
          {message.is_unread && (
            <span className="block h-1.5 w-1.5 rounded-full bg-accent" />
          )}
        </div>

        {/* Main content */}
        <div className="flex-1 min-w-0">
          {/* Top row: sender + date */}
          <div className="flex items-baseline justify-between gap-3">
            <p
              className={`text-[13px] truncate ${
                message.is_unread ? 'text-text-primary font-medium' : 'text-text-secondary'
              }`}
            >
              {truncate(sender, 36)}
            </p>
            <span className="font-mono text-[10px] text-text-muted tracking-wide shrink-0">
              {formatDate(message.date_sent)}
            </span>
          </div>

          {/* Subject */}
          <p
            className={`text-[12px] truncate mt-0.5 ${
              message.is_unread ? 'text-text-primary/80' : 'text-text-secondary/70'
            }`}
          >
            {subject || '(no subject)'}
          </p>

          {/* Snippet */}
          {snippet && (
            <p className="text-[11px] text-text-muted truncate mt-0.5">
              {snippet}
            </p>
          )}
        </div>
      </button>

      {/* Expanded detail panel */}
      {isExpanded && <MessageDetail messageId={message.id} />}
    </div>
  )
}

function SyncButton() {
  const queryClient = useQueryClient()

  const syncMutation = useMutation({
    mutationFn: () => apiPost<SyncResponse>('/api/email/sync'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['email', 'messages'] })
    },
  })

  return (
    <button
      onClick={() => syncMutation.mutate()}
      disabled={syncMutation.isPending}
      className="font-mono text-[11px] tracking-wider text-accent hover:text-accent-hover transition-colors disabled:opacity-50 flex items-center gap-2"
    >
      {syncMutation.isPending && (
        <svg
          className="h-3 w-3 animate-spin"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path d="M21 12a9 9 0 1 1-6.219-8.56" />
        </svg>
      )}
      {syncMutation.isPending ? 'SYNCING...' : 'SYNC'}
    </button>
  )
}

// ---------------------------------------------------------------------------
// Main page component
// ---------------------------------------------------------------------------

export function CommsPage() {
  const [expandedId, setExpandedId] = useState<string | null>(null)

  // Auth status
  const { data: auth, isLoading: authLoading } = useQuery({
    queryKey: ['email', 'auth'],
    queryFn: fetchAuthStatus,
  })

  // Messages (only when authenticated)
  const { data: emailData, isLoading: messagesLoading } = useQuery({
    queryKey: ['email', 'messages'],
    queryFn: fetchMessages,
    enabled: auth?.authenticated === true,
  })

  const messages = emailData?.messages ?? []
  const authenticated = auth?.authenticated === true

  return (
    <div>
      {/* Header row */}
      <div className="flex items-center justify-between mb-6">
        <h3 className="section-title !mb-0">COMMUNICATIONS</h3>
        {authenticated && <SyncButton />}
      </div>

      {/* Loading state */}
      {authLoading && <LoadingSkeleton lines={4} />}

      {/* Auth gate */}
      {!authLoading && !authenticated && <AuthGate />}

      {/* Authenticated content */}
      {!authLoading && authenticated && (
        <>
          {messagesLoading ? (
            <LoadingSkeleton lines={6} />
          ) : (
            <>
              <StatsBar messages={messages} />

              {messages.length === 0 ? (
                <p className="text-sm text-text-secondary py-4">
                  No messages found. Try syncing your inbox.
                </p>
              ) : (
                <div className="border border-border">
                  {messages.map((msg) => (
                    <MessageRow
                      key={msg.id}
                      message={msg}
                      isExpanded={expandedId === msg.id}
                      onToggle={() =>
                        setExpandedId((prev) =>
                          prev === msg.id ? null : msg.id
                        )
                      }
                    />
                  ))}
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  )
}
