import { Routes, Route } from 'react-router-dom'
import { Shell } from './components/layout/Shell.tsx'
import { Dashboard } from './pages/Dashboard.tsx'
import { SchedulePage } from './pages/SchedulePage.tsx'
import { CommsPage } from './pages/CommsPage.tsx'
import { CommandPage } from './pages/CommandPage.tsx'
import { TasksPage } from './pages/TasksPage.tsx'
import { SystemPage } from './pages/SystemPage.tsx'
import { CatchUpPage } from './pages/CatchUpPage.tsx'

export default function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/schedule" element={<SchedulePage />} />
        <Route path="/comms" element={<CommsPage />} />
        <Route path="/tasks" element={<TasksPage />} />
        <Route path="/command" element={<CommandPage />} />
        <Route path="/catchup" element={<CatchUpPage />} />
        <Route path="/system" element={<SystemPage />} />
      </Routes>
    </Shell>
  )
}
