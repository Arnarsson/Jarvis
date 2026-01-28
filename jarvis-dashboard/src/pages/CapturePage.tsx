import { useState, useEffect, useRef, useCallback } from 'react'
import type { FormEvent } from 'react'
import { apiGet, apiPost } from '../api/client.ts'

/* ───────────────────────── Types ───────────────────────── */

interface QuickCapture {
  id: string
  text: string
  tags: string[]
  created_at: string
  source: string
}

interface QuickCapturesResponse {
  captures: QuickCapture[]
  total: number
}

interface MemoryResult {
  conversation_id: string
  title: string
  snippet: string
  topics?: string[]
  people?: string[]
  projects?: string[]
}

interface MemorySearchResponse {
  results: MemoryResult[]
}

interface ConstellationNode {
  id: string
  x: number
  y: number
  vx: number
  vy: number
  radius: number
  capture: QuickCapture
  connections: number
  glowPhase: number
}

interface ConstellationEdge {
  source: number
  target: number
  strength: number
}

/* ───────────────────────── Helpers ───────────────────────── */

function timeAgo(isoDate: string): string {
  try {
    const now = Date.now()
    const then = new Date(isoDate).getTime()
    const diffMs = now - then
    const diffMin = Math.floor(diffMs / 60000)
    const diffHr = Math.floor(diffMs / 3600000)
    const diffDay = Math.floor(diffMs / 86400000)
    if (diffMin < 1) return 'just now'
    if (diffMin < 60) return `${diffMin}m ago`
    if (diffHr < 24) return `${diffHr}h ago`
    if (diffDay === 1) return 'yesterday'
    if (diffDay < 7) return `${diffDay}d ago`
    const d = new Date(isoDate)
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  } catch {
    return ''
  }
}

function formatFullDate(isoDate: string): string {
  try {
    const d = new Date(isoDate)
    return d.toLocaleDateString('en-US', {
      month: 'long', day: 'numeric', year: 'numeric',
      hour: '2-digit', minute: '2-digit'
    })
  } catch {
    return ''
  }
}

function getSourceConfig(source: string) {
  const configs: Record<string, { label: string; emoji: string; color: string; bg: string; border: string; hex: string }> = {
    manual:   { label: 'QUICK CAPTURE', emoji: '⚡', color: 'text-blue-400',    bg: 'bg-blue-500/10',    border: 'border-blue-500/30',    hex: '#60a5fa' },
    voice:    { label: 'VOICE',         emoji: '🎙️', color: 'text-purple-400',  bg: 'bg-purple-500/10',  border: 'border-purple-500/30',  hex: '#c084fc' },
    telegram: { label: 'TELEGRAM',      emoji: '🤖', color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', hex: '#34d399' },
    eureka:   { label: 'EUREKA',        emoji: '🤖', color: 'text-amber-400',   bg: 'bg-amber-500/10',   border: 'border-amber-500/30',   hex: '#fbbf24' },
    linear:   { label: 'LINEAR',        emoji: '📋', color: 'text-amber-400',   bg: 'bg-amber-500/10',   border: 'border-amber-500/30',   hex: '#fbbf24' },
  }
  return configs[source] || { label: source.toUpperCase(), emoji: '💬', color: 'text-text-muted', bg: 'bg-surface', border: 'border-border', hex: '#888888' }
}

function extractKeywords(text: string): string[] {
  const stopWords = new Set([
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'can', 'shall', 'to', 'of', 'in', 'for',
    'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through', 'during',
    'before', 'after', 'above', 'below', 'between', 'out', 'off', 'over',
    'under', 'again', 'further', 'then', 'once', 'here', 'there', 'when',
    'where', 'why', 'how', 'all', 'each', 'every', 'both', 'few', 'more',
    'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own',
    'same', 'so', 'than', 'too', 'very', 'just', 'because', 'but', 'and',
    'or', 'if', 'while', 'about', 'this', 'that', 'these', 'those', 'it',
    'its', 'i', 'me', 'my', 'we', 'our', 'you', 'your', 'he', 'him',
    'she', 'her', 'they', 'them', 'their', 'what', 'which', 'who', 'whom',
    'up', 'down', 'also', 'like', 'get', 'got', 'make', 'made', 'think',
    'know', 'want', 'need', 'use', 'try', 'take', 'come', 'go', 'see',
    'look', 'find', 'give', 'tell', 'say', 'thing', 'something', 'really',
  ])
  const words = text.toLowerCase().replace(/[^a-z0-9\s-]/g, '').split(/\s+/)
  const freq: Record<string, number> = {}
  for (const w of words) {
    if (w.length > 2 && !stopWords.has(w)) {
      freq[w] = (freq[w] || 0) + 1
    }
  }
  return Object.entries(freq)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([w]) => w)
}

