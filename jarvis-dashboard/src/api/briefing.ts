import { apiGet } from './client.ts'

/* ───────────────── Types ───────────────── */

export interface CalendarEvent {
  summary: string
  start_time: string
  end_time: string
  location?: string | null
  attendees: string[]
}

export interface EmailHighlight {
  subject: string
  from_name: string
  from_address: string
  snippet: string
  received: string
  priority: string
}

export interface UnfinishedBusiness {
  topic: string
  description: string
  last_seen: string
  suggested_action: string
}

export interface FollowUp {
  text: string
  due_by?: string
  days_overdue?: number
}

export interface PatternAlert {
  pattern_type: string
  key: string
  description: string
  suggested_action: string
}

export interface BriefingSections {
  calendar: CalendarEvent[]
  email_highlights: EmailHighlight[]
  unfinished_business: UnfinishedBusiness[]
  follow_ups_due: FollowUp[]
  pattern_alerts: PatternAlert[]
  daily3_suggestions: Array<{ priority: string; rationale: string }>
}

export interface BriefingData {
  text: string
  sections: BriefingSections
  generated_at: string
}

export interface PeopleContact {
  name: string
  frequency: number
  last_seen: string
  first_seen: string
  days_since_contact: number
  projects: string[]
  topics: string[]
  status: 'active' | 'fading' | 'stale'
  suggested_action: string
  conversation_count: number
}

export interface PeopleGraphResponse {
  contacts: PeopleContact[]
  total_people: number
  active_count: number
  fading_count: number
  stale_count: number
}

export interface Pattern {
  id: string
  pattern_type: string
  pattern_key: string
  description: string
  frequency: number
  suggested_action: string
  status: string
}

export interface PatternsResponse {
  patterns: Pattern[]
  total: number
}

/* ───────────────── Fetchers ───────────────── */

export async function fetchMorningBriefing(): Promise<BriefingData> {
  return apiGet<BriefingData>('/api/v2/briefing/morning')
}

export async function fetchPeopleGraph(limit = 10): Promise<PeopleGraphResponse> {
  return apiGet<PeopleGraphResponse>(`/api/v2/people/graph?limit=${limit}`)
}

export async function fetchPatterns(limit = 10): Promise<PatternsResponse> {
  return apiGet<PatternsResponse>(`/api/v2/patterns?limit=${limit}`)
}
