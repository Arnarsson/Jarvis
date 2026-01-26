import { apiGet } from './client.ts'

export interface CalendarEvent {
  id: string
  summary: string
  start_time: string
  end_time: string
  location?: string
  meet_link?: string
}

export async function fetchUpcomingMeetings(): Promise<CalendarEvent[]> {
  return apiGet<CalendarEvent[]>('/api/calendar/events/upcoming')
}
