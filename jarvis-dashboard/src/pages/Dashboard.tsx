import { HeroHeader } from '../components/dashboard/HeroHeader.tsx'
import { MomentumTracker } from '../components/dashboard/MomentumTracker.tsx'
import { SmartSummary } from '../components/dashboard/SmartSummary.tsx'
import { StatsGrid } from '../components/dashboard/StatsGrid.tsx'
import { AgendaList } from '../components/dashboard/AgendaList.tsx'
import { PendingLogic } from '../components/dashboard/PendingLogic.tsx'
import { Communications } from '../components/dashboard/Communications.tsx'
import { ActiveTracks } from '../components/dashboard/ActiveTracks.tsx'
import { ErrorBoundary } from '../components/ErrorBoundary.tsx'

function WidgetFallback({ name }: { name: string }) {
  return (
    <div className="border border-border/30 border-dashed rounded p-4 text-center">
      <p className="font-mono text-xs text-text-muted">{name} — failed to load</p>
    </div>
  )
}

export function Dashboard() {
  return (
    <div>
      <ErrorBoundary fallback={<WidgetFallback name="Header" />}>
        <HeroHeader />
      </ErrorBoundary>
      <ErrorBoundary fallback={<WidgetFallback name="Momentum" />}>
        <MomentumTracker />
      </ErrorBoundary>
      <ErrorBoundary fallback={<WidgetFallback name="Summary" />}>
        <SmartSummary />
      </ErrorBoundary>
      <ErrorBoundary fallback={<WidgetFallback name="Stats" />}>
        <StatsGrid />
      </ErrorBoundary>

      {/* Two-column: Agenda + Pending Logic */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-x-12 gap-y-10 mb-10">
        <ErrorBoundary fallback={<WidgetFallback name="Agenda" />}>
          <AgendaList />
        </ErrorBoundary>
        <ErrorBoundary fallback={<WidgetFallback name="Pending Logic" />}>
          <PendingLogic />
        </ErrorBoundary>
      </div>

      {/* Two-column: Communications + Active Tracks */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-x-12 gap-y-10">
        <ErrorBoundary fallback={<WidgetFallback name="Communications" />}>
          <Communications />
        </ErrorBoundary>
        <ErrorBoundary fallback={<WidgetFallback name="Active Tracks" />}>
          <ActiveTracks />
        </ErrorBoundary>
      </div>
    </div>
  )
}
