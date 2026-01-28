import { useQuery } from '@tanstack/react-query'
import { fetchMorningBriefing, fetchPeopleGraph } from '../../api/briefing.ts'
import type { BriefingData, PeopleContact } from '../../api/briefing.ts'
import { LoadingSkeleton } from '../ui/LoadingSkeleton.tsx'

/* ───────────────── Types ───────────────── */

interface ProactiveSuggestion {
  id: string
  icon: string
  title: string
  description: string
  actionLabel: string
  actionUrl?: string
  urgency: 'high' | 'medium' | 'low'
  type: 'follow-up' | 'reconnect' | 'task' | 'email' | 'pattern'
}

/* ───────────────── Suggestion Builder ───────────────── */

function buildSuggestions(
  briefing: BriefingData | undefined,
  people: PeopleContact[] | undefined
): ProactiveSuggestion[] {
  const suggestions: ProactiveSuggestion[] = []

  // 1. Follow-ups that are overdue
  if (briefing?.sections.follow_ups_due) {
    for (const followUp of briefing.sections.follow_ups_due) {
      if (followUp.days_overdue && followUp.days_overdue > 0) {
        suggestions.push({
          id: `followup-${followUp.text.slice(0, 20)}`,
          icon: '🔔',
          title: `Overdue: ${followUp.text.slice(0, 60)}`,
          description: `${followUp.days_overdue} day${followUp.days_overdue > 1 ? 's' : ''} overdue`,
          actionLabel: 'HANDLE NOW',
          urgency: followUp.days_overdue > 3 ? 'high' : 'medium',
          type: 'follow-up',
        })
      }
    }
  }

  // 2. Stale contacts — people who need reconnection
  if (people) {
    const staleContacts = people.filter(
      (p) => p.status === 'stale' && p.days_since_contact > 30 && p.conversation_count > 5
    )
    for (const contact of staleContacts.slice(0, 3)) {
      suggestions.push({
        id: `reconnect-${contact.name}`,
        icon: '👤',
        title: `Reconnect with ${contact.name}`,
        description: `No contact for ${contact.days_since_contact} days — ${contact.conversation_count} past conversations`,
        actionLabel: 'DRAFT MESSAGE',
        actionUrl: `/command?prefill=Draft a reconnection message to ${encodeURIComponent(contact.name)}`,
        urgency: contact.days_since_contact > 60 ? 'high' : 'medium',
        type: 'reconnect',
      })
    }
  }

  // 3. Fading contacts who might need attention
  if (people) {
    const fadingContacts = people.filter(
      (p) => p.status === 'fading' && p.conversation_count > 10
    )
    for (const contact of fadingContacts.slice(0, 2)) {
      suggestions.push({
        id: `fading-${contact.name}`,
        icon: '⏳',
        title: `${contact.name} is fading`,
        description: `Last contact ${contact.days_since_contact} days ago. ${contact.conversation_count} conversations total.`,
        actionLabel: 'REACH OUT',
        urgency: 'low',
        type: 'reconnect',
      })
    }
  }

  // 4. Unfinished business items
  if (briefing?.sections.unfinished_business) {
    for (const item of briefing.sections.unfinished_business) {
      // Filter out generic noise
      const topic = item.topic.toLowerCase()
      if (['google', 'ads', 'analysis', 'user', 'style'].includes(topic)) continue
      
      suggestions.push({
        id: `unfinished-${item.topic}`,
        icon: '⚠️',
        title: `Unfinished: ${item.topic}`,
        description: item.suggested_action,
        actionLabel: 'REVIEW',
        urgency: 'medium',
        type: 'task',
      })
    }
  }

  // 5. Priority emails needing response
  if (briefing?.sections.email_highlights) {
    const priorityEmails = briefing.sections.email_highlights.filter(
      (e) => e.priority === 'high' || e.priority === 'urgent'
    )
    for (const email of priorityEmails.slice(0, 2)) {
      const isChristopher = email.from_name.toLowerCase().includes('christopher')
      suggestions.push({
        id: `email-${email.from_address}`,
        icon: '📧',
        title: isChristopher ? `Draft reply to Christopher` : `Reply to ${email.from_name}`,
        description: email.subject,
        actionLabel: 'DRAFT REPLY',
        actionUrl: `/command?prefill=Draft a reply to ${encodeURIComponent(email.from_name)} about "${encodeURIComponent(email.subject)}"`,
        urgency: 'high',
        type: 'email',
      })
    }
  }

  // 7. Specific follow-up actions (Thomas follow-up creates Linear task)
  if (briefing?.sections.follow_ups_due) {
    const thomasFollowUp = briefing.sections.follow_ups_due.find(f => f.text.toLowerCase().includes('thomas'))
    if (thomasFollowUp) {
      suggestions.push({
        id: 'action-thomas-linear',
        icon: '✅',
        title: 'Follow up with Thomas',
        description: 'Create Linear task for follow-up',
        actionLabel: 'CREATE TASK',
        actionUrl: `/command?prefill=Create a Linear task: Follow up with Thomas regarding ${encodeURIComponent(thomasFollowUp.text)}`,
        urgency: 'medium',
        type: 'task',
      })
    }
  }

  // 6. Pattern alerts that aren't noise
  if (briefing?.sections.pattern_alerts) {
    const realAlerts = briefing.sections.pattern_alerts.filter(
      (a) => a.pattern_type === 'stale_person' && 
             !a.key.includes('\n') && 
             a.key.length < 30
    )
    for (const alert of realAlerts.slice(0, 2)) {
      suggestions.push({
        id: `pattern-${alert.key}`,
        icon: '🔍',
        title: alert.suggested_action,
        description: alert.description,
        actionLabel: 'ACT ON IT',
        urgency: 'low',
        type: 'pattern',
      })
    }
  }

  // Sort: high urgency first
  const urgencyOrder = { high: 0, medium: 1, low: 2 }
  suggestions.sort((a, b) => urgencyOrder[a.urgency] - urgencyOrder[b.urgency])

  return suggestions.slice(0, 6)
}

