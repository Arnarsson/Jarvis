import { HeroHeader } from '../components/dashboard/HeroHeader.tsx'
import { CommandCenter } from '../components/dashboard/CommandCenter.tsx'
import { ErrorBoundary } from '../components/ErrorBoundary.tsx'

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// DASHBOARD — Command Center Home (No Guilt Stats)
// Replaced anxiety-inducing counters with actionable sections
// Task: 7-293 (P0) — Remove "777 inbound" and "00 tasks" guilt UI
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function WidgetFallback({ name }: { name: string }) {
  return (
    <div className="border border-border/30 border-dashed rounded p-4 text-center">
      <p className="font-mono text-xs text-text-muted">{name} — failed to load</p>
    </div>
  )
}

export function Dashboard() {
  return (
    <div className="max-w-6xl mx-auto">
      {/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
          HEADER — Date, time, system status
         ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */}
      <ErrorBoundary fallback={<WidgetFallback name="Header" />}>
        <HeroHeader />
      </ErrorBoundary>

      {/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
          COMMAND CENTER — Actionable dashboard (replaces guilt stats)
          
          Sections:
          1. RESUME — Where you left off
          2. TODAY'S 3 — Daily priorities  
          3. OPEN LOOPS — Commitments & waiting-on
          4. NEXT MEETING — Prep brief
          5. FOCUS INBOX — Priority triage
         ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */}
      <ErrorBoundary fallback={<WidgetFallback name="Command Center" />}>
        <CommandCenter />
      </ErrorBoundary>
    </div>
  )
}
