import { describe, expect, it } from 'vitest'
import { buildResumeHitl, pickActiveRun, previewFromGameDetail } from './resume'
import type { GameDetail, RunDetail, RunListItem } from '@/api/types'

describe('forge resume helpers', () => {
  it('优先选 running，其次 paused', () => {
    const rows: RunListItem[] = [
      {
        run_id: 'r-done',
        status: 'done',
        phase: 'done',
        started_at: '2026-01-01T00:00:00Z',
        ended_at: '2026-01-01T00:01:00Z',
      },
      {
        run_id: 'r-run',
        status: 'running',
        phase: 'code',
        started_at: '2026-01-01T00:02:00Z',
        ended_at: null,
      },
      {
        run_id: 'r-pause',
        status: 'paused',
        phase: 'plan',
        started_at: '2026-01-01T00:03:00Z',
        ended_at: null,
      },
    ]
    expect(pickActiveRun(rows)?.run_id).toBe('r-run')
    expect(pickActiveRun(rows.filter((r) => r.run_id !== 'r-run'))?.run_id).toBe('r-pause')
    expect(pickActiveRun(rows.filter((r) => r.status === 'done'))).toBeNull()
  })

  it('HITL 态生成可展示的占位 design_doc', () => {
    const run: RunDetail = {
      run_id: 'r1',
      game_id: 'g1',
      status: 'running',
      phase: 'plan',
      ws_url: '/ws/runs/r1',
      current_hitl: { node: 'plan_confirm' },
    }
    const hitl = buildResumeHitl(run, '霓虹蛇')
    expect(hitl?.node).toBe('plan_confirm')
    expect(hitl?.design_doc.title).toContain('霓虹蛇')
    expect(hitl?.action_url).toContain('/hitl/resolve')
  })

  it('从 game detail 推导草稿预览 URL', () => {
    const g = {
      game_id: 'g-1',
      current_version: 2,
      slug: null,
    } as GameDetail
    expect(previewFromGameDetail(g)).toMatch(/g-1/)
    expect(previewFromGameDetail({ ...g, current_version: 0 })).toBeNull()
  })
})
