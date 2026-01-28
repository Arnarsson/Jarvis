import { apiGet } from './client.ts'

export interface LinearTask {
  id: string
  identifier: string
  title: string
  state: string
  priority: number
  priorityLabel: string
  dueDate: string | null
  url: string
}

export interface LinearTasksResponse {
  tasks: LinearTask[]
  total: number
}

/**
 * Fetch Linear tasks from the Jarvis backend proxy.
 * Falls back to empty array if the endpoint doesn't exist yet.
 */
export async function fetchLinearTasks(): Promise<LinearTask[]> {
  try {
    const data = await apiGet<LinearTasksResponse>('/api/v2/linear/tasks')
    return data.tasks ?? []
  } catch {
    // Backend doesn't have this endpoint yet — return empty
    return []
  }
}
