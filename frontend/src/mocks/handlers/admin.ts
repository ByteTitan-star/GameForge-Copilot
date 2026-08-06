import { http } from 'msw'
import { ErrorCode, GameStatus, Role } from '@/api/enums'
import { env } from '@/lib/env'
import { delay, mockDb } from '../db'
import { fail, listOk, ok, readJson, requireUser } from '../http'

const base = env.apiBaseUrl

function requireAdmin(req: Request) {
  const r = requireUser(req)
  if (r.error) return r
  if (r.user.role !== Role.admin) {
    return { user: null as null, error: fail(403, ErrorCode.FORBIDDEN, '需要管理员权限') }
  }
  return r
}

export const adminHandlers = [
  http.get(`${base}/publish/queue`, async ({ request }) => {
    await delay()
    const { error } = requireAdmin(request)
    if (error) return error
    const url = new URL(request.url)
    const status = url.searchParams.get('status')
    let rows = mockDb.publishQueue
    if (status) rows = rows.filter((p) => p.status === status)
    return listOk(
      rows.map(({ publish_request_id, game_id, game_title, version, status: st, created_at }) => ({
        publish_request_id,
        game_id,
        game_title,
        version,
        status: st,
        created_at,
      })),
    )
  }),

  http.post(`${base}/publish/:id/approve`, async ({ request, params }) => {
    await delay()
    const { error } = requireAdmin(request)
    if (error) return error
    const item = mockDb.publishQueue.find((p) => p.publish_request_id === params.id)
    if (!item) return fail(404, ErrorCode.GAME_NOT_FOUND, '审批单不存在')
    item.status = 'approved'
    const g = mockDb.games.find((x) => x.game_id === item.game_id)
    if (g) {
      g.status = GameStatus.published
      g.slug = g.slug ?? `game-${g.game_id.slice(-6)}`
      g.updated_at = new Date().toISOString()
    }
    return ok({
      publish_request_id: item.publish_request_id,
      status: 'approved',
      game: {
        game_id: item.game_id,
        slug: g?.slug ?? null,
        status: GameStatus.published,
      },
    })
  }),

  http.post(`${base}/publish/:id/reject`, async ({ request, params }) => {
    await delay()
    const { error } = requireAdmin(request)
    if (error) return error
    const body = await readJson<{ reason: string }>(request)
    const item = mockDb.publishQueue.find((p) => p.publish_request_id === params.id)
    if (!item) return fail(404, ErrorCode.GAME_NOT_FOUND, '审批单不存在')
    item.status = 'rejected'
    const g = mockDb.games.find((x) => x.game_id === item.game_id)
    if (g) {
      g.status = GameStatus.rejected
      g.updated_at = new Date().toISOString()
    }
    return ok({
      publish_request_id: item.publish_request_id,
      status: 'rejected',
      game: { game_id: item.game_id, status: GameStatus.rejected },
      reason: body.reason,
    })
  }),

  http.post(`${base}/games/:gameId/take-down`, async ({ request, params }) => {
    await delay()
    const { error } = requireAdmin(request)
    if (error) return error
    const body = await readJson<{ reason: string }>(request)
    const g = mockDb.games.find((x) => x.game_id === params.gameId)
    if (!g) return fail(404, ErrorCode.GAME_NOT_FOUND, '游戏不存在')
    if (g.status !== GameStatus.published) {
      return fail(409, ErrorCode.INVALID_STATE, '非 published 不能下架')
    }
    g.status = GameStatus.taken_down
    g.updated_at = new Date().toISOString()
    return ok({ game_id: g.game_id, status: GameStatus.taken_down, reason: body.reason })
  }),

  http.get(`${base}/admin/usage`, async ({ request }) => {
    await delay()
    const { error } = requireAdmin(request)
    if (error) return error
    return ok({
      system: {
        today: { input_tokens: 50000, output_tokens: 12000, calls: 80 },
        month: { input_tokens: 900000, output_tokens: 200000, calls: 1400 },
        total: { input_tokens: 5000000, output_tokens: 1100000, calls: 9000 },
      },
      top_users: [
        {
          user_id: 'u-demo',
          email: 'demo@gameforge.dev',
          month_input_tokens: 150000,
          month_output_tokens: 36000,
          calls: 186,
        },
      ],
    })
  }),
]
