import { useState } from 'react'
import { BrainTimelinePage } from './BrainTimelinePage.tsx'
import { MemoryPage as MemoryPageContent } from './MemoryPage.tsx'
import { PatternsPage as PatternsPageContent } from './PatternsPage.tsx'

const tabs = [
  { id: 'timeline', label: '🧠 TIMELINE' },
  { id: 'memory', label: '💾 MEMORY' },
  { id: 'patterns', label: '🔍 PATTERNS' },
] as const

type TabId = typeof tabs[number]['id']

export default function BrainPage() {
  const [activeTab, setActiveTab] = useState<TabId>('timeline')

  return (
    <div>
      {/* Tab Bar */}
      <div className="flex gap-1 mb-6 border-b border-border">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2.5 text-xs font-mono tracking-wider transition-colors border-b-2 -mb-px ${
              activeTab === tab.id
                ? 'text-accent border-accent'
                : 'text-text-secondary border-transparent hover:text-text-primary hover:border-border-light'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'timeline' && <BrainTimelinePage />}
      {activeTab === 'memory' && <MemoryPageContent />}
      {activeTab === 'patterns' && <PatternsPageContent />}
    </div>
  )
}
