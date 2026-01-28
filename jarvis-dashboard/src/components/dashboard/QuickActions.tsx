import { useNavigate } from 'react-router-dom'

interface QuickAction {
  emoji: string
  label: string
  path: string
  hotkey?: string
}

const actions: QuickAction[] = [
  { emoji: '⚡', label: 'New Capture', path: '/capture', hotkey: 'Ctrl+K' },
  { emoji: '📅', label: 'View Schedule', path: '/schedule' },
  { emoji: '🧠', label: 'Brain Search', path: '/brain' },
  { emoji: '🎯', label: 'Daily 3', path: '/daily3' },
]

export function QuickActions() {
  const navigate = useNavigate()

  return (
    <div className="mb-10">
      <h3 className="section-title">QUICK ACTIONS</h3>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {actions.map((action) => (
          <button
            key={action.label}
            onClick={() => navigate(action.path)}
            className="flex items-center gap-2.5 px-4 py-3 border border-border/40 rounded bg-surface/20 hover:bg-surface/50 hover:border-accent/50 transition-all text-left group"
          >
            <span className="text-base group-hover:scale-110 transition-transform">
              {action.emoji}
            </span>
            <div className="flex-1 min-w-0">
              <span className="font-mono text-[11px] text-text-secondary group-hover:text-text-primary tracking-wide transition-colors block">
                {action.label}
              </span>
              {action.hotkey && (
                <span className="font-mono text-[9px] text-text-muted">
                  {action.hotkey}
                </span>
              )}
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}
