import { apiRequestList } from './client'

/** 后端 UsageBreakdownItem 契约（id 非 game_id；estimated_usd 非 estimated_cost_usd）。 */
export type UsageBreakdownItem = {
  id: string
  title: string | null
  input_tokens: number
  output_tokens: number
  calls: number
  estimated_usd: number
}

export type UsageBreakdown = {
  items: UsageBreakdownItem[]
  total_estimated_cost_usd: number
}

export const usageBreakdownApi = {
  /** GET /me/usage/breakdown 返回 PaginatedData；前端按 item.estimated_usd 汇总成本。 */
  async get(accessToken: string): Promise<UsageBreakdown> {
    const page = await apiRequestList<UsageBreakdownItem>('/me/usage/breakdown', {
      token: accessToken,
    })
    const items = page.data
    const total_estimated_cost_usd = items.reduce((sum, it) => sum + it.estimated_usd, 0)
    return { items, total_estimated_cost_usd }
  },
}
