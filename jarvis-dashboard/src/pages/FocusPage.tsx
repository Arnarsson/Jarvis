import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'

function getTodayKey(): string {
  const d = new Date()
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `jarvis-daily3-${yyyy}-${mm}-${dd}`
}

function getTopTask(): string {
  try {
    const raw = localStorage.getItem(getTodayKey())
    if (raw) {
      const items = JSON.parse(raw)
      if (items.length > 0 && !items[0].done) return items[0].text
      // Find first incomplete
      const incomplete = items.find((i: { done: boolean }) => !i.done)
      if (incomplete) return incomplete.text
    }
  } catch {}
  return 'Set your Daily 3 first'
}

const DEFAULT_MINUTES = 25

export function FocusPage() {
  const navigate = useNavigate()
  const [task] = useState(getTopTask)
  const [totalSeconds, setTotalSeconds] = useState(DEFAULT_MINUTES * 60)
  const [remaining, setRemaining] = useState(DEFAULT_MINUTES * 60)
  const [running, setRunning] = useState(false)
  const [finished, setFinished] = useState(false)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // ESC to exit
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') navigate('/')
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [navigate])

  // Timer logic
  useEffect(() => {
    if (running && remaining > 0) {
      intervalRef.current = setInterval(() => {
        setRemaining((prev) => {
          if (prev <= 1) {
            setRunning(false)
            setFinished(true)
            return 0
          }
          return prev - 1
        })
      }, 1000)
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [running, remaining])

  const start = useCallback(() => {
    if (finished) return
    setRunning(true)
  }, [finished])

  const pause = useCallback(() => {
    setRunning(false)
  }, [])

  const reset = useCallback(() => {
    setRunning(false)
    setFinished(false)
    setRemaining(totalSeconds)
  }, [totalSeconds])

  const adjustTime = (delta: number) => {
    if (running) return
    const newTotal = Math.max(60, totalSeconds + delta * 60)
    setTotalSeconds(newTotal)
    setRemaining(newTotal)
    setFinished(false)
  }

  const minutes = Math.floor(remaining / 60)
  const seconds = remaining % 60

  return (
    <div
      className="fixed inset-0 z-[100] flex flex-col items-center justify-center"
      style={{ backgroundColor: '#000000' }}
    >
      {/* Task name */}
      <div className="mb-12 px-8 text-center">
        <p className="font-mono text-xs tracking-[0.3em] text-neutral-500 mb-4 uppercase">
          FOCUS MODE
        </p>
        <h1 className="font-mono text-2xl md:text-3xl font-bold text-white tracking-wide max-w-lg">
          {task}
        </h1>
      </div>

      {/* Timer */}
      <div className={`mb-12 ${finished ? 'animate-pulse' : ''}`}>
        <div className="flex items-center gap-2">
          {!running && !finished && (
            <button
              onClick={() => adjustTime(-5)}
              className="font-mono text-neutral-600 hover:text-neutral-400 text-lg px-2 transition-colors"
              title="−5 min"
            >
              −
            </button>
          )}
          <span
            className={`font-mono text-7xl md:text-8xl font-bold tabular-nums ${
              finished ? 'text-green-400' : remaining <= 60 ? 'text-red-500' : 'text-white'
            }`}
          >
            {String(minutes).padStart(2, '0')}:{String(seconds).padStart(2, '0')}
          </span>
          {!running && !finished && (
            <button
              onClick={() => adjustTime(5)}
              className="font-mono text-neutral-600 hover:text-neutral-400 text-lg px-2 transition-colors"
              title="+5 min"
            >
              +
            </button>
          )}
        </div>
      </div>

      {/* Finished state */}
      {finished && (
        <p className="font-mono text-lg text-green-400/80 tracking-wider mb-8 animate-pulse">
          Take a break. You earned it.
        </p>
      )}

      {/* Controls */}
      <div className="flex items-center gap-4">
        {!running && !finished && (
          <button
            onClick={start}
            className="font-mono text-sm tracking-wider px-8 py-3 rounded bg-white text-black hover:bg-neutral-200 transition-colors"
          >
            START
          </button>
        )}
        {running && (
          <button
            onClick={pause}
            className="font-mono text-sm tracking-wider px-8 py-3 rounded border border-neutral-600 text-neutral-300 hover:border-neutral-400 transition-colors"
          >
            PAUSE
          </button>
        )}
        {(remaining < totalSeconds || finished) && (
          <button
            onClick={reset}
            className="font-mono text-sm tracking-wider px-8 py-3 rounded border border-neutral-700 text-neutral-500 hover:text-neutral-300 hover:border-neutral-500 transition-colors"
          >
            RESET
          </button>
        )}
        <button
          onClick={() => navigate('/')}
          className="font-mono text-sm tracking-wider px-8 py-3 rounded border border-neutral-700 text-neutral-500 hover:text-neutral-300 hover:border-neutral-500 transition-colors"
        >
          DONE
        </button>
      </div>

      {/* Subtle hint */}
      <p className="absolute bottom-6 font-mono text-[10px] text-neutral-700 tracking-wider">
        ESC TO EXIT
      </p>
    </div>
  )
}
