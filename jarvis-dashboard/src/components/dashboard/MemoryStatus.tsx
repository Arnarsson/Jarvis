import { SectionHeader } from '../ui/SectionHeader.tsx'
import { StatusDot } from '../ui/StatusDot.tsx'

export function MemoryStatus() {
  return (
    <div className="rounded-lg border border-border bg-surface p-5">
      <SectionHeader title="Memory Status" />

      <div className="space-y-4">
        {/* Vector count */}
        <div className="flex items-center justify-between">
          <span className="text-sm text-text-secondary">Vector count</span>
          <span className="font-mono text-sm text-text-primary">3,849</span>
        </div>

        {/* Conversations indexed */}
        <div className="flex items-center justify-between">
          <span className="text-sm text-text-secondary">
            Conversations indexed
          </span>
          <span className="font-mono text-sm text-text-primary">5,040+</span>
        </div>

        {/* Divider */}
        <div className="border-t border-border" />

        {/* Capture agent status */}
        <div className="flex items-center justify-between">
          <span className="text-sm text-text-secondary">Capture agent</span>
          <div className="flex items-center gap-2">
            <StatusDot status="operational" />
            <span className="text-sm text-success">Connected</span>
          </div>
        </div>

        {/* Last capture */}
        <div className="flex items-center justify-between">
          <span className="text-sm text-text-secondary">Last capture</span>
          <span className="font-mono text-xs text-text-secondary">
            {new Date().toLocaleTimeString('en-US', {
              hour12: false,
              hour: '2-digit',
              minute: '2-digit',
            })}
          </span>
        </div>
      </div>
    </div>
  )
}
