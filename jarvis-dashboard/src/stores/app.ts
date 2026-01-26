import { create } from 'zustand'

type SystemStatus = 'operational' | 'degraded' | 'down'
type Theme = 'dark' | 'light'
type ConnectionStatus = 'online' | 'offline'

interface AppState {
  userName: string
  systemStatus: SystemStatus
  sidebarOpen: boolean
  theme: Theme
  connectionStatus: ConnectionStatus
  setUserName: (name: string) => void
  setSystemStatus: (status: SystemStatus) => void
  toggleSidebar: () => void
  setSidebarOpen: (open: boolean) => void
  toggleTheme: () => void
  setConnectionStatus: (status: ConnectionStatus) => void
}

export const useAppStore = create<AppState>((set) => ({
  userName: 'Sven Arnarsson',
  systemStatus: 'operational',
  sidebarOpen: false,
  theme: 'dark',
  connectionStatus: 'online',
  setUserName: (name) => set({ userName: name }),
  setSystemStatus: (status) => set({ systemStatus: status }),
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  toggleTheme: () =>
    set((state) => ({ theme: state.theme === 'dark' ? 'light' : 'dark' })),
  setConnectionStatus: (status) => set({ connectionStatus: status }),
}))
