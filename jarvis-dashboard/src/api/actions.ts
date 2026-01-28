/**
 * Action Buttons API Client
 * Handles 1-click executable actions from command center
 */

import { apiPost } from './client.ts'

/* ───────────────── Types ───────────────── */

export interface DraftEmailRequest {
  to_email: string
  to_name: string
  subject: string
  context?: string
  reply_type?: 'professional' | 'friendly' | 'brief' | 'detailed'
}

export interface DraftEmailResponse {
  success: boolean
  gmail_url: string
  draft_body: string
  action: 'open_gmail'
}

export interface CreateLinearTaskRequest {
  title: string
  description?: string
  priority?: number
  team_id?: string
  state_id?: string
}

export interface LinearTaskResponse {
  success: boolean
  task: {
    id: string
    identifier: string
    title: string
    url?: string
    state: string
    priority?: number
  }
}

export interface UpdateLinearTaskRequest {
  task_id: string
  state_id?: string
  priority?: number
}

export interface SendReminderRequest {
  to_email: string
  to_name: string
  subject: string
  reminder_text: string
}

/* ───────────────── API Functions ───────────────── */

/**
 * Generate a draft email reply and open Gmail compose window
 */
export async function draftEmail(request: DraftEmailRequest): Promise<DraftEmailResponse> {
  const response = await apiPost<DraftEmailResponse>('/api/v2/actions/draft-email', request)
  
  // Open Gmail in new tab
  if (response.gmail_url) {
    window.open(response.gmail_url, '_blank', 'noopener,noreferrer')
  }
  
  return response
}

/**
 * Create a new Linear task
 */
export async function createLinearTask(request: CreateLinearTaskRequest): Promise<LinearTaskResponse> {
  return await apiPost<LinearTaskResponse>('/api/v2/actions/create-linear-task', request)
}

/**
 * Update an existing Linear task (change state, priority, etc.)
 */
export async function updateLinearTask(request: UpdateLinearTaskRequest): Promise<LinearTaskResponse> {
  return await apiPost<LinearTaskResponse>('/api/v2/actions/update-linear-task', request)
}

/**
 * Send a reminder email (opens Gmail compose window)
 */
export async function sendReminder(request: SendReminderRequest): Promise<DraftEmailResponse> {
  const response = await apiPost<DraftEmailResponse>('/api/v2/actions/send-reminder', request)
  
  // Open Gmail in new tab
  if (response.gmail_url) {
    window.open(response.gmail_url, '_blank', 'noopener,noreferrer')
  }
  
  return response
}

/* ───────────────── Linear State IDs ───────────────── */

export const LINEAR_STATES = {
  TODO: '7ae2f220-6394-4117-97f3-3e10f58c4e47',
  IN_PROGRESS: '941943ae-fa4e-4fac-96cb-a4a8a682999b',
  DONE: '3ae46e12-b4dc-4d19-b1b9-fafd7a4eb88a',
} as const
