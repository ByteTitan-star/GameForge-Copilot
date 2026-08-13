import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ChevronRight, Gamepad2, LayoutGrid, Sparkles, Users } from 'lucide-react'
import { adminApi } from '@/api/admin'
import { analyticsApi } from '@/api/analytics'
import { useAuthStore } from '@/stores/auth-store'
import { useT } from '@/i18n/use-t'
import { Gauge } from '@/components/admin/Gauge'
import { AnalyticsTrendChart } from '@/components/usage/UsageBreakdown'

/** admin 橙色 hex，喂给 recharts（绕过 useThemeColors 读 <html> 的限制） */
const ORANGE = '#ef4d23'
const ORANGE_2 = '#f97316'

function abbreviate(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`
  return String(n)
}

/**
 * admin 概览首页（Convix 风卡墙）。取代旧 /admin/index → /admin/queue 的冷清跳转，
 * 给运营一进入后台就看到游戏工坊的关键脉搏：待审批 / 已发布 / 今日 Token / 用户，
 * + Token 配额池使用率 gauge + Top 游戏榜 + 30 日访问趋势。
 *
 * 数据全部来自现有接口（不复用子页分页列表缓存，避免 size 污染子页表格）：
 * - queue/analytics/usage/settings：精确可用
 * - 已发布数 / 用户数：用 list total（size=1 省流量）
 * - 「今日生成游戏数」后端无接口，不编造，故不做该卡。
 * gauge 语义 = 今日全站 Token / (默认单人日配额 × 用户数)，即「默认配额池」使用率。
 */
export function OverviewSection() {
  const t = useT()
  const token = useAuthStore((s) => s.access_token)

  const usage = useQuery({
    queryKey: ['admin', 'overview', 'usage'],
    queryFn: () => adminApi.usage(token!),
  })
  const settings = useQuery({
    queryKey: ['admin', 'overview', 'settings'],
    queryFn: () => adminApi.getSettings(token!),
  })
  const queue = useQuery({
    queryKey: ['admin', 'overview', 'queue'],
    queryFn: () => adminApi.listPublishQueue(token!),
  })
  const published = useQuery({
    queryKey: ['admin', 'overview', 'published'],
    queryFn: () => adminApi.listGames(token!, 'published', 1, 1),
  })
  const users = useQuery({
    queryKey: ['admin', 'overview', 'users'],
    queryFn: () => adminApi.listUsers(token!, 1, 1),
  })
  const analytics = useQuery({
    queryKey: ['admin', 'overview', 'analytics'],
    queryFn: () => analyticsApi.getTop(token!),
  })

  if (!token) return null

  const todayTokens =
    (usage.data?.system.today.input_tokens ?? 0) + (usage.data?.system.today.output_tokens ?? 0)
  const pending =
    (queue.data?.data ?? []).filter((x) => x.status === 'submitted' || x.status === 'reviewing')
      .length
  const publishedCount = published.data?.total ?? 0
  const userCount = users.data?.total ?? 0
  const defaultDaily = settings.data?.default_daily_token_limit ?? 0
  const quotaPool = defaultDaily * Math.max(userCount, 1)
  const gaugeValue = quotaPool > 0 ? Math.round((todayTokens / quotaPool) * 100) : 0
  const topGames = analytics.data?.top_games ?? []
  const trend = analytics.data?.trend ?? []
  const loading = usage.isLoading || queue.isLoading

  return (
    <div className="space-y-6">
      {/* Hero 小标题区：badge + 标题（Inter 半粗 + Instrument Serif 斜体关键词）+ 副标题 */}
      <div className="flex flex-col items-start gap-4">
        <span className="inline-flex items-center gap-2 rounded-full bg-white px-4 py-1.5 text-[13px] shadow-sm">
          <span className="h-1.5 w-1.5 rounded-full bg-[#ef4d23]" />
          {t('adminOverviewBadge')}
        </span>
        <h1
          className="max-w-3xl text-[var(--gf-text)]"
          style={{ fontSize: 'clamp(28px, 5vw, 44px)', lineHeight: 1.08, fontWeight: 600, letterSpacing: '-0.02em' }}
        >
          {t('adminOverviewTitlePre')}{' '}
          <span className="gf-admin-serif-italic">{t('adminOverviewTitleAccent')}</span>
          {t('adminOverviewTitlePost')}
        </h1>
        <p className="max-w-2xl text-sm text-neutral-700">{t('adminOverviewSubtitle')}</p>
      </div>

      {/* 4 张 KPI 卡 */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-4 lg:grid-cols-4">
        <KpiCard label={t('adminOverviewKpiPending')} value={String(pending)} accent loading={queue.isLoading} href="/admin/queue" cta={t('adminOverviewGoReview')} />
        <KpiCard label={t('adminOverviewKpiPublished')} value={publishedCount.toLocaleString()} loading={published.isLoading} href="/admin/published" cta={t('adminOverviewGoPublished')} />
        <KpiCard label={t('adminOverviewKpiTodayTokens')} value={abbreviate(todayTokens)} caption={t('adminOverviewTodayTokensCaption')} loading={usage.isLoading} href="/admin/usage" cta={t('adminOverviewGoUsage')} />
        <KpiCard label={t('adminOverviewKpiUsers')} value={userCount.toLocaleString()} loading={users.isLoading} href="/admin/users" cta={t('adminOverviewGoUsers')} />
      </div>

      {/* gauge + Top 游戏 + 趋势：第二排 */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-4 lg:grid-cols-3">
        {/* Token 配额池 gauge 卡 */}
        <section className="gf-admin-card rounded-2xl p-5">
          <div className="mb-2 flex items-baseline justify-between">
            <span className="text-[13px] font-medium text-[#ef4d23]">{t('adminOverviewQuotaTitle')}</span>
            <span className="text-[11px] text-neutral-500">{t('adminOverviewQuotaPeriod')}</span>
          </div>
          <Gauge
            value={gaugeValue}
            color={ORANGE}
            showLabels
            min={abbreviate(todayTokens)}
            max={abbreviate(quotaPool)}
          />
          <p className="mt-3 text-center text-[11px] text-neutral-500">{t('adminOverviewQuotaCaption')}</p>
        </section>

        {/* Top 游戏榜卡 */}
        <section className="gf-admin-card rounded-2xl p-5">
          <div className="mb-3 flex items-center gap-2">
            <Gamepad2 className="h-4 w-4 text-[#ef4d23]" />
            <span className="text-[13px] font-medium text-[var(--gf-text)]">{t('adminOverviewTopGames')}</span>
          </div>
          {topGames.length === 0 ? (
            <p className="py-8 text-center text-xs text-neutral-500">{t('adminOverviewNoTopGames')}</p>
          ) : (
            <ul className="space-y-2">
              {topGames.slice(0, 5).map((g, i) => {
                const maxPlays = topGames[0]?.play_count || 1
                const ratio = maxPlays > 0 ? g.play_count / maxPlays : 0
                return (
                  <li key={g.game_id} className="text-sm">
                    <div className="flex items-center gap-2.5">
                      <span className="grid h-5 w-5 shrink-0 place-items-center rounded-md bg-[rgba(239,77,35,0.1)] text-[11px] font-semibold tabular-nums text-[#ef4d23]">
                        {i + 1}
                      </span>
                      <span className="truncate text-[var(--gf-text)]">{g.title}</span>
                      <span className="ml-auto font-mono text-xs tabular-nums text-neutral-500">
                        {g.play_count.toLocaleString()}
                      </span>
                    </div>
                    <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-[rgba(15,23,42,0.06)]">
                      <div
                        className="h-full rounded-full"
                        style={{ width: `${Math.max(ratio * 100, ratio > 0 ? 4 : 0)}%`, backgroundColor: 'rgba(239,77,35,0.5)' }}
                      />
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
        </section>

        {/* 30 日访问趋势卡 */}
        <section className="gf-admin-card rounded-2xl p-5 lg:col-span-1">
          <div className="mb-3 flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-[#ef4d23]" />
            <span className="text-[13px] font-medium text-[var(--gf-text)]">{t('adminOverviewTrend')}</span>
          </div>
          {trend.length === 0 ? (
            <p className="py-8 text-center text-xs text-neutral-500">{t('adminOverviewNoTrend')}</p>
          ) : (
            <AnalyticsTrendChart data={trend} tone="light" primaryHex={ORANGE} secondaryHex={ORANGE_2} />
          )}
        </section>
      </div>

      {loading ? (
        <p className="sr-only" role="status">{t('loading')}</p>
      ) : null}
    </div>
  )
}

/** KPI 卡：Convix Card1 风（白底 rounded-2xl，橙色小标题 + 大数字 + 跳转 CTA） */
function KpiCard({
  label,
  value,
  caption,
  accent,
  loading,
  href,
  cta,
}: {
  label: string
  value: string
  caption?: string
  accent?: boolean
  loading?: boolean
  href?: string
  cta?: string
}) {
  return (
    <section className="gf-admin-card gf-admin-card-hover flex flex-col rounded-2xl p-5">
      <div className="flex items-center gap-2 text-[13px]">
        {accent ? <Users className="h-3.5 w-3.5 text-[#ef4d23]" /> : <LayoutGrid className="h-3.5 w-3.5 text-neutral-400" />}
        <span className={accent ? 'font-medium text-[#ef4d23]' : 'text-neutral-500'}>{label}</span>
      </div>
      <p className="mt-3 text-[28px] font-semibold tabular-nums text-[var(--gf-text)]">
        {loading ? '—' : value}
      </p>
      {caption ? <p className="mt-1 text-[11px] text-neutral-500">{caption}</p> : null}
      {href && cta ? (
        <Link
          to={href}
          className="mt-4 inline-flex items-center gap-1 text-xs font-medium text-[var(--gf-text)] transition-colors hover:text-[#ef4d23]"
        >
          {cta}
          <ChevronRight className="h-3.5 w-3.5" />
        </Link>
      ) : null}
    </section>
  )
}
