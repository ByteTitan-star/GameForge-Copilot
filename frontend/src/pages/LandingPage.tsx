import { Link } from 'react-router-dom'
import { ArrowRight, ChevronRight, MessageSquareText, Bot, Gamepad2, ShieldCheck } from 'lucide-react'
import { FadeIn } from '@/components/ui/fade-in'
import { MagneticButton } from '@/components/ui/magnetic-button'
import { Button } from '@/components/ui/button'
import { useT } from '@/i18n/use-t'
import { useAuthStore } from '@/stores/auth-store'
import { cn } from '@/lib/cn'
import heroArt from '@/assets/hero.png'

/** 保留动态视频底座；下方再叠能力 / Cases（在原版上增强，而非替换） */
const HERO_VIDEO =
  'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260729_102822_0e6c87e8-c141-4744-bf32-ad30db296371.mp4'

const services = ['/ 对话策划', '/ 代码生成', '/ 一键试玩', '/ 发布审批']

const features = [
  {
    icon: MessageSquareText,
    title: '对话即工坊',
    body: '左侧聊需求，右侧看生成进度，不必在工具间跳转。',
  },
  {
    icon: Bot,
    title: '多角色链路',
    body: '策划 → 美术 → 代码 → 质检；关键节点 HITL 确认。',
  },
  {
    icon: Gamepad2,
    title: '生成即可玩',
    body: '产物托管后 iframe 沙箱试玩，迭代再跑一轮。',
  },
  {
    icon: ShieldCheck,
    title: '自带 Key · 可计量',
    body: 'LLM apikey 加密存；用量按真实 token usage 记账。',
  },
]

const cases = [
  {
    title: '霓虹贪吃蛇',
    tag: 'Arcade · Draft',
    blurb: '一句话开局：方向键 + 计分，进工坊继续打磨。',
  },
  {
    title: '像素跑酷',
    tag: 'Runner · Published',
    blurb: '障碍节奏与皮肤切换，已有公开 slug 可试玩。',
  },
  {
    title: '塔防雏形',
    tag: 'Strategy · Forge',
    blurb: '路径与波次先 HITL 确认数值，再出可运行版本。',
  },
]

