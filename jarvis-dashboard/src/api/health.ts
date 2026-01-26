import { apiGet, apiGetText } from './client.ts'

export interface HealthResponse {
  status: string
  version?: string
}

export interface WorkflowSuggestion {
  id: string
  type: string
  title: string
  priority: string
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
    return await apiGet<WorkflowSuggestion[]>('/api/workflow/suggestions')
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
