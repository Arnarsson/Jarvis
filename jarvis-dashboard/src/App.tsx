import { Routes, Route } from 'react-router-dom'
import { Shell } from './components/layout/Shell.tsx'
import { ErrorBoundary } from './components/ErrorBoundary.tsx'
import { Dashboard } from './pages/Dashboard.tsx'
import { SchedulePage } from './pages/SchedulePage.tsx'
import { CommsPage } from './pages/CommsPage.tsx'
import { CommandPage } from './pages/CommandPage.tsx'
import { TasksPage } from './pages/TasksPage.tsx'
import { SystemPage } from './pages/SystemPage.tsx'
import { MemoryPage } from './pages/MemoryPage.tsx'
import { Daily3Page } from './pages/Daily3Page.tsx'
import { FocusPage } from './pages/FocusPage.tsx'
import { CatchUpPage } from './pages/CatchUpPage.tsx'

function PageBoundary({ children }: { children: React.ReactNode }) {
  return (
    <ErrorBoundary
      fallback={
        <div className="flex items-center justify-center min-h-[50vh]">
          <div className="text-center space-y-3">
            <p className="font-mono text-sm text-text-secondary">This page encountered an error</p>
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 border border-border text-text-primary font-mono text-xs tracking-wider hover:border-accent hover:text-accent transition-colors"
            >
              RELOAD
            </button>
          </div>
        </div>
      }
    >
      {children}
    </ErrorBoundary>
  )
}

export default function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<PageBoundary><Dashboard /></PageBoundary>} />
        <Route path="/memory" element={<PageBoundary><MemoryPage /></PageBoundary>} />
        <Route path="/schedule" element={<PageBoundary><SchedulePage /></PageBoundary>} />
        <Route path="/comms" element={<PageBoundary><CommsPage /></PageBoundary>} />
        <Route path="/tasks" element={<PageBoundary><TasksPage /></PageBoundary>} />
        <Route path="/command" element={<PageBoundary><CommandPage /></PageBoundary>} />
        <Route path="/system" element={<PageBoundary><SystemPage /></PageBoundary>} />
        <Route path="/daily3" element={<PageBoundary><Daily3Page /></PageBoundary>} />
        <Route path="/focus" element={<FocusPage />} />
        <Route path="/catchup" element={<PageBoundary><CatchUpPage /></PageBoundary>} />
      </Routes>
    </Shell>
  )
}
