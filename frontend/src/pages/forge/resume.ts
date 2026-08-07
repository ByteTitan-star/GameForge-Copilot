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

/** getRun 仅返回 current_hitl.node；补齐 HitlCard 所需结构 */
export function buildResumeHitl(run: RunDetail, gameTitle: string): HitlWaitPayload | null {
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
