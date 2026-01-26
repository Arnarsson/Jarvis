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

function truncate(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text
  return text.slice(0, maxLen).trimEnd() + '...'
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
      <div className="flex flex-wrap gap-x-6 gap-y-1 mb-3 text-[11px] text-text-secondary font-mono tracking-wide">
        {data.from_address && (
          <span>
            FROM: {data.from_name ? `${data.from_name} <${data.from_address}>` : data.from_address}
          </span>
        )}
        {data.to_addresses && <span>TO: {data.to_addresses}</span>}
        {data.cc_addresses && <span>CC: {data.cc_addresses}</span>}
      </div>

      {/* Body */}
      {data.body_text ? (
        <div className="text-[13px] text-text-primary leading-relaxed whitespace-pre-wrap max-h-80 overflow-y-auto pr-2">
          {data.body_text}
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

  return (
    <div>
      <button
        onClick={onToggle}
        className={`w-full text-left flex items-start gap-3 py-3.5 border-b border-border/50 transition-colors hover:bg-surface-alt/50 ${
          message.is_important ? 'border-l-2 border-l-accent pl-3' : 'pl-4'
        }`}
      >
        {/* Main content */}
        <div className="flex-1 min-w-0">
          {/* Sender */}
          <p
            className={`text-[13px] font-medium truncate ${
              message.is_unread ? 'text-text-primary' : 'text-text-secondary'
            }`}
          >
            {truncate(sender, 32)}
          </p>

          {/* Subject */}
          <p
            className={`text-[13px] truncate mt-0.5 ${
              message.is_unread ? 'text-text-primary' : 'text-text-secondary/80'
            }`}
          >
            {message.subject || '(no subject)'}
          </p>

          {/* Snippet - hidden on mobile */}
          {message.snippet && (
            <p className="hidden sm:block text-[12px] text-text-secondary truncate mt-0.5">
              {message.snippet}
            </p>
          )}
        </div>

        {/* Right side: date + unread indicator */}
        <div className="flex items-center gap-2 shrink-0 pt-0.5">
          <span className="font-mono text-[11px] text-text-secondary tracking-wide">
            {formatDate(message.date_sent)}
          </span>
          {message.is_unread && (
            <span className="inline-block h-2 w-2 rounded-full bg-accent shrink-0" />
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
