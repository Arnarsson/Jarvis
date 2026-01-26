import { useQuery } from '@tanstack/react-query'
import { fetchUpcomingMeetings } from '../api/calendar.ts'
import type { CalendarEvent } from '../api/calendar.ts'

export function useAgenda() {
  return useQuery<CalendarEvent[]>({
    queryKey: ['calendar', 'upcoming'],
    queryFn: fetchUpcomingMeetings,
    refetchInterval: 60_000,
  })
}
