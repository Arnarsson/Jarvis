import { HeroHeader } from '../components/dashboard/HeroHeader.tsx'
import { MomentumTracker } from '../components/dashboard/MomentumTracker.tsx'
import { SmartSummary } from '../components/dashboard/SmartSummary.tsx'
import { StatsGrid } from '../components/dashboard/StatsGrid.tsx'
import { AgendaList } from '../components/dashboard/AgendaList.tsx'
import { PendingLogic } from '../components/dashboard/PendingLogic.tsx'
import { Communications } from '../components/dashboard/Communications.tsx'
import { ActiveTracks } from '../components/dashboard/ActiveTracks.tsx'

export function Dashboard() {
  return (
    <div>
      <HeroHeader />
      <MomentumTracker />
      <SmartSummary />
      <StatsGrid />

      {/* Two-column: Agenda + Pending Logic */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-x-12 gap-y-10 mb-10">
        <AgendaList />
        <PendingLogic />
      </div>

      {/* Two-column: Communications + Active Tracks */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-x-12 gap-y-10">
        <Communications />
        <ActiveTracks />
      </div>
    </div>
  )
}
