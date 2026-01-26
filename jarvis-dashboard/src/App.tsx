import { Routes, Route } from 'react-router-dom'
import { Shell } from './components/layout/Shell.tsx'
import { Dashboard } from './pages/Dashboard.tsx'

function PlaceholderPage({ title }: { title: string }) {
  return (
    <div>
      <h3 className="section-title">{title}</h3>
      <p className="text-sm text-text-secondary">
        {title} module coming soon.
      </p>
    </div>
  )
}

export default function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/schedule" element={<PlaceholderPage title="Schedule" />} />
        <Route path="/comms" element={<PlaceholderPage title="Communications" />} />
        <Route path="/tasks" element={<PlaceholderPage title="Tasks" />} />
        <Route path="/command" element={<PlaceholderPage title="Command" />} />
        <Route path="/system" element={<PlaceholderPage title="System" />} />
      </Routes>
    </Shell>
  )
}
