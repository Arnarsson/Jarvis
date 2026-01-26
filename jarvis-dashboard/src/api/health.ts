import { apiGet, apiGetText } from './client.ts'

export interface HealthResponse {
  status: string
  version?: string
}

export interface WorkflowSuggestion {
  id: string
  name: string
  description: string
  pattern_type: string
  trigger_description: string
  action_description: string
  confidence: number
  similar_captures: unknown[]
}

interface WorkflowSuggestionsResponse {
  suggestions: WorkflowSuggestion[]
  total: number
}

export interface EmailAuthStatus {
  authenticated: boolean
  email?: string
}

export async function fetchHealth(): Promise<HealthResponse> {
  return apiGet<HealthResponse>('/health/')
}

export async function fetchStats(): Promise<string> {
  return apiGetText('/api/web/stats')
}

export async function fetchWorkflowSuggestions(): Promise<WorkflowSuggestion[]> {
  try {
    const data = await apiGet<WorkflowSuggestionsResponse>('/api/workflow/suggestions')
    return data.suggestions
  } catch {
    return []
  }
}

export async function fetchEmailAuthStatus(): Promise<EmailAuthStatus> {
  try {
    return await apiGet<EmailAuthStatus>('/api/email/auth/status')
  } catch {
    return { authenticated: false }
  }
}
