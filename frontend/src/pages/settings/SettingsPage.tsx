import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { useT } from '@/i18n/use-t'
import { useAuthStore } from '@/stores/auth-store'
import { LlmConfigPanel } from './LlmConfigPanel'
import { UsagePanel } from './UsagePanel'

export function SettingsPage() {
  const t = useT()
  const user = useAuthStore((s) => s.user)

  return (
    <div className="space-y-6">
      <div>
        <p className="font-mono text-[10px] tracking-[0.16em] text-white/35 uppercase">Account</p>
        <h1 className="text-2xl tracking-tight text-white/95 md:text-3xl">{t('settings')}</h1>
        <p className="mt-1 text-sm text-white/40">LLM 配置、用量与账号</p>
      </div>

      <section className="rounded-2xl border border-white/[0.08] bg-[#12151a] p-5">
        <h2 className="text-lg text-white/90">账号</h2>
        <dl className="mt-3 space-y-2 text-sm text-white/45">
          {[
            ['邮箱', user?.email],
            ['角色', user?.role],
            ['邮箱验证', user?.email_verified ? '已验证' : '未验证'],
          ].map(([k, v]) => (
            <div
              key={String(k)}
              className="flex justify-between gap-4 rounded-xl bg-black/25 px-3 py-2 ring-1 ring-white/[0.04]"
            >
              <dt>{k}</dt>
              <dd className="text-white/85">{v}</dd>
            </div>
          ))}
        </dl>
        {!user?.email_verified ? (
          <Link to="/verify-email" className="mt-4 inline-flex">
            <Button className="!rounded-lg !bg-teal-400 !text-black hover:!bg-teal-300">去验证邮箱</Button>
          </Link>
        ) : null}
      </section>

      <LlmConfigPanel />
      <UsagePanel />
    </div>
  )
}
