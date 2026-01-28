import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchMorningBriefing, fetchPatterns } from '../../api/briefing.ts'
import { LoadingSkeleton } from '../ui/LoadingSkeleton.tsx'
import { draftEmail, createLinearTask } from '../../api/actions.ts'

/* ───────────────── Helpers ───────────────── */

function timeAgo(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(ms / 60000)
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

/* ───────────────── Action Button Component ───────────────── */

interface ActionButtonProps {
  onClick: () => Promise<void>
  label: string
  variant?: 'primary' | 'secondary' | 'danger'
  icon?: string
  disabled?: boolean
}

function ActionButton({ onClick, label, variant = 'secondary', icon, disabled = false }: ActionButtonProps) {
  const [isLoading, setIsLoading] = useState(false)
  
  const handleClick = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (disabled || isLoading) return
    
    setIsLoading(true)
    try {
      await onClick()
    } catch (error) {
      console.error('Action failed:', error)
    } finally {
      setIsLoading(false)
    }
  }
  
  const variantClasses = {
    primary: 'bg-accent/20 text-accent border-accent/30 hover:bg-accent/30',
    secondary: 'bg-surface/50 text-text-muted border-border/50 hover:bg-surface hover:text-text-primary',
    danger: 'bg-red-500/20 text-red-400 border-red-500/30 hover:bg-red-500/30',
  }
  
  return (
    <button
      onClick={handleClick}
      disabled={disabled || isLoading}
      className={`
        shrink-0 px-2.5 py-1 rounded text-[10px] font-mono tracking-wider 
        border transition-all disabled:opacity-40 disabled:cursor-not-allowed
        ${variantClasses[variant]}
      `}
    >
      {isLoading ? '...' : `${icon || ''}${icon ? ' ' : ''}${label}`}
    </button>
  )
}

/* ───────────────── Component ───────────────── */

export function WhatDidIMiss() {
  const { data: briefing, isLoading: briefingLoading } = useQuery({
    queryKey: ['briefing', 'morning'],
    queryFn: fetchMorningBriefing,
    staleTime: 5 * 60_000,
    retry: 1,
  })

  const { data: patternsData, isLoading: patternsLoading } = useQuery({
    queryKey: ['patterns', 'recent'],
    queryFn: () => fetchPatterns(5),
    staleTime: 5 * 60_000,
    retry: 1,
  })

  const isLoading = briefingLoading || patternsLoading
  
  /* ───────────────── Action Handlers ───────────────── */
  
  const handleDraftReply = async (email: any) => {
    await draftEmail({
      to_email: email.from_email || `${email.from_name.toLowerCase().replace(' ', '')}@example.com`,
      to_name: email.from_name,
      subject: email.subject,
      reply_type: 'professional',
    })
  }
  
  const handleCreateTaskFromThread = async (title: string, description: string) => {
    await createLinearTask({
      title: title.slice(0, 80),
      description,
      priority: 3,
    })
  }

  if (isLoading) {
    return (
      <div>
        <h2 className="section-title">👁 WHAT DID I MISS?</h2>
        <LoadingSkeleton lines={4} />
      </div>
    )
  }

  const emails = briefing?.sections.email_highlights ?? []
  const patterns = patternsData?.patterns ?? []
  const unfinished = briefing?.sections.unfinished_business ?? []
  const patternAlerts = briefing?.sections.pattern_alerts ?? []

  // Filter out noise from pattern alerts
  const realAlerts = patternAlerts.filter(
    (a) => !a.key.includes('\n') && a.key.length < 40
  )

  const totalEmailCount = emails.length
  const hasActivity = totalEmailCount > 0 || patterns.length > 0 || realAlerts.length > 0

  if (!hasActivity) {
    return (
      <div>
        <h2 className="section-title">👁 WHAT DID I MISS?</h2>
        <div className="border border-border/30 border-dashed rounded-lg p-6 text-center">
          <p className="text-2xl mb-2">✨</p>
          <p className="font-mono text-xs text-text-muted">Nothing missed — you're on top of it</p>
        </div>
      </div>
    )
  }

  return (
    <div>
      <h2 className="section-title">👁 WHAT DID I MISS?</h2>

      <div className="space-y-4">
        {/* Email summary */}
        {totalEmailCount > 0 && (
          <div className="border border-border/30 rounded-lg bg-surface/30 p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="text-blue-400 text-lg">📧</span>
                <span className="font-mono text-xs font-bold text-text-primary tracking-wider">
                  {totalEmailCount} RECENT EMAILS
                </span>
              </div>
              <a
                href="/comms"
                className="font-mono text-[10px] text-text-muted hover:text-accent tracking-wider transition-colors"
              >
                VIEW ALL →
              </a>
            </div>
            <div className="space-y-2">
              {emails.slice(0, 3).map((email, i) => (
                <div key={i} className="flex items-start gap-2 py-1.5">
                  <div className="shrink-0 w-6 h-6 rounded-full bg-blue-500/20 flex items-center justify-center text-[10px] text-blue-400 font-bold">
                    {email.from_name.charAt(0).toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-text-primary truncate">
                      <span className="font-medium">{email.from_name}</span>
                      <span className="text-text-muted"> — </span>
                      {email.subject}
                    </p>
                    <p className="text-[10px] text-text-muted mt-0.5">
                      {timeAgo(email.received)}
                    </p>
                  </div>
                  <ActionButton
                    onClick={() => handleDraftReply(email)}
                    label="REPLY"
                    variant="primary"
                    icon="✉"
                  />
                </div>
              ))}
              {totalEmailCount > 3 && (
                <p className="text-[10px] text-text-muted font-mono pt-1">
                  +{totalEmailCount - 3} more
                </p>
              )}
            </div>
          </div>
        )}

        {/* Unfinished business */}
        {unfinished.length > 0 && (
          <div className="border border-orange-500/20 rounded-lg bg-orange-500/5 p-4">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-orange-400 text-lg">⚠️</span>
              <span className="font-mono text-xs font-bold text-text-primary tracking-wider">
                UNFINISHED THREADS
              </span>
            </div>
            <div className="space-y-2">
              {unfinished.map((item, i) => (
                <div key={i} className="flex items-center justify-between py-1.5">
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-text-primary font-medium capitalize">
                      {item.topic}
                    </p>
                    <p className="text-[10px] text-text-muted">{item.suggested_action}</p>
                  </div>
                  <span className="text-[10px] text-text-muted font-mono shrink-0 ml-4">
                    {timeAgo(item.last_seen)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Pattern alerts */}
        {realAlerts.length > 0 && (
          <div className="border border-purple-500/20 rounded-lg bg-purple-500/5 p-4">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-purple-400 text-lg">🔍</span>
              <span className="font-mono text-xs font-bold text-text-primary tracking-wider">
                PATTERNS DETECTED
              </span>
            </div>
            <div className="space-y-2">
              {realAlerts.slice(0, 3).map((alert, i) => (
                <div key={i} className="py-1.5">
                  <p className="text-xs text-text-primary">{alert.suggested_action}</p>
                  <p className="text-[10px] text-text-muted mt-0.5">{alert.description}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
