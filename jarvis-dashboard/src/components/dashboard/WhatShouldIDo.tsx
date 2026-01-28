import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchMorningBriefing } from '../../api/briefing.ts'
import { apiGet } from '../../api/client.ts'
import { LoadingSkeleton } from '../ui/LoadingSkeleton.tsx'
import { updateLinearTask, createLinearTask, LINEAR_STATES } from '../../api/actions.ts'

/* ───────────────── Types ───────────────── */

interface LinearTask {
  id: string
  identifier: string
  title: string
  state: string
  priority: number
  priorityLabel: string
  dueDate: string | null
  url: string
}

interface LinearTasksResponse {
  tasks: LinearTask[]
  total: number
}

/* ───────────────── Fetcher ───────────────── */

async function fetchLinearTasks(): Promise<LinearTask[]> {
  try {
    const data = await apiGet<LinearTasksResponse>('/api/v2/linear/tasks')
    return data.tasks ?? []
  } catch {
    return []
  }
}

/* ───────────────── Priority helpers ───────────────── */

function priorityBadge(priority: number): { label: string; color: string } {
  switch (priority) {
    case 1: return { label: 'URGENT', color: 'bg-red-500/20 text-red-400 border-red-500/30' }
    case 2: return { label: 'HIGH', color: 'bg-orange-500/20 text-orange-400 border-orange-500/30' }
    case 3: return { label: 'MEDIUM', color: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30' }
    case 4: return { label: 'LOW', color: 'bg-border/50 text-text-muted border-border' }
    default: return { label: 'NONE', color: 'bg-border/30 text-text-muted border-border/50' }
  }
}

function stateIcon(state: string): string {
  switch (state.toLowerCase()) {
    case 'in progress': return '🔵'
    case 'todo': return '⚪'
    case 'done': return '✅'
    default: return '○'
  }
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

export function WhatShouldIDo() {
  const queryClient = useQueryClient()
  
  const { data: tasks, isLoading: tasksLoading } = useQuery({
    queryKey: ['linear', 'tasks'],
    queryFn: fetchLinearTasks,
    staleTime: 2 * 60_000,
    retry: 1,
  })

  const { data: briefing, isLoading: briefingLoading } = useQuery({
    queryKey: ['briefing', 'morning'],
    queryFn: fetchMorningBriefing,
    staleTime: 5 * 60_000,
    retry: 1,
  })

  const isLoading = tasksLoading || briefingLoading
  
  /* ───────────────── Action Handlers ───────────────── */
  
  const handleStartTask = async (taskId: string) => {
    await updateLinearTask({
      task_id: taskId,
      state_id: LINEAR_STATES.IN_PROGRESS,
    })
    // Refetch tasks to update UI
    queryClient.invalidateQueries({ queryKey: ['linear', 'tasks'] })
  }
  
  const handleMarkDone = async (taskId: string) => {
    await updateLinearTask({
      task_id: taskId,
      state_id: LINEAR_STATES.DONE,
    })
    queryClient.invalidateQueries({ queryKey: ['linear', 'tasks'] })
  }
  
  const handleCreateFollowUpTask = async (followUpText: string) => {
    await createLinearTask({
      title: `Follow up: ${followUpText.slice(0, 80)}`,
      description: followUpText,
      priority: 2,
    })
    queryClient.invalidateQueries({ queryKey: ['linear', 'tasks'] })
    queryClient.invalidateQueries({ queryKey: ['briefing', 'morning'] })
  }
  
  // Reminder handler for future use
  // eslint-disable-next-line @typescript-eslint/no-unused-vars

  if (isLoading) {
    return (
      <div>
        <h2 className="section-title">🎯 WHAT SHOULD I DO NOW?</h2>
        <LoadingSkeleton lines={5} />
      </div>
    )
  }

  const linearTasks = tasks ?? []
  const followUps = briefing?.sections.follow_ups_due ?? []
  const dailySuggestions = briefing?.sections.daily3_suggestions ?? []

  // Split tasks into in-progress and todo
  const inProgress = linearTasks.filter((t) => t.state === 'In Progress')
  const todoTasks = linearTasks.filter((t) => t.state === 'Todo')

  // Check for overdue items
  const overdueFollowUps = followUps.filter(
    (f) => f.days_overdue && f.days_overdue > 0
  )

  const hasContent = linearTasks.length > 0 || overdueFollowUps.length > 0

  if (!hasContent) {
    return (
      <div>
        <h2 className="section-title">🎯 WHAT SHOULD I DO NOW?</h2>
        <div className="border border-border/30 border-dashed rounded-lg p-6 text-center">
          <p className="text-2xl mb-2">🧘</p>
          <p className="font-mono text-xs text-text-muted">No tasks in sight — maybe check Linear?</p>
          <a
            href="https://linear.app"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block mt-3 font-mono text-[11px] text-accent hover:text-accent-hover transition-colors"
          >
            OPEN LINEAR →
          </a>
        </div>
      </div>
    )
  }

  return (
    <div>
      <h2 className="section-title">🎯 WHAT SHOULD I DO NOW?</h2>

      <div className="space-y-4">
        {/* Overdue follow-ups — RED ALERT */}
        {overdueFollowUps.length > 0 && (
          <div className="border border-red-500/30 rounded-lg bg-red-500/5 p-4">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-red-400 text-lg">🚨</span>
              <span className="font-mono text-xs font-bold text-red-400 tracking-wider">
                OVERDUE ({overdueFollowUps.length})
              </span>
            </div>
            <div className="space-y-2">
              {overdueFollowUps.map((item, i) => (
                <div key={i} className="flex items-center gap-2 py-1.5">
                  <p className="text-xs text-text-primary flex-1">{item.text}</p>
                  <span className="font-mono text-[10px] text-red-400 shrink-0">
                    {item.days_overdue}d late
                  </span>
                  <ActionButton
                    onClick={() => handleCreateFollowUpTask(item.text)}
                    label="CREATE TASK"
                    variant="primary"
                    icon="+"
                  />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* In-Progress tasks — CURRENT WORK */}
        {inProgress.length > 0 && (
          <div className="border border-blue-500/30 rounded-lg bg-blue-500/5 p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="text-blue-400 text-lg">🔵</span>
                <span className="font-mono text-xs font-bold text-text-primary tracking-wider">
                  IN PROGRESS ({inProgress.length})
                </span>
              </div>
              <a
                href="https://linear.app"
                target="_blank"
                rel="noopener noreferrer"
                className="font-mono text-[10px] text-text-muted hover:text-accent tracking-wider transition-colors"
              >
                LINEAR →
              </a>
            </div>
            <div className="space-y-2">
              {inProgress.map((task) => {
                const badge = priorityBadge(task.priority)
                return (
                  <div
                    key={task.id}
                    className="flex items-center gap-3 py-2 px-3 rounded bg-blue-500/5 hover:bg-blue-500/10 transition-colors group"
                  >
                    <span className="shrink-0">{stateIcon(task.state)}</span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-text-primary font-medium truncate group-hover:text-blue-400 transition-colors">
                        {task.title}
                      </p>
                      <p className="font-mono text-[10px] text-text-muted mt-0.5">
                        {task.identifier}
                      </p>
                    </div>
                    <span className={`shrink-0 font-mono text-[9px] tracking-wider px-2 py-0.5 rounded border ${badge.color}`}>
                      {badge.label}
                    </span>
                    <ActionButton
                      onClick={() => handleMarkDone(task.id)}
                      label="DONE"
                      variant="primary"
                      icon="✓"
                    />
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Todo tasks — UP NEXT */}
        {todoTasks.length > 0 && (
          <div className="border border-border/30 rounded-lg bg-surface/30 p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="text-text-secondary text-lg">📋</span>
                <span className="font-mono text-xs font-bold text-text-primary tracking-wider">
                  UP NEXT ({todoTasks.length})
                </span>
              </div>
            </div>
            <div className="space-y-1.5">
              {todoTasks.slice(0, 8).map((task) => {
                const badge = priorityBadge(task.priority)
                return (
                  <div
                    key={task.id}
                    className="flex items-center gap-3 py-2 px-3 rounded hover:bg-surface/50 transition-colors group"
                  >
                    <span className="shrink-0 text-sm">{stateIcon(task.state)}</span>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-text-secondary group-hover:text-text-primary truncate transition-colors">
                        {task.title}
                      </p>
                    </div>
                    <span className={`shrink-0 font-mono text-[9px] tracking-wider px-2 py-0.5 rounded border ${badge.color}`}>
                      {badge.label}
                    </span>
                    <ActionButton
                      onClick={() => handleStartTask(task.id)}
                      label="START"
                      variant="primary"
                      icon="▶"
                    />
                  </div>
                )
              })}
              {todoTasks.length > 8 && (
                <p className="text-[10px] text-text-muted font-mono pt-1 pl-3">
                  +{todoTasks.length - 8} more in backlog
                </p>
              )}
            </div>
          </div>
        )}

        {/* Daily 3 suggestions from AI */}
        {dailySuggestions.length > 0 && (
          <div className="border border-accent/20 rounded-lg bg-accent/5 p-4">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-accent text-lg">🤖</span>
              <span className="font-mono text-xs font-bold text-text-primary tracking-wider">
                AI SUGGESTS
              </span>
            </div>
            <div className="space-y-2">
              {dailySuggestions.map((s, i) => (
                <div key={i} className="py-1">
                  <p className="text-xs text-text-primary font-medium">{s.priority}</p>
                  <p className="text-[10px] text-text-muted">{s.rationale}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
