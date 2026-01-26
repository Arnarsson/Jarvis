import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../../api/client.ts'
import { LoadingSkeleton } from '../ui/LoadingSkeleton.tsx'

interface EmailAuthStatus {
  authenticated: boolean
  email?: string
}

interface EmailMessage {
  id: string
  subject: string
  from_address: string
  is_unread: boolean
  is_important: boolean
}

interface EmailListResponse {
  messages: EmailMessage[]
  count: number
}

async function fetchEmailAuth(): Promise<EmailAuthStatus> {
  try {
    return await apiGet<EmailAuthStatus>('/api/email/auth/status')
  } catch {
    return { authenticated: false }
  }
}

async function fetchEmails(): Promise<EmailMessage[]> {
  try {
    const data = await apiGet<EmailListResponse>('/api/email/messages')
    return data.messages
  } catch {
    return []
  }
}

export function Communications() {
  const { data: auth } = useQuery({
    queryKey: ['email', 'auth'],
    queryFn: fetchEmailAuth,
  })

  const { data: messages, isLoading } = useQuery({
    queryKey: ['email', 'messages'],
    queryFn: fetchEmails,
    enabled: auth?.authenticated === true,
  })

  const unread = messages?.filter((m) => m.is_unread).length ?? 0
  const priority = messages?.filter((m) => m.is_important).length ?? 0

  return (
    <div>
      <h3 className="section-title">COMMUNICATIONS</h3>

      {isLoading ? (
        <LoadingSkeleton lines={3} />
      ) : !auth?.authenticated ? (
        <p className="text-sm text-text-secondary py-4">
          Email not connected
        </p>
      ) : (
        <div className="space-y-0">
          <div className="flex items-center justify-between py-3.5 border-b border-border/50">
            <div>
              <p className="text-[14px] text-text-primary">Unread Volume</p>
              <p className="text-[11px] text-text-secondary mt-0.5">
                {messages?.length ?? 0} total messages
              </p>
            </div>
            <span className="font-mono text-xl font-bold text-text-primary">
              {unread}
            </span>
          </div>
          <div className="flex items-center justify-between py-3.5">
            <div>
              <p className="text-[14px] text-text-primary">Priority Threads</p>
              <p className="text-[11px] text-text-secondary mt-0.5">marked important</p>
            </div>
            <span className="font-mono text-xl font-bold text-text-primary">
              {priority}
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
