import { env } from '@/lib/env'
import { apiRequest } from './client'

export type UsageBreakdownItem = {
  game_id: string
  title: string
  input_tokens: number
  output_tokens: number
  estimated_cost_usd: number
}

export type UsageBreakdown = {
  items: UsageBreakdownItem[]
  total_estimated_cost_usd: number
}

const MOCK_BREAKDOWN: UsageBreakdown = {
  total_estimated_cost_usd: 0.42,
  items: [
    {
      game_id: '00000000-0000-4000-8000-000000000101',
      title: '霓虹贪吃蛇',
      input_tokens: 12400,
      output_tokens: 8200,
      estimated_cost_usd: 0.18,
    },
    {
      game_id: '00000000-0000-4000-8000-000000000102',
      title: '像素跑酷',
      input_tokens: 9800,
      output_tokens: 6100,
      estimated_cost_usd: 0.14,
    },
    {
      game_id: '00000000-0000-4000-8000-000000000103',
      title: '塔防雏形',
      input_tokens: 15200,
      output_tokens: 9400,
      estimated_cost_usd: 0.1,
    },
  ],
}

async function tryFetchBreakdown(token: string): Promise<UsageBreakdown | null> {
  const res = await fetch(`${env.apiBaseUrl}/me/usage/breakdown`, {
    headers: { Accept: 'application/json', Authorization: `Bearer ${token}` },
  })
  if (!res.ok) return null
  const json = (await res.json()) as { data?: UsageBreakdown }
  if (!json.data?.items) return null
  return json.data
}

export const usageBreakdownApi = {
  async get(accessToken: string): Promise<UsageBreakdown> {
    if (import.meta.env.VITE_USAGE_BREAKDOWN_MOCK === 'true') {
      return MOCK_BREAKDOWN
    }
    try {
      const live = await tryFetchBreakdown(accessToken)
      if (live) return live
      const viaClient = await apiRequest<UsageBreakdown>('/me/usage/breakdown', {
        token: accessToken,
      })
      if (viaClient.items) return viaClient
    } catch {
      /* mock fallback */
    }
    return MOCK_BREAKDOWN
  },
}

export { MOCK_BREAKDOWN }
