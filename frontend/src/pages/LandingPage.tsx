import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, ChevronRight, LogOut, MessageSquareText, Bot, Gamepad2, ShieldCheck } from 'lucide-react'
import { publicGamesApi } from '@/api/public-games'
import { PublicGameCard } from '@/components/games/PublicGameCard'
import { OfficialGameCards } from '@/components/onboarding/OfficialGameCards'
import { FeaturedGamesStrip } from '@/components/discover/FeaturedGamesStrip'
import { FadeIn } from '@/components/ui/fade-in'
import { MagneticButton } from '@/components/ui/magnetic-button'
import { Button } from '@/components/ui/button'
import { useT } from '@/i18n/use-t'
import { useLocaleStore } from '@/stores/locale-store'
import { useAuthStore } from '@/stores/auth-store'
import { isTrialUser } from '@/lib/trial'
import { cn } from '@/lib/cn'
import heroArt from '@/assets/hero.png'

const HERO_VIDEO =
  'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260729_102822_0e6c87e8-c141-4744-bf32-ad30db296371.mp4'

export function LandingPage() {
  const t = useT()
  const locale = useLocaleStore((s) => s.locale)
  const token = useAuthStore((s) => s.access_token)
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)
  const ctaTo = token ? '/forge' : '/register'

  const publicQuery = useQuery({
    queryKey: ['public-games', 'landing', locale],
    queryFn: () => publicGamesApi.list(locale),
  })

  const services = useMemo(
    () => [t('landingService1'), t('landingService2'), t('landingService3'), t('landingService4')],
    [locale],
  )

  const features = useMemo(
    () => [
      { icon: MessageSquareText, title: t('landingFeature1Title'), body: t('landingFeature1Body') },
      { icon: Bot, title: t('landingFeature2Title'), body: t('landingFeature2Body') },
      { icon: Gamepad2, title: t('landingFeature3Title'), body: t('landingFeature3Body') },
      { icon: ShieldCheck, title: t('landingFeature4Title'), body: t('landingFeature4Body') },
    ],
    [locale],
  )

  const staticCases = useMemo(
    () => [
      { title: t('landingCase1Title'), tag: t('landingCase1Tag'), blurb: t('landingCase1Blurb'), slug: null as string | null },
      { title: t('landingCase2Title'), tag: t('landingCase2Tag'), blurb: t('landingCase2Blurb'), slug: null },
      { title: t('landingCase3Title'), tag: t('landingCase3Tag'), blurb: t('landingCase3Blurb'), slug: null },
    ],
    [locale],
  )

  const publishedCases = publicQuery.data?.slice(0, 3) ?? []
  const useLiveCases = publishedCases.length > 0

  return (
    <div className="relative min-h-screen bg-[#0a0a0a] text-white">
      <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden" aria-hidden>
        <video
          className="h-full w-full object-cover"
          src={HERO_VIDEO}
          autoPlay
          muted
          loop
          playsInline
          poster={heroArt}
        />
        {/* 压暗仅用于保证白字可读：底部渐深衔接下方内容区，中段保持通透 */}
        <div className="absolute inset-0 bg-gradient-to-b from-black/45 via-black/30 to-black/65" />
      </div>

      <div className="relative z-10">
        <section className="flex min-h-[100svh] min-h-screen flex-col px-5 pb-12 pt-6 sm:px-8 md:px-12">
          <header className="flex flex-wrap items-center justify-between gap-3 border-b border-white/15 pb-4">
            <Link
              to="/home"
              className="text-lg font-medium tracking-tight transition-opacity hover:opacity-90 sm:text-xl"
            >
              {t('brand')}
            </Link>
            <div className="flex flex-wrap items-center justify-end gap-2 sm:gap-3">
              {token && user ? (
                <span
                  className="hidden max-w-[min(100%,220px)] truncate rounded-full border border-white/20 bg-white/10 px-3 py-1.5 text-xs text-white/90 backdrop-blur-sm sm:inline-block"
                  title={user.email}
                >
                  {t('loggedInAs').replace('{email}', user.email)}
                </span>
              ) : null}
              {token ? (
                <>
                  <Link
                    to="/discover"
                    className="hidden cursor-pointer text-sm text-white/80 transition-colors hover:text-white sm:inline"
                  >
                    {t('discover')}
                  </Link>
                  <Link
                    to="/games"
                    className="hidden cursor-pointer text-sm text-white/80 transition-colors hover:text-white sm:inline"
                  >
                    {t('games')}
                  </Link>
                  <Link to="/games">
                    <Button
                      variant="secondary"
                      className="rounded-md transition-transform duration-200 hover:scale-[1.03] active:scale-[0.98] sm:hidden"
                    >
                      {t('games')}
                    </Button>
                  </Link>
                  <Link to="/forge">
                    <Button
                      variant="secondary"
                      className="hidden rounded-md transition-transform duration-200 hover:scale-[1.03] active:scale-[0.98] sm:inline-flex"
                    >
                      {t('forge')}
                    </Button>
                  </Link>
                  <Link to="/settings">
                    <Button
                      variant="secondary"
                      className="hidden rounded-md transition-transform duration-200 hover:scale-[1.03] active:scale-[0.98] md:inline-flex"
                    >
                      {t('settings')}
                    </Button>
                  </Link>
                  <Button
                    type="button"
                    variant="secondary"
                    className="inline-flex items-center gap-1.5 rounded-md transition-transform duration-200 hover:scale-[1.03] active:scale-[0.98]"
                    onClick={() => void logout()}
                  >
                    <LogOut className="h-3.5 w-3.5" />
                    {t('logout')}
                  </Button>
                </>
              ) : (
                <>
                  <Link
                    to="/login"
                    className="hidden cursor-pointer text-sm text-white/85 transition-colors duration-200 hover:text-white sm:inline"
                  >
                    {t('login')}
                  </Link>
                  <Link to="/register">
                    <Button
                      variant="secondary"
                      className="rounded-md transition-transform duration-200 hover:scale-[1.03] active:scale-[0.98]"
                    >
                      {t('register')}
                    </Button>
                  </Link>
                </>
              )}
            </div>
          </header>

          {token && user ? (
            <p className="mt-3 truncate text-xs text-white/75 sm:hidden" title={user.email}>
              {t('loggedInAs').replace('{email}', user.email)}
            </p>
          ) : null}

          <div className="flex flex-1 flex-col justify-between pt-24 sm:pt-28">
            <div className="flex flex-col justify-between gap-10 lg:flex-row lg:items-start">
              <div className="flex flex-col justify-between gap-8 sm:flex-row sm:flex-1">
                <ul className="space-y-2.5">
                  {services.map((s, i) => (
                    <FadeIn key={s} delayMs={150 + i * 120}>
                      <li className="font-mono text-[13px] tracking-[0.15em] text-white/95 uppercase drop-shadow-md transition-colors duration-200 hover:text-white">
                        {s}
                      </li>
                    </FadeIn>
                  ))}
                </ul>
                <FadeIn delayMs={300} className="max-w-xs sm:text-right">
                  <p className="text-lg leading-relaxed text-white drop-shadow-md sm:text-xl">{t('tagline')}</p>
                </FadeIn>
              </div>
              <FadeIn delayMs={220} className="hidden shrink-0 lg:block">
                <img
                  src={heroArt}
                  alt=""
                  className="h-36 w-36 object-contain opacity-90 drop-shadow-[0_20px_40px_rgba(0,0,0,0.45)] transition-transform duration-500 hover:scale-105 hover:opacity-100"
                />
              </FadeIn>
            </div>

            <div className="mt-16 flex flex-col items-end justify-between gap-8 md:mt-0 md:flex-row md:items-end">
              <div>
                <FadeIn delayMs={150}>
                  <div className="mb-5 border-l-2 border-white bg-white/15 px-3.5 py-2 font-mono text-xs font-semibold tracking-[0.15em] uppercase backdrop-blur-sm transition-colors duration-200 hover:bg-white/25">
                    {t('landingBadge')}
                  </div>
                </FadeIn>
                <FadeIn delayMs={280}>
                  <h1 className="text-5xl font-normal leading-[1.05] tracking-tight text-white drop-shadow-lg sm:text-6xl lg:text-7xl">
                    {t('landingHero1')}
                    <br />
                    {t('landingHero2')}
                    <br />
                    {t('landingHero3')}
                  </h1>
                </FadeIn>
              </div>
              <FadeIn delayMs={420} className="flex flex-wrap items-center gap-3">
                <Link to={ctaTo}>
                  <MagneticButton className="!rounded-full">
                    {t('startForge')}
                    <ChevronRight size={14} />
                  </MagneticButton>
                </Link>
                <Link to="/forge?template=snake">
                  <Button
                    variant="secondary"
                    className="rounded-full px-6 py-3 transition-transform duration-200 hover:scale-[1.03] active:scale-[0.98]"
                  >
                    {t('templateStart')}
                  </Button>
                </Link>
                <a href="#cases">
                  <Button
                    variant="secondary"
                    className="rounded-full px-6 py-3 transition-transform duration-200 hover:scale-[1.03] active:scale-[0.98]"
                  >
                    {t('viewCases')}
                  </Button>
                </a>
              </FadeIn>
            </div>
          </div>
        </section>

        <section
          id="quick-start"
          className="border-t border-white/15 bg-[#111315] px-5 py-16 sm:px-8 md:px-12"
        >
          <div className="mx-auto max-w-7xl">
            <FadeIn>
              <OfficialGameCards
                accessToken={token}
                trial={user ? isTrialUser(user) : false}
              />
            </FadeIn>
          </div>
        </section>

        <section className="border-t border-white/15 bg-[#0f1113] px-5 py-16 sm:px-8 md:px-12">
          <div className="mx-auto max-w-7xl">
            <FadeIn>
              <FeaturedGamesStrip variant="dark" />
            </FadeIn>
          </div>
        </section>

        <section
          id="features"
          className="border-t border-white/15 bg-[#111315] px-5 py-16 sm:px-8 md:px-12"
        >
          <div className="mx-auto max-w-7xl">
            <FadeIn>
              <p className="font-mono text-xs font-semibold tracking-[0.15em] text-white/65 uppercase">
                {t('whatYouGet')}
              </p>
              <h2 className="mt-2 text-3xl font-normal tracking-tight drop-shadow-md sm:text-4xl">
                {t('featuresTitle')}
              </h2>
            </FadeIn>
            <div className="mt-10 grid gap-4 sm:grid-cols-2">
              {features.map((f, i) => (
                <FadeIn key={f.title} delayMs={80 + i * 80}>
                  <article
                    className={cn(
                      'group h-full rounded-2xl border border-white/10 bg-[#1a1d21] p-6',
                      'transition-all duration-300 ease-out',
                      'hover:-translate-y-1 hover:border-white/25 hover:bg-[#20242a]',
                    )}
                  >
                    <f.icon className="mb-4 h-6 w-6 text-white/85 transition-transform duration-300 group-hover:scale-110" />
                    <h3 className="text-lg font-medium text-white">{f.title}</h3>
                    <p className="mt-2 text-sm leading-relaxed text-white/70">{f.body}</p>
                  </article>
                </FadeIn>
              ))}
            </div>
          </div>
        </section>

        <section id="cases" className="border-t border-white/15 bg-[#0f1113] px-5 py-16 sm:px-8 md:px-12">
          <div className="mx-auto max-w-7xl">
            <FadeIn>
              <div className="flex flex-wrap items-end justify-between gap-4">
                <div>
                  <p className="font-mono text-xs font-semibold tracking-[0.15em] text-white/65 uppercase">
                    Cases
                  </p>
                  <h2 className="mt-2 text-3xl font-normal tracking-tight drop-shadow-md sm:text-4xl">
                    {t('casesTitle')}
                  </h2>
                </div>
                <Link to={useLiveCases ? '/discover' : ctaTo}>
                  <MagneticButton className="!rounded-full !px-5 !py-2.5 text-xs sm:text-sm">
                    {useLiveCases ? t('discoverAll') : t('makeOneToo')}
                    <ArrowRight className="h-4 w-4" />
                  </MagneticButton>
                </Link>
              </div>
            </FadeIn>
            <div className="mt-10 grid gap-4 md:grid-cols-3">
              {useLiveCases
                ? publishedCases.map((g, i) => (
                    <FadeIn key={g.game_id} delayMs={60 + i * 90}>
                      <PublicGameCard game={g} />
                    </FadeIn>
                  ))
                : staticCases.map((c, i) => (
                    <FadeIn key={c.title} delayMs={60 + i * 90}>
                      <article className="flex h-full flex-col rounded-2xl border border-white/10 bg-[#1a1d21] p-5 transition-all duration-300 hover:-translate-y-1 hover:border-white/25 hover:bg-[#20242a]">
                        <p className="font-mono text-[11px] font-semibold tracking-[0.14em] text-white/60 uppercase">
                          {c.tag}
                        </p>
                        <h3 className="mt-3 text-xl font-medium text-white">{c.title}</h3>
                        <p className="mt-2 flex-1 text-sm leading-relaxed text-white/70">{c.blurb}</p>
                        <Link
                          to={token ? '/games' : '/register'}
                          className="mt-4 inline-flex cursor-pointer items-center gap-1 text-sm font-medium text-white transition-all duration-200 hover:gap-2"
                        >
                          {t('trySimilar')} <ArrowRight className="h-3.5 w-3.5" />
                        </Link>
                      </article>
                    </FadeIn>
                  ))}
            </div>
          </div>
        </section>

        <footer className="border-t border-white/15 bg-[#111315] px-5 py-12 sm:px-8 md:px-12">
          <div className="mx-auto flex max-w-7xl flex-col items-start justify-between gap-6 md:flex-row md:items-center">
            <div>
              <h2 className="text-2xl font-normal tracking-tight drop-shadow-md">{t('footerTitle')}</h2>
              <p className="mt-2 text-sm text-white/70">{t('footerSubtitle')}</p>
            </div>
            <Link to={ctaTo}>
              <MagneticButton className="!rounded-full">
                {t('startForge')}
                <ChevronRight size={14} />
              </MagneticButton>
            </Link>
          </div>
        </footer>
      </div>
    </div>
  )
}