/* ───────────────── Urgency colors ───────────────── */

function urgencyStyle(urgency: ProactiveSuggestion['urgency']) {
  switch (urgency) {
    case 'high':
      return {
        border: 'border-red-500/30',
        bg: 'bg-red-500/5',
        badge: 'bg-red-500/20 text-red-400',
        button: 'border-red-500/50 text-red-400 hover:bg-red-500/10',
      }
    case 'medium':
      return {
        border: 'border-orange-500/30',
        bg: 'bg-orange-500/5',
        badge: 'bg-orange-500/20 text-orange-400',
        button: 'border-orange-500/50 text-orange-400 hover:bg-orange-500/10',
      }
    case 'low':
      return {
        border: 'border-border/50',
        bg: 'bg-surface/30',
        badge: 'bg-border/50 text-text-muted',
        button: 'border-border text-text-secondary hover:bg-surface/50',
      }
  }
}

/* ───────────────── Component ───────────────── */

export function ProactiveActions() {
  const { data: briefing, isLoading: briefingLoading } = useQuery({
    queryKey: ['briefing', 'morning'],
    queryFn: fetchMorningBriefing,
    staleTime: 5 * 60_000,
    retry: 1,
  })

  const { data: people, isLoading: peopleLoading } = useQuery({
    queryKey: ['people', 'graph'],
    queryFn: () => fetchPeopleGraph(20),
    staleTime: 5 * 60_000,
    retry: 1,
  })

  const isLoading = briefingLoading || peopleLoading
  const suggestions = buildSuggestions(briefing, people?.contacts)

  if (isLoading) {
    return (
      <div>
        <h2 className="section-title">⚡ SUGGESTED ACTIONS</h2>
        <LoadingSkeleton lines={4} />
      </div>
    )
  }

  if (suggestions.length === 0) {
    return (
      <div>
        <h2 className="section-title">⚡ SUGGESTED ACTIONS</h2>
        <div className="border border-border/30 border-dashed rounded-lg p-6 text-center">
          <p className="font-mono text-xs text-text-muted">All caught up — no actions suggested</p>
        </div>
      </div>
    )
  }

  return (
    <div>
      <h2 className="section-title">⚡ SUGGESTED ACTIONS</h2>
      <div className="space-y-3">
        {suggestions.map((s) => {
          const style = urgencyStyle(s.urgency)
          return (
            <div
              key={s.id}
              className={`flex items-start gap-4 p-4 rounded-lg border ${style.border} ${style.bg} transition-all hover:scale-[1.005]`}
            >
              <span className="text-xl shrink-0 mt-0.5">{s.icon}</span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <p className="text-sm font-medium text-text-primary truncate">
                    {s.title}
                  </p>
                  <span className={`shrink-0 font-mono text-[9px] tracking-wider px-2 py-0.5 rounded-full ${style.badge}`}>
                    {s.urgency.toUpperCase()}
                  </span>
                </div>
                <p className="text-xs text-text-secondary line-clamp-1">
                  {s.description}
                </p>
              </div>
              {s.actionUrl ? (
                <a
                  href={s.actionUrl}
                  className={`shrink-0 font-mono text-[11px] tracking-wider font-bold px-4 py-2 border rounded transition-colors ${style.button}`}
                >
                  {s.actionLabel}
                </a>
              ) : (
                <button
                  className={`shrink-0 font-mono text-[11px] tracking-wider font-bold px-4 py-2 border rounded transition-colors ${style.button}`}
                >
                  {s.actionLabel}
                </button>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
