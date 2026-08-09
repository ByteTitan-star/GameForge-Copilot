import { apiRequest } from './client'

/** 后端 /admin/analytics/top 仅返回 play_count 排行（无 page_views）。 */
export type AnalyticsTopItem = {
  game_id: string
  title: string
  slug: string | null
  play_count: number
}

export type AnalyticsTrendPoint = {
  date: string
  page_views: number
  play_starts: number
}

export type AdminAnalytics = {
  top_games: AnalyticsTopItem[]
  /** 后端暂未提供 PV/试玩趋势，恒为空。 */
  trend: AnalyticsTrendPoint[]
}

export const analyticsApi = {
  async getTop(accessToken: string): Promise<AdminAnalytics> {
    const top_games = await apiRequest<AnalyticsTopItem[]>('/admin/analytics/top', {
      token: accessToken,
    })
    return { top_games, trend: [] }
  },
}