export function LandingPage() {
  const t = useT()
  const token = useAuthStore((s) => s.access_token)
  const ctaTo = token ? '/forge' : '/register'

  return (
    <div className="relative min-h-screen bg-[#0a0a0a] text-white">
      {/* 动态层：全页固定视频（原版核心） */}
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
        {/* 仅底部渐强，保证下半屏文字可读，不盖死整页 */}
        <div className="absolute inset-0 bg-gradient-to-b from-black/25 via-transparent to-black/75" />
      </div>

      <div className="relative z-10">
        {/* ===== Hero：沿用原版结构，加强交互 ===== */}
        <section className="flex min-h-[100svh] min-h-screen flex-col px-5 pb-12 pt-6 sm:px-8 md:px-12">
          <header className="flex items-center justify-between border-b border-white/15 pb-4">
            <span className="text-lg font-medium tracking-tight sm:text-xl">{t('brand')}</span>
            <div className="flex items-center gap-3">
              {token ? (
                <Link to="/games">
                  <Button
                    variant="secondary"
                    className="rounded-md transition-transform duration-200 hover:scale-[1.03] active:scale-[0.98]"
                  >
                    {t('games')}
                  </Button>
                </Link>
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

          <div className="flex flex-1 flex-col justify-between pt-24 sm:pt-28">
            <div className="flex flex-col justify-between gap-10 lg:flex-row lg:items-start">
              <div className="flex flex-col justify-between gap-8 sm:flex-row sm:flex-1">
                <ul className="space-y-2">
                  {services.map((s, i) => (
                    <FadeIn key={s} delayMs={150 + i * 120}>
                      <li className="font-mono text-xs uppercase tracking-[0.15em] text-white/90 drop-shadow-md transition-colors duration-200 hover:text-white">
                        {s}
                      </li>
                    </FadeIn>
                  ))}
                </ul>
                <FadeIn delayMs={300} className="max-w-xs sm:text-right">
                  <p className="text-lg leading-relaxed text-white drop-shadow-md sm:text-xl">
                    {t('tagline')}
                  </p>
                </FadeIn>
              </div>
              {/* 本地资产：增加一点原创辨识，不替代视频 */}
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
                  <div className="mb-5 border-l-2 border-white bg-white/15 px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.15em] backdrop-blur-md transition-colors duration-200 hover:bg-white/25">
                    From prompt to playable
                  </div>
                </FadeIn>
                <FadeIn delayMs={280}>
                  <h1 className="text-5xl font-normal leading-[1.05] tracking-tight text-white drop-shadow-lg sm:text-6xl lg:text-7xl">
                    Clear. Precise.
                    <br />
                    Playable.
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
                <a href="#cases">
                  <Button
                    variant="secondary"
                    className="rounded-full px-6 py-3 transition-transform duration-200 hover:scale-[1.03] active:scale-[0.98]"
                  >
                    看 Cases
                  </Button>
                </a>
              </FadeIn>
            </div>
          </div>
        </section>

        {/* ===== 增强区：仍压在动态视频上，用玻璃层 ===== */}
        <section
          id="features"
          className="border-t border-white/15 bg-black/35 px-5 py-16 backdrop-blur-md sm:px-8 md:px-12"
        >
          <div className="mx-auto max-w-6xl">
            <FadeIn>
              <p className="font-mono text-[11px] uppercase tracking-[0.15em] text-white/55">
                What you get
              </p>
              <h2 className="mt-2 text-3xl font-normal tracking-tight drop-shadow-md sm:text-4xl">
                为做小游戏排好的能力
              </h2>
            </FadeIn>
            <div className="mt-10 grid gap-4 sm:grid-cols-2">
              {features.map((f, i) => (
                <FadeIn key={f.title} delayMs={80 + i * 80}>
                  <article
                    className={cn(
                      'group rounded-2xl border border-white/15 bg-white/10 p-5 backdrop-blur-md',
                      'transition-all duration-300 ease-out',
                      'hover:-translate-y-1 hover:border-white/30 hover:bg-white/15',
                    )}
                  >
                    <f.icon className="mb-3 h-5 w-5 text-white/80 transition-transform duration-300 group-hover:scale-110" />
                    <h3 className="text-lg font-medium">{f.title}</h3>
                    <p className="mt-2 text-sm leading-relaxed text-white/70">{f.body}</p>
                  </article>
                </FadeIn>
              ))}
            </div>
          </div>
        </section>

        <section id="cases" className="border-t border-white/15 bg-black/45 px-5 py-16 backdrop-blur-md sm:px-8 md:px-12">
          <div className="mx-auto max-w-6xl">
            <FadeIn>
              <div className="flex flex-wrap items-end justify-between gap-4">
                <div>
                  <p className="font-mono text-[11px] uppercase tracking-[0.15em] text-white/55">
                    Cases
                  </p>
                  <h2 className="mt-2 text-3xl font-normal tracking-tight drop-shadow-md sm:text-4xl">
                    工坊里长出来的样例路径
                  </h2>
                </div>
                <Link to={ctaTo}>
                  <MagneticButton className="!rounded-full !px-5 !py-2.5 text-xs sm:text-sm">
                    开一个自己的
                    <ArrowRight className="h-4 w-4" />
                  </MagneticButton>
                </Link>
              </div>
            </FadeIn>
            <div className="mt-10 grid gap-4 md:grid-cols-3">
              {cases.map((c, i) => (
                <FadeIn key={c.title} delayMs={60 + i * 90}>
                  <article className="flex h-full flex-col rounded-2xl border border-white/15 bg-white/10 p-5 backdrop-blur-md transition-all duration-300 hover:-translate-y-1 hover:border-white/30 hover:bg-white/[0.16]">
                    <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-white/50">
                      {c.tag}
                    </p>
                    <h3 className="mt-3 text-xl font-medium">{c.title}</h3>
                    <p className="mt-2 flex-1 text-sm leading-relaxed text-white/70">{c.blurb}</p>
                    <Link
                      to={token ? '/games' : '/register'}
                      className="mt-4 inline-flex cursor-pointer items-center gap-1 text-sm text-white transition-all duration-200 hover:gap-2"
                    >
                      了解路径 <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                  </article>
                </FadeIn>
              ))}
            </div>
          </div>
        </section>

        <footer className="border-t border-white/15 bg-black/50 px-5 py-12 backdrop-blur-md sm:px-8 md:px-12">
          <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-6 md:flex-row md:items-center">
            <div>
              <h2 className="text-2xl font-normal tracking-tight drop-shadow-md">
                准备好锻造下一款小游戏了吗？
              </h2>
              <p className="mt-2 text-sm text-white/65">注册 → 验证邮箱 → 配置 LLM Key → 进入工坊。</p>
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