function findConnections(captures: QuickCapture[]): ConstellationEdge[] {
  const edges: ConstellationEdge[] = []
  for (let i = 0; i < captures.length; i++) {
    for (let j = i + 1; j < captures.length; j++) {
      const a = captures[i]
      const b = captures[j]
      // shared tags
      const sharedTags = a.tags.filter(t => b.tags.includes(t)).length
      // shared keywords
      const kwA = new Set(extractKeywords(a.text))
      const kwB = extractKeywords(b.text)
      const sharedKw = kwB.filter(k => kwA.has(k)).length
      const strength = sharedTags * 2 + sharedKw
      if (strength > 0) {
        edges.push({ source: i, target: j, strength: Math.min(strength, 5) })
      }
    }
  }
  return edges
}

/* ───────────────────────── Constellation Canvas ───────────────────────── */

function ConstellationView({
  captures,
  onSelectCapture,
  selectedId,
}: {
  captures: QuickCapture[]
  onSelectCapture: (c: QuickCapture | null) => void
  selectedId: string | null
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const nodesRef = useRef<ConstellationNode[]>([])
  const edgesRef = useRef<ConstellationEdge[]>([])
  const animRef = useRef<number>(0)
  const mouseRef = useRef<{ x: number; y: number } | null>(null)
  const hoveredRef = useRef<number>(-1)
  const containerRef = useRef<HTMLDivElement>(null)

  // Initialize nodes and edges when captures change
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const w = canvas.width
    const h = canvas.height

    const edges = findConnections(captures)
    edgesRef.current = edges

    // Count connections per node
    const connCount = new Array(captures.length).fill(0)
    for (const e of edges) {
      connCount[e.source]++
      connCount[e.target]++
    }

    // Create nodes
    const nodes: ConstellationNode[] = captures.map((cap, i) => {
      const conns = connCount[i] || 0
      return {
        id: cap.id,
        x: w * 0.2 + Math.random() * w * 0.6,
        y: h * 0.2 + Math.random() * h * 0.6,
        vx: (Math.random() - 0.5) * 0.5,
        vy: (Math.random() - 0.5) * 0.5,
        radius: Math.max(6, Math.min(20, 6 + conns * 3)),
        capture: cap,
        connections: conns,
        glowPhase: Math.random() * Math.PI * 2,
      }
    })
    nodesRef.current = nodes
  }, [captures])

  // Animation loop
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let time = 0

    const tick = () => {
      const nodes = nodesRef.current
      const edges = edgesRef.current
      const w = canvas.width
      const h = canvas.height
      time += 0.016

      // --- Physics ---
      const damping = 0.92
      const repulsion = 800
      const edgeAttraction = 0.005
      const centerGravity = 0.0008

      // Repulsion between all nodes
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[j].x - nodes[i].x
          const dy = nodes[j].y - nodes[i].y
          const dist = Math.sqrt(dx * dx + dy * dy) || 1
          const force = repulsion / (dist * dist)
          const fx = (dx / dist) * force
          const fy = (dy / dist) * force
          nodes[i].vx -= fx
          nodes[i].vy -= fy
          nodes[j].vx += fx
          nodes[j].vy += fy
        }
      }

      // Edge attraction
      for (const edge of edges) {
        const a = nodes[edge.source]
        const b = nodes[edge.target]
        if (!a || !b) continue
        const dx = b.x - a.x
        const dy = b.y - a.y
        const force = edgeAttraction * edge.strength
        a.vx += dx * force
        a.vy += dy * force
        b.vx -= dx * force
        b.vy -= dy * force
      }

      // Center gravity
      for (const node of nodes) {
        node.vx += (w / 2 - node.x) * centerGravity
        node.vy += (h / 2 - node.y) * centerGravity
      }

      // Update positions
      for (const node of nodes) {
        node.vx *= damping
        node.vy *= damping
        node.x += node.vx
        node.y += node.vy
        // Boundary
        const pad = node.radius + 4
        if (node.x < pad) { node.x = pad; node.vx *= -0.5 }
        if (node.x > w - pad) { node.x = w - pad; node.vx *= -0.5 }
        if (node.y < pad) { node.y = pad; node.vy *= -0.5 }
        if (node.y > h - pad) { node.y = h - pad; node.vy *= -0.5 }
      }

      // --- Hit test for hover ---
      const mp = mouseRef.current
      hoveredRef.current = -1
      if (mp) {
        for (let i = nodes.length - 1; i >= 0; i--) {
          const dx = mp.x - nodes[i].x
          const dy = mp.y - nodes[i].y
          if (dx * dx + dy * dy < (nodes[i].radius + 4) ** 2) {
            hoveredRef.current = i
            break
          }
        }
      }

      // --- Render ---
      ctx.clearRect(0, 0, w, h)

      // Edges
      for (const edge of edges) {
        const a = nodes[edge.source]
        const b = nodes[edge.target]
        if (!a || !b) continue
        ctx.beginPath()
        ctx.moveTo(a.x, a.y)
        ctx.lineTo(b.x, b.y)
        ctx.strokeStyle = `rgba(139, 92, 246, ${0.08 + edge.strength * 0.04})`
        ctx.lineWidth = 0.5 + edge.strength * 0.3
        ctx.stroke()
      }

      // Nodes
      for (let i = 0; i < nodes.length; i++) {
        const node = nodes[i]
        const cfg = getSourceConfig(node.capture.source)
        const isHovered = hoveredRef.current === i
        const isSelected = selectedId === node.id
        const glowIntensity = 0.3 + 0.2 * Math.sin(time * 1.5 + node.glowPhase)
        const r = isHovered || isSelected ? node.radius * 1.3 : node.radius

        // Glow
        const glow = ctx.createRadialGradient(node.x, node.y, 0, node.x, node.y, r * 3)
        glow.addColorStop(0, hexToRgba(cfg.hex, glowIntensity * (isHovered ? 1.5 : 1)))
        glow.addColorStop(1, hexToRgba(cfg.hex, 0))
        ctx.fillStyle = glow
        ctx.beginPath()
        ctx.arc(node.x, node.y, r * 3, 0, Math.PI * 2)
        ctx.fill()

        // Node body
        ctx.beginPath()
        ctx.arc(node.x, node.y, r, 0, Math.PI * 2)
        ctx.fillStyle = hexToRgba(cfg.hex, isHovered || isSelected ? 0.9 : 0.7)
        ctx.fill()

        // Ring for selected
        if (isSelected) {
          ctx.beginPath()
          ctx.arc(node.x, node.y, r + 3, 0, Math.PI * 2)
          ctx.strokeStyle = hexToRgba(cfg.hex, 0.8)
          ctx.lineWidth = 2
          ctx.stroke()
        }

        // Tooltip on hover
        if (isHovered) {
          const txt = node.capture.text.length > 60
            ? node.capture.text.slice(0, 57) + '…'
            : node.capture.text
          ctx.font = '11px monospace'
          const metrics = ctx.measureText(txt)
          const tw = metrics.width + 16
          const tx = Math.min(Math.max(node.x - tw / 2, 4), w - tw - 4)
          const ty = node.y - r - 28

          ctx.fillStyle = 'rgba(15, 15, 20, 0.92)'
          ctx.beginPath()
          roundRect(ctx, tx, ty, tw, 22, 4)
          ctx.fill()
          ctx.strokeStyle = hexToRgba(cfg.hex, 0.4)
          ctx.lineWidth = 1
          ctx.beginPath()
          roundRect(ctx, tx, ty, tw, 22, 4)
          ctx.stroke()

          ctx.fillStyle = '#e0e0e0'
          ctx.fillText(txt, tx + 8, ty + 15)
        }
      }

      animRef.current = requestAnimationFrame(tick)
    }

    animRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(animRef.current)
  }, [captures, selectedId])

  // Resize handler
  useEffect(() => {
    const handleResize = () => {
      const canvas = canvasRef.current
      const container = containerRef.current
      if (!canvas || !container) return
      const rect = container.getBoundingClientRect()
      const dpr = window.devicePixelRatio || 1
      canvas.width = rect.width * dpr
      canvas.height = rect.height * dpr
      canvas.style.width = rect.width + 'px'
      canvas.style.height = rect.height + 'px'
      const ctx = canvas.getContext('2d')
      if (ctx) ctx.scale(dpr, dpr)
      // Remap nodes to new dimensions
      for (const node of nodesRef.current) {
        node.x = Math.min(node.x, rect.width - node.radius)
        node.y = Math.min(node.y, rect.height - node.radius)
      }
    }
    handleResize()
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [captures])

  // Mouse events
  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    mouseRef.current = {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    }
  }, [])

  const handleMouseLeave = useCallback(() => {
    mouseRef.current = null
    hoveredRef.current = -1
  }, [])

  const handleClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    const mx = e.clientX - rect.left
    const my = e.clientY - rect.top
    const nodes = nodesRef.current
    for (let i = nodes.length - 1; i >= 0; i--) {
      const dx = mx - nodes[i].x
      const dy = my - nodes[i].y
      if (dx * dx + dy * dy < (nodes[i].radius + 4) ** 2) {
        onSelectCapture(selectedId === nodes[i].id ? null : nodes[i].capture)
        return
      }
    }
    onSelectCapture(null)
  }, [onSelectCapture, selectedId])

  return (
    <div ref={containerRef} className="relative w-full h-[320px] md:h-[400px] rounded-lg border border-border/40 bg-[#0a0a10] overflow-hidden">
      <canvas
        ref={canvasRef}
        className="w-full h-full cursor-crosshair"
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        onClick={handleClick}
      />
      {/* Legend */}
      <div className="absolute top-3 left-3 flex flex-wrap gap-2">
        {[
          { label: 'Manual', hex: '#60a5fa' },
          { label: 'Voice', hex: '#c084fc' },
          { label: 'Telegram', hex: '#34d399' },
          { label: 'Eureka', hex: '#fbbf24' },
        ].map(l => (
          <span key={l.label} className="flex items-center gap-1 text-[9px] font-mono text-text-muted/60">
            <span className="inline-block w-2 h-2 rounded-full" style={{ background: l.hex }} />
            {l.label}
          </span>
        ))}
      </div>
      {captures.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center">
          <p className="text-xs font-mono text-text-muted/40">Captures will appear as constellation nodes</p>
        </div>
      )}
    </div>
  )
}

