import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiGet } from '../api/client.ts'

/* ───────────────────────── Types ───────────────────────── */

interface PersonContact {
  name: string
  frequency: number
  last_seen: string | null
  first_seen: string | null
  days_since_contact: number | null
  projects: string[]
  topics: string[]
  status: string
  suggested_action: string | null
  conversation_count: number
}

interface PeopleGraphData {
  contacts: PersonContact[]
  total_people: number
  active_count: number
  fading_count: number
  stale_count: number
  top_5: string[]
}

/* ───────────────────────── Helpers ───────────────────────── */

function timeAgo(isoDate: string | null): string {
  if (!isoDate) return 'unknown'
  try {
    const now = Date.now()
    const then = new Date(isoDate).getTime()
    const diffMs = now - then
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffDays === 0) return 'today'
    if (diffDays === 1) return 'yesterday'
    if (diffDays < 7) return `${diffDays}d ago`
    if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`
    if (diffDays < 365) return `${Math.floor(diffDays / 30)}mo ago`
    return `${Math.floor(diffDays / 365)}y ago`
  } catch {
    return 'unknown'
  }
}

/* ───────────────────────── Contact Card ───────────────────────── */

function ContactCard({ contact, onClick }: { contact: PersonContact; onClick?: () => void }) {
  const statusConfig = {
    active: {
      label: 'ACTIVE',
      color: 'text-green-400',
      bg: 'bg-green-500/10',
      border: 'border-green-500/30',
      icon: '🟢',
    },
    fading: {
      label: 'FADING',
      color: 'text-yellow-400',
      bg: 'bg-yellow-500/10',
      border: 'border-yellow-500/30',
      icon: '🟡',
    },
    stale: {
      label: 'STALE',
      color: 'text-red-400',
      bg: 'bg-red-500/10',
      border: 'border-red-500/30',
      icon: '🔴',
    },
  }[contact.status] || {
    label: contact.status.toUpperCase(),
    color: 'text-text-muted',
    bg: 'bg-surface',
    border: 'border-border',
    icon: '⚪',
  }

  return (
    <div
      onClick={onClick}
      className={`border rounded-lg p-4 ${statusConfig.bg} ${statusConfig.border} hover:border-accent/50 transition-colors ${onClick ? 'cursor-pointer' : ''}`}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2">
          <span className="text-base">{statusConfig.icon}</span>
          <h3 className="text-sm font-mono font-semibold text-text-primary">
            {contact.name}
          </h3>
        </div>
        <span
          className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${statusConfig.color} bg-black/20 uppercase`}
        >
          {statusConfig.label}
        </span>
      </div>

      {/* Stats */}
      <div className="flex items-center gap-4 mb-3 text-[11px] font-mono text-text-muted">
        <span>
          Mentions: <span className="text-text-primary">{contact.frequency}</span>
        </span>
        <span>
          Last: <span className="text-text-primary">{timeAgo(contact.last_seen)}</span>
        </span>
      </div>

      {/* Projects */}
      {contact.projects.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {contact.projects.slice(0, 3).map((project, i) => (
            <span
              key={i}
              className="px-2 py-0.5 text-[10px] font-mono text-purple-400 bg-purple-500/10 rounded"
            >
              📁 {project}
            </span>
          ))}
          {contact.projects.length > 3 && (
            <span className="px-2 py-0.5 text-[10px] font-mono text-text-muted">
              +{contact.projects.length - 3} more
            </span>
          )}
        </div>
      )}

      {/* Suggested Action */}
      {contact.suggested_action && (
        <div className="text-[11px] font-mono text-accent">
          💡 {contact.suggested_action}
        </div>
      )}
    </div>
  )
}

/* ───────────────────────── Main Component ───────────────────────── */

