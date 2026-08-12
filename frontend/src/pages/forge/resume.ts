import type { GameDetail, RunDetail, RunListItem } from '@/api/types'
import type { HitlWaitPayload } from '@/api/ws-types'
import { draftArtifactUrl } from '@/lib/hosting'

/** 选最近一条未结束的 run（running 优先于 paused） */
export function pickActiveRun(runs: RunListItem[]): RunListItem | null {
  const active = runs.filter((r) => r.status === 'running' || r.status === 'paused')
  if (active.length === 0) return null
  const running = active.find((r) => r.status === 'running')
  return running ?? active[0] ?? null
}

type HitlWaitDetail = {
  node: string
  design_doc?: HitlWaitPayload['design_doc']
  action_url?: string | null
}

/** 从 API hitl_wait 或 current_hitl 恢复 HITL 卡片 */
export function buildResumeHitl(run: RunDetail, gameTitle: string): HitlWaitPayload | null {
  const extended = run as RunDetail & { hitl_wait?: HitlWaitDetail | null }
  if (
    extended.hitl_wait &&
    (run.status === 'paused' || run.status === 'running')
  ) {
    const hw = extended.hitl_wait
    return {
      node: hw.node,
      design_doc:
        hw.design_doc ??
        ({
          title: `${gameTitle} · 待确认策划`,
          gameplay: '（重连恢复）请确认或修改策划后继续生成。',
          controls: '',
          levels: [],
        } as HitlWaitPayload['design_doc']),
      action_url:
        hw.action_url ??
        `/api/v1/games/${run.game_id}/runs/${run.run_id}/hitl/resolve`,
    }
  }
  // current_hitl 兜底仅对仍可交互的 paused/running 态生效。新版流程下
  // qa_failed/sandbox_failed 是 FAILED 终态（checkpoint 仍写、get_run 仍返回
  // current_hitl，但 resolve 会 409），failed run 不能再浮出 HITL 卡，否则会显示
  // 一张点批准必 409 的死卡，掩盖本应出现的失败恢复条。
  if (run.status !== 'paused' && run.status !== 'running') return null
  if (!run.current_hitl) return null
  return {
    node: run.current_hitl.node,
    design_doc: {
      title: `${gameTitle} · 待确认策划`,
      gameplay: '（重连恢复）请确认或修改策划后继续生成。',
      controls: '',
      levels: [],
    },
    action_url: `/api/v1/games/${run.game_id}/runs/${run.run_id}/hitl/resolve`,
  }
}

export function previewFromGameDetail(game: Pick<GameDetail, 'game_id' | 'current_version'>): string | null {
  if (game.current_version < 1) return null
  return draftArtifactUrl(game.game_id, game.current_version)
}

export function syncUiFromRun(
  run: RunDetail,
  gameTitle: string,
): {
  hitl: HitlWaitPayload | null
  phase: RunDetail['phase'] | 'paused'
  busy: boolean
  runStatus: RunDetail['status']
} {
  const hitl = buildResumeHitl(run, gameTitle)
  const runStatus = run.status
  if (hitl) {
    return { hitl, phase: 'paused', busy: false, runStatus }
  }
  return {
    hitl: null,
    phase: run.phase,
    busy: run.status === 'running',
    runStatus,
  }
}
