import { apiGet } from './client.ts'

export interface CalendarEvent {
  id: string
  summary: string
  start: string
  end: string
  location?: string | null
  description?: string | null
  meeting_link?: string | null
  attendees: string[]
}

interface CalendarResponse {
  events: CalendarEvent[]
  count: number
}

export async function fetchUpcomingMeetings(): Promise<CalendarEvent[]> {
  try {
    const data = await apiGet<CalendarResponse>('/api/calendar/events/upcoming')
    return data.events ?? []
  } catch {
    return []
  }
}