export function PeopleGraph() {
  const navigate = useNavigate()
  const [data, setData] = useState<PeopleGraphData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filterStatus, setFilterStatus] = useState<string | null>(null)

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await apiGet<PeopleGraphData>('/api/v2/people/graph?min_frequency=3&limit=50')
      setData(response)
    } catch (e) {
      console.error('Failed to fetch people graph:', e)
      setError('Failed to load people graph')
    } finally {
      setLoading(false)
    }
  }

  const filteredContacts = data?.contacts.filter((c) =>
    filterStatus ? c.status === filterStatus : true
  )

  return (
    <div className="mb-10">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-mono font-bold text-text-primary tracking-wider uppercase">
            👥 PEOPLE GRAPH
          </h2>
          <p className="text-xs font-mono text-text-muted tracking-wide mt-1">
            Contact frequency & reconnection radar
          </p>
        </div>
        <button
          onClick={fetchData}
          disabled={loading}
          className="px-3 py-1.5 text-[11px] font-mono border border-border text-text-primary hover:border-accent hover:text-accent transition-colors disabled:opacity-50"
        >
          {loading ? 'LOADING...' : 'REFRESH'}
        </button>
      </div>

      {/* Stats Row */}
      {data && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
          <div className="border border-border rounded p-3 text-center">
            <div className="text-xl font-mono font-bold text-text-primary">
              {data.total_people}
            </div>
            <div className="text-[10px] font-mono text-text-muted uppercase tracking-wider">
              Total Contacts
            </div>
          </div>
          <div className="border border-green-500/30 rounded p-3 text-center bg-green-500/5">
            <div className="text-xl font-mono font-bold text-green-400">
              {data.active_count}
            </div>
            <div className="text-[10px] font-mono text-text-muted uppercase tracking-wider">
              Active (7d)
            </div>
          </div>
          <div className="border border-yellow-500/30 rounded p-3 text-center bg-yellow-500/5">
            <div className="text-xl font-mono font-bold text-yellow-400">
              {data.fading_count}
            </div>
            <div className="text-[10px] font-mono text-text-muted uppercase tracking-wider">
              Fading (30d)
            </div>
          </div>
          <div className="border border-red-500/30 rounded p-3 text-center bg-red-500/5">
            <div className="text-xl font-mono font-bold text-red-400">
              {data.stale_count}
            </div>
            <div className="text-[10px] font-mono text-text-muted uppercase tracking-wider">
              Stale (30d+)
            </div>
          </div>
          <div className="border border-border rounded p-3 text-center">
            <div className="text-xl font-mono font-bold text-accent">
              {data.top_5.length}
            </div>
            <div className="text-[10px] font-mono text-text-muted uppercase tracking-wider">
              Top Contacts
            </div>
          </div>
        </div>
      )}

      {/* Filter Buttons */}
      {data && (
        <div className="flex flex-wrap items-center gap-2 mb-6">
          <span className="text-[10px] font-mono text-text-muted tracking-wider uppercase">
            FILTER:
          </span>
          <button
            onClick={() => setFilterStatus(null)}
            className={`px-3 py-1.5 text-[11px] font-mono rounded border transition-colors ${
              !filterStatus
                ? 'border-accent text-accent bg-accent/5'
                : 'border-border text-text-secondary hover:border-border-light hover:text-text-primary'
            }`}
          >
            All ({data.contacts.length})
          </button>
          <button
            onClick={() => setFilterStatus('active')}
            className={`px-3 py-1.5 text-[11px] font-mono rounded border transition-colors ${
              filterStatus === 'active'
                ? 'border-green-400 text-green-400 bg-green-500/5'
                : 'border-border text-text-secondary hover:border-border-light hover:text-text-primary'
            }`}
          >
            Active ({data.active_count})
          </button>
          <button
            onClick={() => setFilterStatus('fading')}
            className={`px-3 py-1.5 text-[11px] font-mono rounded border transition-colors ${
              filterStatus === 'fading'
                ? 'border-yellow-400 text-yellow-400 bg-yellow-500/5'
                : 'border-border text-text-secondary hover:border-border-light hover:text-text-primary'
            }`}
          >
            Fading ({data.fading_count})
          </button>
          <button
            onClick={() => setFilterStatus('stale')}
            className={`px-3 py-1.5 text-[11px] font-mono rounded border transition-colors ${
              filterStatus === 'stale'
                ? 'border-red-400 text-red-400 bg-red-500/5'
                : 'border-border text-text-secondary hover:border-border-light hover:text-text-primary'
            }`}
          >
            Stale ({data.stale_count})
          </button>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="border border-red-500/20 rounded-lg p-4 bg-red-500/5 mb-4">
          <p className="text-red-400/70 text-xs font-mono">{error}</p>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center gap-2 text-text-muted text-xs font-mono py-8">
          <span className="inline-block h-2 w-2 rounded-full bg-accent animate-pulse" />
          Loading people graph…
        </div>
      )}

      {/* Contacts Grid */}
      {!loading && filteredContacts && filteredContacts.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredContacts.map((contact) => (
            <ContactCard 
              key={contact.name} 
              contact={contact}
              onClick={() => navigate(`/brain?search=${encodeURIComponent(contact.name)}`)}
            />
          ))}
        </div>
      )}

      {/* Empty State */}
      {!loading && data && filteredContacts && filteredContacts.length === 0 && (
        <div className="border border-border/30 rounded-lg p-10 text-center">
          <div className="text-3xl mb-4">👥</div>
          <p className="text-sm font-mono text-text-secondary">
            No contacts found in this category
          </p>
        </div>
      )}
    </div>
  )
}
