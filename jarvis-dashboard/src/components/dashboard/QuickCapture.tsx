import { useState, useEffect, useCallback, useRef } from 'react'
import { apiPost } from '../../api/client.ts'

export function QuickCapture() {
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [toast, setToast] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  // Ctrl+K shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        setOpen((prev) => !prev)
      }
      if (e.key === 'Escape' && open) {
        setOpen(false)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open])

  // Focus input when modal opens
  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [open])

  const capture = useCallback(async () => {
    const trimmed = text.trim()
    if (!trimmed) return

    // Save to localStorage
    try {
      const existing = JSON.parse(localStorage.getItem('jarvis-captures') || '[]')
      existing.push({ text: trimmed, source: 'quick-capture', ts: Date.now() })
      localStorage.setItem('jarvis-captures', JSON.stringify(existing))
    } catch (err) {
      console.error('Failed to save capture to localStorage:', err)
    }

    // POST to API (fire and forget)
    apiPost('/api/captures/', { text: trimmed, source: 'quick-capture' }).catch(() => {})

    setText('')
    setOpen(false)
    setToast(true)
    setTimeout(() => setToast(false), 2000)
  }, [text])

  return (
    <>
      {/* FAB button */}
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-20 right-5 lg:bottom-8 lg:right-8 z-50 w-14 h-14 rounded-full flex items-center justify-center shadow-lg transition-all hover:scale-110 active:scale-95"
        style={{ backgroundColor: '#DC2626' }}
        title="Quick Capture (Ctrl+K)"
      >
        <svg
          className="w-6 h-6 text-white"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2.5}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
        </svg>
      </button>

      {/* Modal overlay */}
      {open && (
        <div
          className="fixed inset-0 z-[90] flex items-start justify-center pt-[20vh] bg-black/70 backdrop-blur-sm"
          onClick={(e) => {
            if (e.target === e.currentTarget) setOpen(false)
          }}
        >
          <div className="w-full max-w-lg mx-4 bg-surface border border-border rounded-lg overflow-hidden shadow-2xl">
            <div className="p-1">
              <input
                ref={inputRef}
                type="text"
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') capture()
                }}
                placeholder="Quick thought..."
                className="w-full bg-transparent px-4 py-4 font-mono text-base text-text-primary placeholder:text-text-muted focus:outline-none"
              />
            </div>
            <div className="flex items-center justify-between px-4 py-2 border-t border-border">
              <span className="font-mono text-[10px] text-text-muted tracking-wider">
                ENTER TO CAPTURE · ESC TO CLOSE
              </span>
              <button
                onClick={capture}
                disabled={!text.trim()}
                className="font-mono text-xs tracking-wider px-4 py-1.5 rounded bg-accent text-white disabled:opacity-30 transition-all"
              >
                CAPTURE
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-24 right-5 lg:bottom-24 lg:right-8 z-[100] animate-fade-in">
          <div className="bg-surface border border-green-500/30 rounded-lg px-4 py-2 shadow-lg">
            <span className="font-mono text-sm text-green-400 tracking-wider">
              Captured ✓
            </span>
          </div>
        </div>
      )}
    </>
  )
}
