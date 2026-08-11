import { apiRequest } from './client'

export type AnalyticsTopItem = {
  game_id: string
  title: string
  slug: string | null
  play_count: number
}

export type AnalyticsTrendPoint = {
  date: string // YYYY-MM-DD
  page_views: number
  unique_visitors: number
}

export type AdminAnalytics = {
  top_games: AnalyticsTopItem[]
  trend: AnalyticsTrendPoint[]
}

export const analyticsApi = {
  async getTop(accessToken: string): Promise<AdminAnalytics> {
    return apiRequest<AdminAnalytics>('/admin/analytics/top', { token: accessToken })
  },
}
