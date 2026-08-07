import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell, Loader2 } from 'lucide-react'
import { meApi } from '@/api/me'
import { useAuthStore } from '@/stores/auth-store'
import { cn } from '@/lib/cn'

export function NotificationBell() {
  const token = useAuthStore((s) => s.access_token)
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)

  const inbox = useQuery({
    queryKey: ['notifications'],
    enabled: Boolean(token),
    queryFn: () => meApi.listNotifications(token!),
  })

  const unread = (inbox.data ?? []).filter((n) => !n.read).length

  const readMu = useMutation({
    mutationFn: (id: string) => meApi.markNotificationRead(id, token!),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['notifications'] })
    },
  })

  if (!token) return null

  return (
    <div className="relative">
      <button
        type="button"
        title="通知"
        aria-label="通知"
        onClick={() => setOpen((v) => !v)}
        className="relative grid h-9 w-9 cursor-pointer place-items-center rounded-xl text-white/50 transition hover:bg-white/[0.08] hover:text-white"
      >
        <Bell className="h-4 w-4" />
        {unread > 0 ? (
          <span className="absolute -top-0.5 -right-0.5 grid h-4 min-w-4 place-items-center rounded-full bg-[#ff705c] px-1 text-[9px] font-bold text-white">
            {unread > 9 ? '9+' : unread}
          </span>
        ) : null}
      </button>

      {open ? (
        <>
          <button
            type="button"
            aria-label="关闭通知"
            className="fixed inset-0 z-40 cursor-default"
            onClick={() => setOpen(false)}
          />
          <div className="absolute bottom-full left-1/2 z-50 mb-2 w-72 -translate-x-1/2 rounded-xl border border-white/10 bg-[#161a20] p-2 shadow-2xl">
            <p className="px-2 py-1 font-mono text-[10px] tracking-wider text-white/40 uppercase">
              站内通知
            </p>
            {inbox.isLoading ? (
              <p className="flex items-center gap-2 px-2 py-4 text-xs text-white/40">
                <Loader2 className="h-3.5 w-3.5 animate-spin" /> 加载中…
              </p>
            ) : (inbox.data ?? []).length === 0 ? (
              <p className="px-2 py-4 text-xs text-white/35">暂无通知</p>
            ) : (
              <ul className="max-h-64 space-y-1 overflow-y-auto">
                {(inbox.data ?? []).slice(0, 20).map((n) => (
                  <li key={n.id}>
                    <button
                      type="button"
                      onClick={() => {
                        if (!n.read) readMu.mutate(n.id)
                      }}
                      className={cn(
                        'w-full rounded-lg px-2 py-2 text-left text-xs transition hover:bg-white/[0.06]',
                        n.read ? 'text-white/45' : 'text-white/85',
                      )}
                    >
                      <p className="font-medium">{n.title}</p>
                      <p className="mt-0.5 line-clamp-2 text-white/45">{n.body}</p>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      ) : null}
    </div>
  )
}