function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r},${g},${b},${alpha})`
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.moveTo(x + r, y)
  ctx.lineTo(x + w - r, y)
  ctx.quadraticCurveTo(x + w, y, x + w, y + r)
  ctx.lineTo(x + w, y + h - r)
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h)
  ctx.lineTo(x + r, y + h)
  ctx.quadraticCurveTo(x, y + h, x, y + h - r)
  ctx.lineTo(x, y + r)
  ctx.quadraticCurveTo(x, y, x + r, y)
}

/* ───────────────────── Mobile List View ───────────────────── */

function ConstellationListView({
  captures,
  onSelectCapture,
  selectedId,
}: {
  captures: QuickCapture[]
  onSelectCapture: (c: QuickCapture | null) => void
  selectedId: string | null
}) {
  const edges = findConnections(captures)
  const connCount = new Array(captures.length).fill(0)
  for (const e of edges) {
    connCount[e.source]++
    connCount[e.target]++
  }

  return (
    <div className="grid grid-cols-2 gap-2 p-2 rounded-lg border border-border/40 bg-[#0a0a10]">
      {captures.slice(0, 20).map((cap, i) => {
        const cfg = getSourceConfig(cap.source)
        const isSelected = selectedId === cap.id
        return (
          <button
            key={cap.id}
            onClick={() => onSelectCapture(isSelected ? null : cap)}
            className={`text-left p-2 rounded border transition-all ${
              isSelected
                ? `${cfg.border} ${cfg.bg}`
                : 'border-border/20 bg-transparent hover:bg-white/5'
            }`}
          >
            <div className="flex items-center gap-1.5 mb-1">
              <span className="inline-block w-2 h-2 rounded-full" style={{ background: cfg.hex }} />
              <span className="text-[9px] font-mono text-text-muted">{cfg.emoji} {cfg.label}</span>
            </div>
            <p className="text-[11px] font-mono text-text-primary/80 line-clamp-2">{cap.text}</p>
            {connCount[i] > 0 && (
              <span className="text-[9px] font-mono text-accent/60 mt-1 block">
                {connCount[i]} connection{connCount[i] > 1 ? 's' : ''}
              </span>
            )}
          </button>
        )
      })}
      {captures.length === 0 && (
        <div className="col-span-2 py-8 text-center">
          <p className="text-xs font-mono text-text-muted/40">No captures yet</p>
        </div>
      )}
    </div>
  )
}

/* ───────────────────── Selected Capture Detail ───────────────────── */

function CaptureDetail({
  capture,
  onClose,
}: {
  capture: QuickCapture
  onClose: () => void
}) {
  const [memories, setMemories] = useState<MemoryResult[]>([])
  const [loadingMemories, setLoadingMemories] = useState(false)
  const cfg = getSourceConfig(capture.source)

  useEffect(() => {
    const fetchRelated = async () => {
      setLoadingMemories(true)
      try {
        const q = encodeURIComponent(capture.text.slice(0, 200))
        const data = await apiGet<MemorySearchResponse>(`/api/v2/memory/search?q=${q}&limit=3`)
        setMemories(data.results || [])
      } catch {
        setMemories([])
      } finally {
        setLoadingMemories(false)
      }
    }
    fetchRelated()
  }, [capture])

  return (
    <div className={`mt-3 border rounded-lg p-4 ${cfg.bg} ${cfg.border} animate-in fade-in`}>
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2">
          <span className="inline-block w-3 h-3 rounded-full" style={{ background: cfg.hex }} />
          <span className={`text-[10px] font-mono ${cfg.color}`}>{cfg.emoji} {cfg.label}</span>
          <span className="text-[10px] font-mono text-text-muted" title={formatFullDate(capture.created_at)}>
            · {timeAgo(capture.created_at)}
          </span>
        </div>
        <button onClick={onClose} className="text-text-muted hover:text-text-primary text-sm">✕</button>
      </div>
      <p className="text-sm text-text-primary leading-relaxed mb-3 font-mono">{capture.text}</p>
      {capture.tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {capture.tags.map((tag, i) => (
            <span key={i} className="px-2 py-0.5 text-[10px] font-mono text-text-muted bg-border/30 rounded">#{tag}</span>
          ))}
        </div>
      )}
      {/* Related Memories */}
      {loadingMemories && (
        <div className="flex items-center gap-2 text-text-muted text-[10px] font-mono pt-2 border-t border-border/30">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-accent animate-pulse" />
          Finding related memories…
        </div>
      )}
      {!loadingMemories && memories.length > 0 && (
        <div className="pt-2 border-t border-border/30">
          <h4 className="text-[10px] font-mono tracking-widest text-text-muted/70 mb-2">CONNECTED MEMORIES</h4>
          <div className="space-y-1.5">
            {memories.map((m) => (
              <div key={m.conversation_id} className="p-2 rounded bg-black/20 border border-border/20">
                <p className="text-[11px] font-mono text-text-primary/80">{m.title}</p>
                <p className="text-[10px] font-mono text-text-muted/60 line-clamp-2 mt-0.5">{m.snippet}</p>
                {(m.topics && m.topics.length > 0) && (
                  <div className="flex flex-wrap gap-1 mt-1">
                    {m.topics.slice(0, 3).map((t, i) => (
                      <span key={i} className="text-[9px] font-mono text-accent/50">#{t}</span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

/* ───────────────────── Smart Capture Input ───────────────────── */

function SmartCaptureInput({
  onCaptured,
}: {
  onCaptured: () => void
}) {
  const [text, setText] = useState('')
  const [tagsInput, setTagsInput] = useState('')
  const [suggestedTags, setSuggestedTags] = useState<string[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [relatedMemories, setRelatedMemories] = useState<MemoryResult[]>([])
  const [loadingRelated, setLoadingRelated] = useState(false)
  const [showRelated, setShowRelated] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Ctrl+K shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        textareaRef.current?.focus()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  // Auto-suggest tags
  useEffect(() => {
    if (text.trim().length < 10) {
      setSuggestedTags([])
      return
    }
    const timeout = setTimeout(() => {
      const kw = extractKeywords(text)
      setSuggestedTags(kw)
    }, 500)
    return () => clearTimeout(timeout)
  }, [text])

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!text.trim()) return
    setSubmitting(true)
    setError(null)
    try {
      const tags = tagsInput.split(',').map(t => t.trim()).filter(t => t.length > 0)
      await apiPost('/api/v2/captures/quick', { text: text.trim(), tags })

      // Fetch related memories
      setLoadingRelated(true)
      setShowRelated(true)
      try {
        const q = encodeURIComponent(text.trim().slice(0, 200))
        const data = await apiGet<MemorySearchResponse>(`/api/v2/memory/search?q=${q}&limit=5`)
        setRelatedMemories(data.results || [])
      } catch {
        setRelatedMemories([])
      } finally {
        setLoadingRelated(false)
      }

      setText('')
      setTagsInput('')
      setSuggestedTags([])
      onCaptured()
    } catch {
      setError('Failed to save capture')
    } finally {
      setSubmitting(false)
    }
  }

  const addSuggestedTag = (tag: string) => {
    const current = tagsInput.split(',').map(t => t.trim()).filter(Boolean)
    if (!current.includes(tag)) {
      setTagsInput(current.length > 0 ? current.join(', ') + ', ' + tag : tag)
    }
  }

  return (
    <div>
      <form onSubmit={handleSubmit}>
        <div className="border border-border rounded-lg bg-surface p-4 focus-within:border-accent/60 transition-colors">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-[10px] font-mono tracking-widest text-text-muted/70">CAPTURE</h3>
            <span className="text-[9px] font-mono text-text-muted/40 hidden sm:inline">⌘K to focus</span>
          </div>
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                handleSubmit(e)
              }
            }}
            placeholder="What's emerging in your mind?"
            className="w-full bg-transparent text-sm text-text-primary placeholder:text-text-muted/50 font-mono outline-none resize-none"
            rows={3}
          />

          {/* Tag suggestions */}
          {suggestedTags.length > 0 && (
            <div className="flex items-center gap-1.5 mt-2 flex-wrap">
              <span className="text-[9px] font-mono text-text-muted/50">suggest:</span>
              {suggestedTags.map((tag) => (
                <button
                  key={tag}
                  type="button"
                  onClick={() => addSuggestedTag(tag)}
                  className="px-1.5 py-0.5 text-[9px] font-mono text-accent/60 border border-accent/20 rounded hover:bg-accent/10 transition-colors"
                >
                  +{tag}
                </button>
              ))}
            </div>
          )}

          <input
            type="text"
            value={tagsInput}
            onChange={(e) => setTagsInput(e.target.value)}
            placeholder="Tags (comma-separated)"
            className="w-full mt-3 bg-transparent border-t border-border/50 pt-3 text-xs text-text-secondary placeholder:text-text-muted/40 font-mono outline-none"
          />

          <div className="mt-3 flex items-center justify-between">
            <div className="text-[9px] font-mono text-text-muted/40">
              {text.length > 0 && `${text.length} chars · ⌘Enter to save`}
            </div>
            <button
              type="submit"
              disabled={!text.trim() || submitting}
              className="px-4 py-2 text-xs font-mono tracking-wider bg-accent/10 border border-accent/40 text-accent rounded hover:bg-accent/20 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            >
              {submitting ? '⟳ SAVING…' : '⚡ CAPTURE'}
            </button>
          </div>
        </div>
      </form>

      {error && (
        <div className="mt-3 border border-red-500/20 rounded-lg p-3 bg-red-500/5">
          <p className="text-red-400/70 text-xs font-mono">{error}</p>
        </div>
      )}

      {/* Related Memories */}
      {showRelated && (
        <div className="mt-4">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-[10px] font-mono tracking-widest text-text-muted/70">
              🧠 RELATED FROM YOUR MEMORY
            </h3>
            <button
              onClick={() => setShowRelated(false)}
              className="text-[9px] font-mono text-text-muted/40 hover:text-text-muted"
            >
              dismiss
            </button>
          </div>
          {loadingRelated ? (
            <div className="flex items-center gap-2 text-text-muted text-[10px] font-mono py-3">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-purple-400 animate-pulse" />
              Searching your memory…
            </div>
          ) : relatedMemories.length > 0 ? (
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {relatedMemories.map((m) => (
                <div
                  key={m.conversation_id}
                  className="p-3 rounded-lg border border-purple-500/20 bg-purple-500/5 hover:border-purple-500/40 transition-colors"
                >
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <span className="text-[9px]">💬</span>
                    <span className="text-[10px] font-mono text-purple-400/80">Conversation</span>
                  </div>
                  <p className="text-[11px] font-mono text-text-primary/80 font-medium line-clamp-1">{m.title}</p>
                  <p className="text-[10px] font-mono text-text-muted/50 line-clamp-2 mt-1">{m.snippet}</p>
                  <div className="flex flex-wrap gap-1 mt-2">
                    {m.topics?.slice(0, 2).map((t, i) => (
                      <span key={i} className="text-[9px] font-mono text-purple-400/40">#{t}</span>
                    ))}
                    {m.people?.slice(0, 2).map((p, i) => (
                      <span key={i} className="text-[9px] font-mono text-blue-400/40">@{p}</span>
                    ))}
                    {m.projects?.slice(0, 1).map((p, i) => (
                      <span key={i} className="text-[9px] font-mono text-amber-400/40">📁{p}</span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-[10px] font-mono text-text-muted/30 py-2">No related memories found</p>
          )}
        </div>
      )}
    </div>
  )
}

/* ───────────────────── Serendipity Shelf ───────────────────── */

function SerendipityShelf({ captures }: { captures: QuickCapture[] }) {
  const [randomCaptures, setRandomCaptures] = useState<QuickCapture[]>([])

  const pickRandom = useCallback(() => {
    if (captures.length <= 3) {
      setRandomCaptures([...captures])
      return
    }
    const shuffled = [...captures].sort(() => Math.random() - 0.5)
    setRandomCaptures(shuffled.slice(0, 3))
  }, [captures])

  useEffect(() => {
    pickRandom()
  }, [pickRandom])

  if (captures.length === 0) return null

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-xs font-mono tracking-widest text-text-muted/70">
          🎲 SERENDIPITY — What if these connect?
        </h2>
        <button
          onClick={pickRandom}
          className="text-[10px] font-mono text-accent/60 hover:text-accent border border-accent/20 px-2 py-1 rounded hover:bg-accent/10 transition-colors"
        >
          ↻ Reshuffle
        </button>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        {randomCaptures.map((cap) => {
          const cfg = getSourceConfig(cap.source)
          return (
            <div
              key={cap.id}
              className={`border rounded-lg p-3 ${cfg.bg} ${cfg.border} hover:scale-[1.02] transition-transform`}
            >
              <div className="flex items-center justify-between gap-2 mb-2">
                <span className={`text-[9px] font-mono ${cfg.color} flex items-center gap-1`}>
                  <span>{cfg.emoji}</span>
                  <span>{cfg.label}</span>
                </span>
                <span className="text-[9px] font-mono text-text-muted/40" title={formatFullDate(cap.created_at)}>
                  {timeAgo(cap.created_at)}
                </span>
              </div>
              <p className="text-[11px] font-mono text-text-primary/80 leading-relaxed mb-2 line-clamp-3">
                {cap.text}
              </p>
              {cap.tags.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {cap.tags.map((tag, i) => (
                    <span key={i} className="text-[9px] font-mono text-text-muted/40">#{tag}</span>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
      {randomCaptures.length >= 2 && (
        <div className="mt-3 text-center">
          <p className="text-[9px] font-mono text-text-muted/20 italic">
            {randomCaptures.length} ideas pulled from {captures.length} captures — look for the unexpected link
          </p>
        </div>
      )}
    </div>
  )
}

/* ───────────────────── Main Page ───────────────────── */

export function CapturePage() {
  const [captures, setCaptures] = useState<QuickCapture[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedCapture, setSelectedCapture] = useState<QuickCapture | null>(null)
  const [isMobile, setIsMobile] = useState(false)

  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 640)
    check()
    window.addEventListener('resize', check)
    return () => window.removeEventListener('resize', check)
  }, [])

  const fetchCaptures = useCallback(async () => {
    setLoading(true)
    try {
      const data = await apiGet<QuickCapturesResponse>('/api/v2/captures/quick?limit=100')
      setCaptures(data.captures || [])
    } catch (e) {
      console.error('Failed to fetch captures:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchCaptures()
  }, [fetchCaptures])

  return (
    <div className="max-w-5xl space-y-8">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3 mb-1">
          <h1 className="text-lg font-mono font-bold text-text-primary tracking-wider">
            ✦ IDEA CONSTELLATION
          </h1>
          {captures.length > 0 && (
            <span className="text-[10px] font-mono text-text-muted/50 bg-border/20 px-2 py-0.5 rounded">
              {captures.length} nodes
            </span>
          )}
        </div>
        <p className="text-xs font-mono text-text-muted/50 tracking-wide">
          Your captured thoughts, connected and alive
        </p>
      </div>

      {/* A. Constellation View */}
      {loading ? (
        <div className="flex items-center gap-2 text-text-muted text-xs font-mono py-16 justify-center">
          <span className="inline-block h-2 w-2 rounded-full bg-accent animate-pulse" />
          Mapping constellation…
        </div>
      ) : isMobile ? (
        <ConstellationListView
          captures={captures}
          onSelectCapture={(c) => setSelectedCapture(c)}
          selectedId={selectedCapture?.id || null}
        />
      ) : (
        <ConstellationView
          captures={captures}
          onSelectCapture={(c) => setSelectedCapture(c)}
          selectedId={selectedCapture?.id || null}
        />
      )}

      {/* Selected capture detail */}
      {selectedCapture && (
        <CaptureDetail
          capture={selectedCapture}
          onClose={() => setSelectedCapture(null)}
        />
      )}

      {/* B. Smart Capture Input */}
      <SmartCaptureInput onCaptured={fetchCaptures} />

      {/* C. Serendipity Shelf */}
      <SerendipityShelf captures={captures} />
    </div>
  )
}
