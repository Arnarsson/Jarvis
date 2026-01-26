import { useLocation, Link } from 'react-router-dom'
import { useAppStore } from '../../stores/app.ts'
import { useEffect } from 'react'
import { fetchHealth } from '../../api/health.ts'

const navItems = [
  { path: '/', label: 'OVERVIEW' },
  { path: '/schedule', label: 'SCHEDULE' },
  { path: '/comms', label: 'COMMS' },
  { path: '/tasks', label: 'TASKS' },
  { path: '/command', label: 'COMMAND' },
  { path: '/system', label: 'SYSTEM' },
]

const mobileNavItems = [
  { path: '/', label: 'Overview', icon: 'grid' },
  { path: '/schedule', label: 'Schedule', icon: 'calendar' },
  { path: '/comms', label: 'Comms', icon: 'mail' },
  { path: '/command', label: 'Command', icon: 'terminal' },
]

function NavIcon({ icon }: { icon: string }) {
  const size = 18
  const props = { width: size, height: size, fill: 'none', stroke: 'currentColor', strokeWidth: 1.5 }

  switch (icon) {
    case 'grid':
      return (
        <svg {...props} viewBox="0 0 24 24">
          <rect x="3" y="3" width="7" height="7" rx="1" />
          <rect x="14" y="3" width="7" height="7" rx="1" />
          <rect x="3" y="14" width="7" height="7" rx="1" />
          <rect x="14" y="14" width="7" height="7" rx="1" />
        </svg>
      )
    case 'calendar':
      return (
        <svg {...props} viewBox="0 0 24 24">
          <rect x="3" y="4" width="18" height="18" rx="2" />
          <path d="M16 2v4M8 2v4M3 10h18" />
        </svg>
      )
    case 'mail':
      return (
        <svg {...props} viewBox="0 0 24 24">
          <rect x="2" y="4" width="20" height="16" rx="2" />
          <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
        </svg>
      )
    case 'terminal':
      return (
        <svg {...props} viewBox="0 0 24 24">
          <polyline points="4 17 10 11 4 5" />
          <line x1="12" y1="19" x2="20" y2="19" />
        </svg>
      )
    default:
      return null
  }
}

function SidebarContent({ onNavClick }: { onNavClick?: () => void }) {
  const location = useLocation()
  const { connectionStatus, theme, toggleTheme } = useAppStore()

  return (
    <>
      {/* Logo / Branding */}
      <div className="px-6 pt-8 pb-8">
        <h1 className="font-mono text-sm font-bold text-text-primary tracking-widest">
          E.A./SYSTEM
        </h1>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-6 space-y-1">
        {navItems.map((item) => {
          const isActive = location.pathname === item.path
          return (
            <Link
              key={item.path}
              to={item.path}
              onClick={onNavClick}
              className={`block py-2 text-[13px] font-mono tracking-wider transition-colors ${
                isActive
                  ? 'text-text-primary'
                  : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              {isActive && <span className="mr-2">&rarr;</span>}
              {item.label}
            </Link>
          )
        })}
      </nav>

      {/* Status footer */}
      <div className="px-6 pb-6 space-y-3">
        <div className="border-t border-border pt-4" />

        {/* Connection status */}
        <div className="space-y-0.5">
          <div className="flex items-center gap-2">
            <span
              className={`inline-block h-2 w-2 rounded-full ${
                connectionStatus === 'online'
                  ? 'bg-success animate-pulse-dot'
                  : 'bg-text-muted'
              }`}
            />
            <span className="font-mono text-[11px] tracking-wider text-text-secondary uppercase">
              {connectionStatus === 'online' ? 'ONLINE' : 'OFFLINE'}
            </span>
          </div>
          <p className="text-[12px] text-text-secondary pl-4">Sven Arnarsson</p>
        </div>

        {/* Theme toggle */}
        <button
          onClick={toggleTheme}
          className="w-full mt-2 flex items-center justify-center gap-2 rounded border border-border py-2 text-[11px] font-mono tracking-wider text-text-secondary hover:text-text-primary hover:border-border-light transition-colors"
        >
          <span className="text-xs">&loz;</span>
          {theme === 'dark' ? 'LIGHT' : 'DARK'}
        </button>
      </div>
    </>
  )
}

export function Shell({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  const { sidebarOpen, setSidebarOpen, setConnectionStatus } = useAppStore()

  // Ping server health to set connection status
  useEffect(() => {
    let mounted = true
    const check = async () => {
      try {
        await fetchHealth()
        if (mounted) setConnectionStatus('online')
      } catch {
        if (mounted) setConnectionStatus('offline')
      }
    }
    check()
    const interval = setInterval(check, 30_000)
    return () => { mounted = false; clearInterval(interval) }
  }, [setConnectionStatus])

  return (
    <div className="flex h-screen bg-bg">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Desktop sidebar — always visible on lg+ */}
      <aside className="hidden lg:flex w-[192px] shrink-0 flex-col bg-surface border-r border-border">
        <SidebarContent />
      </aside>

      {/* Mobile sidebar — slide-in drawer */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-[192px] flex-col bg-surface border-r border-border transition-transform duration-200 lg:hidden ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <SidebarContent onNavClick={() => setSidebarOpen(false)} />
      </aside>

      {/* Main content */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Mobile top bar */}
        <header className="flex h-14 items-center gap-4 border-b border-border px-4 lg:hidden">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="text-text-secondary hover:text-text-primary"
            aria-label="Toggle menu"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <span className="font-mono text-xs font-bold text-text-primary tracking-widest">
            E.A./SYSTEM
          </span>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto px-6 py-6 lg:px-10 lg:py-8 pb-20 lg:pb-8">
          {children}
        </main>

        {/* Mobile bottom nav — hidden on desktop */}
        <nav className="fixed bottom-0 left-0 right-0 z-30 flex h-16 items-center justify-around border-t border-border bg-surface lg:hidden">
          {mobileNavItems.map((item) => {
            const isActive = location.pathname === item.path
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex flex-col items-center gap-1 px-3 py-2 transition-colors ${
                  isActive ? 'text-accent' : 'text-text-secondary'
                }`}
              >
                <NavIcon icon={item.icon} />
                <span className="text-[10px] font-mono tracking-wider">{item.label.toUpperCase()}</span>
              </Link>
            )
          })}
        </nav>
      </div>
    </div>
  )
}
