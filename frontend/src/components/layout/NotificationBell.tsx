import { useState } from 'react'
import { createPortal } from 'react-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell, Loader2 } from 'lucide-react'
import { meApi } from '@/api/me'
import { useT } from '@/i18n/use-t'
import { useAuthStore } from '@/stores/auth-store'
import { cn } from '@/lib/cn'

export function NotificationBell() {
  const t = useT()
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
        title={t('notifications')}
        aria-label={t('notifications')}
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => setOpen((v) => !v)}
        className="gf-interactive gf-text-accent relative grid h-9 w-9 cursor-pointer place-items-center rounded-xl transition hover:bg-black/[0.06] hover:text-[var(--gf-text)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gf-accent)]/50"
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
            aria-label={t('closeNotifications')}
            className="fixed inset-0 z-40 cursor-default"
            onClick={() => setOpen(false)}
          />
          {createPortal(
            <div
              role="dialog"
              aria-label={t('inboxTitle')}
              className="gf-notification-popover gf-border-subtle fixed bottom-4 left-[calc(var(--gf-sidebar-w)+0.5rem)] z-[60] w-[min(20rem,calc(100vw-var(--gf-sidebar-w)-1rem))] max-w-[calc(100vw-1rem)] max-h-[min(28rem,calc(100dvh-2rem))] overflow-hidden rounded-xl border bg-[var(--gf-surface)] p-2 shadow-[0_16px_40px_rgba(15,23,42,0.18)]"
            >
            <p className="gf-page-muted px-2 py-1 font-mono text-[10px] tracking-wider uppercase">
              {t('inboxTitle')}
            </p>
            {inbox.isLoading ? (
                <p className="gf-page-muted flex items-center gap-2 px-2 py-4 text-xs">
                <Loader2 className="h-3.5 w-3.5 animate-spin" /> {t('loading')}
              </p>
            ) : (inbox.data ?? []).length === 0 ? (
              <p className="gf-page-muted px-2 py-4 text-xs">{t('noNotifications')}</p>
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
                        n.read ? 'gf-page-muted' : 'gf-page-body',
                      )}
                    >
                      <p className="font-medium">{n.title}</p>
                      <p className="gf-page-muted mt-0.5 line-clamp-2">{n.body}</p>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            </div>,
            document.body,
          )}
        </>
      ) : null}
    </div>
  )
}
