import { http } from 'msw'
import { ErrorCode, GameStatus, RunPhase, RunStatus } from '@/api/enums'
import { env } from '@/lib/env'
import { delay, mockDb, uid } from '../db'
import { fail, listOk, ok, readJson, requireUser } from '../http'

const base = env.apiBaseUrl

function summaryOf(g: (typeof mockDb.games)[number]) {
  return {
    game_id: g.game_id,
    title: g.title,
    status: g.status,
    current_version: g.current_version,
    slug: g.slug,
    updated_at: g.updated_at,
  }
}

export const gamesHandlers = [
  http.get(`${base}/games`, async ({ request }) => {
    await delay()
    const { user, error } = requireUser(request)
    if (error) return error
    const url = new URL(request.url)
    const status = url.searchParams.get('status')
    let rows = mockDb.games.filter((g) => g.owner_id === user.user_id)
    if (status) rows = rows.filter((g) => g.status === status)
    return listOk(rows.map(summaryOf))
  }),

  http.post(`${base}/games`, async ({ request }) => {
    await delay()
    const { user, error } = requireUser(request)
    if (error) return error
    const body = await readJson<{ title: string; requirement: string }>(request)
    const created_at = new Date().toISOString()
    const item = {
      game_id: uid('g'),
      owner_id: user.user_id,
      title: body.title || '未命名游戏',
      status: GameStatus.draft,
      current_version: 0,
      slug: null,
      updated_at: created_at,
      created_at,
      cover: 'default',
    }
    mockDb.games.unshift(item)
    return ok({
      game_id: item.game_id,
      owner_id: user.user_id,
      status: GameStatus.draft,
      current_version: 0,
      created_at,
    })
  }),

  http.get(`${base}/games/:gameId`, async ({ request, params }) => {
    await delay()
    const { user, error } = requireUser(request)
    if (error) return error
    const g = mockDb.games.find((x) => x.game_id === params.gameId)
    if (!g || g.owner_id !== user.user_id) {
      return fail(404, ErrorCode.GAME_NOT_FOUND, '游戏不存在')
    }
    return ok({
      game_id: g.game_id,
      owner_id: g.owner_id,
      title: g.title,
      status: g.status,
      current_version: g.current_version,
      slug: g.slug,
      versions:
        g.current_version > 0
          ? [
              {
                version: g.current_version,
                artifact_path: `/mock-artifacts/${g.game_id}/v${g.current_version}/`,
                created_at: g.updated_at,
              },
            ]
          : [],
      created_at: g.created_at,
      updated_at: g.updated_at,
    })
  }),

  http.delete(`${base}/games/:gameId`, async ({ request, params }) => {
    await delay()
    const { user, error } = requireUser(request)
    if (error) return error
    const idx = mockDb.games.findIndex(
      (x) => x.game_id === params.gameId && x.owner_id === user.user_id,
    )
    if (idx < 0) return fail(404, ErrorCode.GAME_NOT_FOUND, '游戏不存在')
    const g = mockDb.games[idx]
    if (
      g.status === GameStatus.published ||
      g.status === GameStatus.submitted ||
      g.status === GameStatus.reviewing
    ) {
      return fail(409, ErrorCode.INVALID_STATE, '已发布或审批中的游戏不能直接删除')
    }
    mockDb.games.splice(idx, 1)
    return ok({ game_id: g.game_id, deleted: true })
  }),

  http.post(`${base}/games/:gameId/runs`, async ({ request, params }) => {
    await delay()
    const { user, error } = requireUser(request)
    if (error) return error
    if (!user.email_verified) {
      return fail(403, ErrorCode.EMAIL_NOT_VERIFIED, '未验证邮箱，功能受限')
    }
    const g = mockDb.games.find((x) => x.game_id === params.gameId && x.owner_id === user.user_id)
    if (!g) return fail(404, ErrorCode.GAME_NOT_FOUND, '游戏不存在')
    await readJson<{ requirement: string; llm_config_id: string | null }>(request)
    const run_id = uid('run')
    const started_at = new Date().toISOString()
    mockDb.runs.set(run_id, {
      run_id,
      game_id: g.game_id,
      owner_id: user.user_id,
      status: RunStatus.running,
      phase: RunPhase.plan,
      started_at,
      ended_at: null,
      current_hitl: null,
    })
    return ok({
      run_id,
      game_id: g.game_id,
      status: RunStatus.running,
      phase: RunPhase.plan,
      ws_url: `/ws/runs/${run_id}`,
    })
  }),

  http.get(`${base}/games/:gameId/runs`, async ({ request, params }) => {
    await delay()
    const { user, error } = requireUser(request)
    if (error) return error
    const g = mockDb.games.find((x) => x.game_id === params.gameId && x.owner_id === user.user_id)
    if (!g) return fail(404, ErrorCode.GAME_NOT_FOUND, '游戏不存在')
    const data = [...mockDb.runs.values()]
      .filter((r) => r.game_id === g.game_id)
      .map((r) => ({
        run_id: r.run_id,
        status: r.status,
        phase: r.phase,
        started_at: r.started_at,
        ended_at: r.ended_at,
      }))
    return listOk(data)
  }),

  http.get(`${base}/games/:gameId/versions`, async ({ request, params }) => {
    await delay()
    const { user, error } = requireUser(request)
    if (error) return error
    const g = mockDb.games.find((x) => x.game_id === params.gameId && x.owner_id === user.user_id)
    if (!g) return fail(404, ErrorCode.GAME_NOT_FOUND, '游戏不存在')
    const data =
      g.current_version > 0
        ? [
            {
              version: g.current_version,
              artifact_path: `/mock-artifacts/${g.game_id}/v${g.current_version}/`,
              created_at: g.updated_at,
            },
          ]
        : []
    return listOk(data)
  }),

  http.get(`${base}/runs/:runId`, async ({ request, params }) => {
    await delay()
    const { user, error } = requireUser(request)
    if (error) return error
    const r = mockDb.runs.get(String(params.runId))
    if (!r || r.owner_id !== user.user_id) {
      return fail(404, ErrorCode.GAME_NOT_FOUND, 'run 不存在')
    }
    return ok({
      run_id: r.run_id,
      game_id: r.game_id,
      status: r.status,
      phase: r.phase,
      ws_url: `/ws/runs/${r.run_id}`,
      current_hitl: r.current_hitl,
    })
  }),

  http.post(`${base}/games/:gameId/runs/:runId/hitl/resolve`, async ({ request, params }) => {
    await delay()
    const { user, error } = requireUser(request)
    if (error) return error
    const r = mockDb.runs.get(String(params.runId))
    if (!r || r.owner_id !== user.user_id || r.game_id !== params.gameId) {
      return fail(404, ErrorCode.GAME_NOT_FOUND, 'run 不存在')
    }
    const body = await readJson<{ node: string; decision: string; modify_text?: string }>(request)
    if (body.decision !== 'approve' && body.decision !== 'modify') {
      return fail(400, ErrorCode.VALIDATION_ERROR, 'decision 无效')
    }
    r.status = RunStatus.running
    r.phase = RunPhase.art
    r.current_hitl = null
    return ok({ run_id: r.run_id, status: RunStatus.running, phase: RunPhase.art })
  }),

  http.post(`${base}/games/:gameId/publish/submit`, async ({ request, params }) => {
    await delay()
    const { user, error } = requireUser(request)
    if (error) return error
    const g = mockDb.games.find((x) => x.game_id === params.gameId && x.owner_id === user.user_id)
    if (!g) return fail(404, ErrorCode.GAME_NOT_FOUND, '游戏不存在')
    const allowed: GameStatus[] = [GameStatus.draft, GameStatus.rejected, GameStatus.taken_down]
    if (!allowed.includes(g.status)) {
      return fail(409, ErrorCode.INVALID_STATE, '当前状态不可提交发布')
    }
    if (g.current_version < 1) {
      return fail(409, ErrorCode.INVALID_STATE, '需要至少一次成功构建版本')
    }
    const body = await readJson<{ version: number; note: string }>(request)
    g.status = GameStatus.submitted
    g.updated_at = new Date().toISOString()
    const publish_request_id = uid('pub')
    mockDb.publishQueue.push({
      publish_request_id,
      game_id: g.game_id,
      game_title: g.title,
      version: body.version,
      status: 'submitted',
      created_at: g.updated_at,
      owner_id: user.user_id,
    })
    return ok({
      publish_request_id,
      status: 'submitted',
      game_id: g.game_id,
      version: body.version,
    })
  }),
]
