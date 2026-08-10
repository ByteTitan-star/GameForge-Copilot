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
    expect(hitl?.design_doc).toBeDefined()
    const docTitle =
      typeof hitl?.design_doc === 'object' && hitl.design_doc && 'title' in hitl.design_doc
        ? String(hitl.design_doc.title)
        : ''
    expect(docTitle || hitl?.node).toContain('霓虹蛇')
    expect(hitl?.action_url).toContain('/hitl/resolve')
  })

  it('failed 终态即使残留 current_hitl 也不浮出 HITL 卡', () => {
    // 新版流程：qa_failed/sandbox_failed 重试耗尽即 FAILED，checkpoint 仍写、
    // get_run 仍返回 current_hitl，但不再是人工确认点。重连到这种 run 必须返回
    // null，让上层走失败恢复条而非一张点批准必 409 的死卡。
    const failed: RunDetail = {
      run_id: 'r-fail',
      game_id: 'g1',
      status: 'failed',
      phase: 'qa',
      ws_url: '/ws/runs/r-fail',
      current_hitl: { node: 'qa_failed' },
    }
    expect(buildResumeHitl(failed, '霓虹蛇')).toBeNull()
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
