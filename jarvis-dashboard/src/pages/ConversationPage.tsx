import { useState, useEffect } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { apiGet } from '../api/client.ts'

/* ───────────────────────── Types ───────────────────────── */

interface Conversation {
  id: string
  external_id: string
  source: string
  title: string
  full_text: string
  message_count: number
  conversation_date: string | null
  imported_at: string | null
}

/* ───────────────────────── Helpers ───────────────────────── */

function formatDate(isoDate: string | null): string {
  if (!isoDate) return 'Unknown date'
  try {
    return new Date(isoDate).toLocaleDateString('en-US', {
      month: 'long',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return 'Invalid date'
  }
}

function highlightText(text: string, query: string): string {
  if (!query.trim()) {
    return text
  }

  // Split query into words (minimum 3 chars)
  const queryWords = query
    .toLowerCase()
    .split(/\s+/)
    .filter((w) => w.length >= 3)

  if (queryWords.length === 0) {
    return text
  }

  // Create regex to match any query word
  const regexPattern = queryWords
    .map((word) => word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
    .join('|')

  const regex = new RegExp(`(${regexPattern})`, 'gi')

  return text.replace(regex, '<mark class="bg-accent/30 text-accent font-semibold">$1</mark>')
}

/* ───────────────────────── Component ───────────────────────── */

export function ConversationPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const [conversation, setConversation] = useState<Conversation | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Get search query from URL state if coming from search
  const searchQuery = (location.state as any)?.searchQuery || ''

  useEffect(() => {
    if (id) {
      fetchConversation(id)
    }
  }, [id])

  const fetchConversation = async (conversationId: string) => {
    setLoading(true)
    setError(null)
    try {
      const data = await apiGet<Conversation>(`/api/v2/conversations/${conversationId}`)
      setConversation(data)
    } catch (e) {
      console.error('Failed to fetch conversation:', e)
      setError('Failed to load conversation')
    } finally {
      setLoading(false)
    }
  }

  const sourceConfig = {
    chatgpt: { label: 'ChatGPT', color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
    claude: { label: 'Claude', color: 'text-orange-400', bg: 'bg-orange-500/10' },
    grok: { label: 'Grok', color: 'text-blue-400', bg: 'bg-blue-500/10' },
  }[conversation?.source.toLowerCase() || ''] || {
    label: conversation?.source || 'Unknown',
    color: 'text-text-muted',
    bg: 'bg-surface',
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <button
          onClick={() => navigate(-1)}
          className="mb-4 text-xs font-mono text-text-muted hover:text-accent transition-colors flex items-center gap-2"
        >
          ← Back
        </button>

        {conversation && (
          <div>
            <div className="flex items-center gap-3 mb-2">
              <h1 className="text-2xl font-mono font-bold text-text-primary tracking-wide">
                {conversation.title}
              </h1>
              <span
                className={`text-[10px] font-mono px-2 py-1 rounded ${sourceConfig.color} ${sourceConfig.bg} uppercase`}
              >
                {sourceConfig.label}
              </span>
            </div>

            <div className="flex items-center gap-4 text-xs font-mono text-text-muted">
              <span>{formatDate(conversation.conversation_date)}</span>
              <span>•</span>
              <span>{conversation.message_count} messages</span>
            </div>
          </div>
        )}
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex items-center gap-2 text-text-muted text-xs font-mono py-8">
          <span className="inline-block h-2 w-2 rounded-full bg-accent animate-pulse" />
          Loading conversation…
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="border border-red-500/20 rounded-lg p-4 bg-red-500/5">
          <p className="text-red-400/70 text-xs font-mono">{error}</p>
        </div>
      )}

      {/* Conversation Content */}
      {!loading && conversation && (
        <div className="border border-border rounded-lg bg-surface p-6">
          <div
            className="prose prose-invert prose-sm max-w-none"
            dangerouslySetInnerHTML={{
              __html: highlightText(
                conversation.full_text.replace(/\n/g, '<br/>'),
                searchQuery
              ),
            }}
          />
        </div>
      )}

      {/* Footer Info */}
      {!loading && conversation && (
        <div className="mt-4 text-[10px] font-mono text-text-muted text-center">
          Imported {formatDate(conversation.imported_at)} • ID: {conversation.id}
        </div>
      )}
    </div>
  )
}
