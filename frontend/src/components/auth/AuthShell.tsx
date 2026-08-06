import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useLocaleStore } from '@/stores/locale-store'
import { useT } from '@/i18n/use-t'
import { env } from '@/lib/env'
import { cn } from '@/lib/cn'
import { FadeIn } from '@/components/ui/fade-in'
import heroArt from '@/assets/hero.png'

const AUTH_VIDEO =
  'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260403_050628_c4e32401-fab4-4a27-b7a8-6e9291cd5959.mp4'

type Props = {
  children: ReactNode
  title: string
  subtitle?: string
}

/** 恢复：全屏动态视频 + liquid-glass 表单；只加强交互，不换成静态 mesh */
export function AuthShell({ children, title, subtitle }: Props) {
  const t = useT()
  const locale = useLocaleStore((s) => s.locale)
  const setLocale = useLocaleStore((s) => s.setLocale)

  return (
    <div className="relative min-h-screen overflow-hidden bg-black text-white">
      <video
        className="absolute inset-0 h-full w-full object-cover"
        src={AUTH_VIDEO}
        autoPlay
        muted
        loop
        playsInline
        poster={heroArt}
        aria-hidden
      />

      <div className="relative z-10 flex min-h-screen flex-col px-5 pb-12 pt-6 sm:px-8 md:px-12">
        <header className="flex items-center justify-between gap-4">
          <Link
            to="/"
            className="liquid-glass rounded-xl px-4 py-2 text-lg font-semibold tracking-tight transition-transform duration-200 hover:scale-[1.03] active:scale-[0.98]"
          >
            {t('brand')}
          </Link>
          <div className="liquid-glass flex rounded-full p-1 text-xs font-semibold uppercase tracking-wider">
            {(['zh', 'en'] as const).map((l) => (
              <button
                key={l}
                type="button"
                aria-pressed={locale === l}
                onClick={() => setLocale(l)}
                className={cn(
                  'cursor-pointer rounded-full px-3 py-1.5 transition-all duration-200',
                  locale === l
                    ? 'bg-white text-black shadow-sm'
                    : 'text-white/70 hover:bg-white/10 hover:text-white',
                )}
              >
                {l === 'zh' ? '中文' : 'EN'}
              </button>
            ))}
          </div>
        </header>

        {env.useMock ? (
          <p className="mt-4 font-mono text-[10px] uppercase tracking-[0.15em] text-white/55 drop-shadow-md">
            {t('mockBanner')}
          </p>
        ) : null}

        <main className="flex flex-1 flex-col justify-end pt-16 md:justify-center md:pt-10">
          <div className="mx-auto w-full max-w-md">
            <FadeIn>
              <div className="mb-6">
                <div className="mb-4 flex items-center gap-3">
                  <img
                    src={heroArt}
                    alt=""
                    className="h-10 w-10 object-contain opacity-90 drop-shadow-lg"
                  />
                  <p className="font-mono text-[11px] uppercase tracking-[0.15em] text-white/70 drop-shadow-md">
                    {t('tagline')}
                  </p>
                </div>
                <h1 className="text-3xl font-normal tracking-tight text-white drop-shadow-lg sm:text-4xl">
                  {title}
                </h1>
                {subtitle ? (
                  <p className="mt-2 text-sm text-white/75 drop-shadow-md">{subtitle}</p>
                ) : null}
              </div>
            </FadeIn>
            <FadeIn delayMs={120}>
              <div className="liquid-glass rounded-2xl border border-white/15 p-5 transition-shadow duration-300 hover:shadow-[0_20px_60px_rgba(0,0,0,0.35)] sm:p-6">
                {children}
              </div>
            </FadeIn>
          </div>
        </main>
      </div>
    </div>
  )
}
