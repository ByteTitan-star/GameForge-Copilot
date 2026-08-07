import { env } from '@/lib/env'
import { apiRequest } from './client'

export type AnalyticsTopItem = {
  game_id: string
  title: string
  slug: string
  page_views: number
  play_count: number
}

export type AnalyticsTrendPoint = {
  date: string
  page_views: number
  play_starts: number
}

export type AdminAnalytics = {
  top_games: AnalyticsTopItem[]
  trend: AnalyticsTrendPoint[]
}

const MOCK_ANALYTICS: AdminAnalytics = {
  top_games: [
    { game_id: '1', title: '霓虹贪吃蛇', slug: 'neon-snake', page_views: 4200, play_count: 1284 },
    { game_id: '2', title: '双人像素闯关', slug: 'coop-pixel-run', page_views: 3100, play_count: 892 },
    { game_id: '3', title: '治愈系收集', slug: 'cozy-collect', page_views: 1800, play_count: 456 },
  ],
  trend: [
    { date: '2026-08-01', page_views: 120, play_starts: 45 },
    { date: '2026-08-02', page_views: 180, play_starts: 62 },
    { date: '2026-08-03', page_views: 240, play_starts: 88 },
    { date: '2026-08-04', page_views: 210, play_starts: 75 },
    { date: '2026-08-05', page_views: 320, play_starts: 110 },
    { date: '2026-08-06', page_views: 290, play_starts: 98 },
    { date: '2026-08-07', page_views: 350, play_starts: 125 },
  ],
}

async function tryFetchAnalytics(token: string): Promise<AdminAnalytics | null> {
  const res = await fetch(`${env.apiBaseUrl}/admin/analytics/top`, {
    headers: { Accept: 'application/json', Authorization: `Bearer ${token}` },
  })
  if (!res.ok) return null
  const json = (await res.json()) as { data?: AdminAnalytics }
  if (!json.data?.top_games) return null
  return json.data
}

export const analyticsApi = {
  async getTop(accessToken: string): Promise<AdminAnalytics> {
    if (import.meta.env.VITE_ADMIN_ANALYTICS_MOCK === 'true') {
      return MOCK_ANALYTICS
    }
    try {
      const live = await tryFetchAnalytics(accessToken)
      if (live) return live
      return await apiRequest<AdminAnalytics>('/admin/analytics/top', { token: accessToken })
    } catch {
      return MOCK_ANALYTICS
    }
  },
}

export { MOCK_ANALYTICS }
