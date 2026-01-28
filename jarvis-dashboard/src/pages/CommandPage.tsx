import { useState, useRef, useEffect, useCallback } from 'react'
import { apiPost } from '../api/client.ts'

// --- Types ---

interface ChatMessage {
  id: string
  role: 'user' | 'eureka'
  content: string
  timestamp: number
  sources?: Array<{ title: string; snippet: string; conversation_id?: string }>
}

interface AskResponse {
  answer: string
  sources?: Array<{ title: string; snippet: string; conversation_id?: string; date?: string }>
}

// --- Storage ---

const STORAGE_KEY = 'jarvis-command-history'
const MAX_STORED = 200

function loadHistory(): ChatMessage[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw)
  } catch {}
  return []
}

function saveHistory(messages: ChatMessage[]) {
  try {
    const trimmed = messages.slice(-MAX_STORED)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed))
  } catch {}
}

function genId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

// --- Markdown-lite renderer ---

function renderContent(text: string) {
  const lines = text.split('\n')
  return lines.map((line, i) => {
    // Code blocks (inline)
    const parts = line.split(/(`[^`]+`)/g)
    const rendered = parts.map((part, j) => {
      if (part.startsWith('`') && part.endsWith('`')) {
        return (
          <code key={j} className="px-1.5 py-0.5 bg-black/40 rounded text-amber-300 text-[13px]">
            {part.slice(1, -1)}
          </code>
        )
      }
      // Bold: **text**
      const boldParts = part.split(/(\*\*[^*]+\*\*)/g)
      return boldParts.map((bp, k) => {
        if (bp.startsWith('**') && bp.endsWith('**')) {
          return (
            <span key={`${j}-${k}`} className="font-bold text-amber-200">
              {bp.slice(2, -2)}
            </span>
          )
        }
        return <span key={`${j}-${k}`}>{bp}</span>
      })
    })

    // Bullet points
    if (line.trimStart().startsWith('- ')) {
      return (
        <div key={i} className="pl-4 py-0.5">
          <span className="text-amber-500 mr-2">•</span>
          {rendered}
        </div>
      )
    }

    // Numbered lists
    if (/^\d+\.\s/.test(line.trimStart())) {
      return (
        <div key={i} className="pl-4 py-0.5">
          {rendered}
        </div>
      )
    }

    // Empty lines
    if (line.trim() === '') {
      return <div key={i} className="h-2" />
    }

    return (
      <div key={i} className="py-0.5">
        {rendered}
      </div>
    )
  })
}

// --- Component ---

export function CommandPage() {
  const [messages, setMessages] = useState<ChatMessage[]>(loadHistory)
  const [input, setInput] = useState('')
  const [isTyping, setIsTyping] = useState(false)
  const [showSources, setShowSources] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Auto-scroll on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, isTyping])

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  // Persist history
  useEffect(() => {
    saveHistory(messages)
  }, [messages])

  const sendMessage = useCallback(async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || isTyping) return

    // Add user message
    const userMsg: ChatMessage = {
      id: genId(),
      role: 'user',
      content: trimmed,
      timestamp: Date.now(),
    }

    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setIsTyping(true)

    try {
      const data = await apiPost<AskResponse>('/api/v2/memory/ask', { question: trimmed })
      const eurekaMsg: ChatMessage = {
        id: genId(),
        role: 'eureka',
        content: data.answer || 'No response.',
        timestamp: Date.now(),
        sources: data.sources,
      }
      setMessages((prev) => [...prev, eurekaMsg])
    } catch (err) {
      const errorMsg: ChatMessage = {
        id: genId(),
        role: 'eureka',
        content: `⚠ Connection error: ${err instanceof Error ? err.message : 'Request failed'}. I'll be back online shortly.`,
        timestamp: Date.now(),
      }
      setMessages((prev) => [...prev, errorMsg])
    } finally {
      setIsTyping(false)
      // Re-focus input
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [isTyping])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        sendMessage(input)
      }
    },
    [input, sendMessage],
  )

  const clearHistory = useCallback(() => {
    setMessages([])
    localStorage.removeItem(STORAGE_KEY)
  }, [])

  const formatTime = (ts: number) => {
    const d = new Date(ts)
    return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' })
  }

  const formatDate = (ts: number) => {
    const d = new Date(ts)
    const today = new Date()
    if (d.toDateString() === today.toDateString()) return 'Today'
    const yesterday = new Date(today)
    yesterday.setDate(yesterday.getDate() - 1)
    if (d.toDateString() === yesterday.toDateString()) return 'Yesterday'
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }

  // Group messages by date
  let lastDate = ''

  return (
    <div className="flex flex-col h-[calc(100vh-theme(spacing.14)-theme(spacing.6)*2)] lg:h-[calc(100vh-theme(spacing.8)*2)]">
      {/* Header */}
      <div className="shrink-0 mb-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.6)] animate-pulse" />
          <h3 className="font-mono text-sm font-bold text-text-primary tracking-widest">
            EUREKA TERMINAL
          </h3>
          <span className="font-mono text-[10px] text-text-muted tracking-wider">
            v2 · memory-aware
          </span>
        </div>
        <div className="flex items-center gap-3">
          {messages.length > 0 && (
            <button
              onClick={clearHistory}
              className="font-mono text-[10px] text-text-muted hover:text-red-400 tracking-wider transition-colors"
            >
              CLEAR
            </button>
          )}
          <span className="font-mono text-[10px] text-text-muted">
            {messages.length} msg{messages.length !== 1 ? 's' : ''}
          </span>
        </div>
      </div>

      {/* Chat area */}
      <div
        ref={scrollRef}
        className="flex-1 min-h-0 overflow-y-auto rounded-lg border border-border/50 bg-[#0a0a0f] px-4 py-4 space-y-1"
      >
        {messages.length === 0 && !isTyping && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center space-y-4 max-w-md">
              <div className="text-4xl mb-2">◈</div>
              <p className="font-mono text-base text-amber-500/80 tracking-wider">
                EUREKA READY
              </p>
              <p className="text-sm text-text-muted leading-relaxed">
                Ask me anything about your projects, emails, meetings, or conversations.
                I search across all your data to give contextual answers.
              </p>
              <div className="flex flex-wrap justify-center gap-2 mt-4">
                {[
                  'What did I discuss with the team this week?',
                  'Summarize my pending decisions',
                  'What\'s the status of RecruitOS?',
                ].map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => sendMessage(suggestion)}
                    className="px-3 py-1.5 border border-border/60 rounded text-xs text-text-secondary hover:text-amber-400 hover:border-amber-500/40 transition-colors font-mono"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {messages.map((msg) => {
          const dateStr = formatDate(msg.timestamp)
          const showDateSep = dateStr !== lastDate
          lastDate = dateStr

          return (
            <div key={msg.id}>
              {/* Date separator */}
              {showDateSep && (
                <div className="flex items-center gap-3 my-4">
                  <div className="flex-1 border-t border-border/30" />
                  <span className="font-mono text-[10px] text-text-muted tracking-wider">{dateStr}</span>
                  <div className="flex-1 border-t border-border/30" />
                </div>
              )}

              {/* Message bubble */}
              <div className={`flex mb-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-[80%] lg:max-w-[70%] group ${
                    msg.role === 'user'
                      ? 'bg-green-900/30 border border-green-500/20 rounded-2xl rounded-br-md'
                      : 'bg-amber-900/10 border border-amber-500/15 rounded-2xl rounded-bl-md'
                  } px-4 py-3`}
                >
                  {/* Sender label */}
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className={`font-mono text-[10px] tracking-wider font-bold ${
                      msg.role === 'user' ? 'text-green-400' : 'text-amber-500'
                    }`}>
                      {msg.role === 'user' ? 'SVEN' : '◈ EUREKA'}
                    </span>
                    <span className="font-mono text-[10px] text-text-muted opacity-0 group-hover:opacity-100 transition-opacity">
                      {formatTime(msg.timestamp)}
                    </span>
                  </div>

                  {/* Content */}
                  <div className={`text-sm leading-relaxed ${
                    msg.role === 'user' ? 'text-green-100' : 'text-amber-100/90'
                  }`}>
                    {msg.role === 'user' ? (
                      <p>{msg.content}</p>
                    ) : (
                      renderContent(msg.content)
                    )}
                  </div>

                  {/* Sources toggle */}
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-amber-500/10">
                      <button
                        onClick={() => setShowSources(showSources === msg.id ? null : msg.id)}
                        className="font-mono text-[10px] text-amber-500/60 hover:text-amber-400 tracking-wider transition-colors"
                      >
                        {showSources === msg.id ? '▾' : '▸'} {msg.sources.length} SOURCE{msg.sources.length !== 1 ? 'S' : ''}
                      </button>
                      {showSources === msg.id && (
                        <div className="mt-2 space-y-1.5">
                          {msg.sources.map((s, i) => (
                            <div key={i} className="pl-3 border-l border-amber-500/20">
                              <p className="font-mono text-[11px] text-amber-400/80 truncate">
                                {s.title || 'Untitled'}
                              </p>
                              {s.snippet && (
                                <p className="text-[11px] text-text-muted truncate mt-0.5">
                                  {s.snippet}
                                </p>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )
        })}

        {/* Typing indicator */}
        {isTyping && (
          <div className="flex justify-start mb-3">
            <div className="bg-amber-900/10 border border-amber-500/15 rounded-2xl rounded-bl-md px-4 py-3">
              <div className="flex items-center gap-2 mb-1">
                <span className="font-mono text-[10px] tracking-wider font-bold text-amber-500">
                  ◈ EUREKA
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-amber-500/60 animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-2 h-2 rounded-full bg-amber-500/60 animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-2 h-2 rounded-full bg-amber-500/60 animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="shrink-0 mt-3">
        <div className="border border-amber-500/20 bg-surface rounded-xl overflow-hidden focus-within:border-amber-500/40 transition-colors">
          <div className="flex items-end gap-3 px-4 py-3">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Talk to Eureka..."
              disabled={isTyping}
              rows={1}
              className="flex-1 bg-transparent border-none outline-none font-mono text-[15px] text-text-primary placeholder:text-text-muted disabled:opacity-50 resize-none min-h-[24px] max-h-[120px]"
              style={{ height: 'auto' }}
              onInput={(e) => {
                const target = e.target as HTMLTextAreaElement
                target.style.height = 'auto'
                target.style.height = `${Math.min(target.scrollHeight, 120)}px`
              }}
              autoFocus
            />
            <button
              onClick={() => sendMessage(input)}
              disabled={isTyping || !input.trim()}
              className="shrink-0 w-9 h-9 flex items-center justify-center rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-500 hover:bg-amber-500/20 transition-all disabled:opacity-20 disabled:cursor-not-allowed"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
              </svg>
            </button>
          </div>
          <div className="px-4 pb-2 flex items-center gap-4">
            <span className="font-mono text-[10px] text-text-muted tracking-wider">
              ENTER TO SEND · SHIFT+ENTER NEW LINE
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
