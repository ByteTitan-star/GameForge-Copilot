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
      status: 'paused',
      phase: 'plan',
      entry_phase: 'plan',
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

  it('running 态即使带有残留 HITL 也不生成可点击卡片', () => {
    const run = {
      run_id: 'r-stale',
      game_id: 'g1',
      status: 'running',
      phase: 'art',
      entry_phase: 'plan',
      ws_url: '/ws/runs/r-stale',
      current_hitl: { node: 'plan_confirm' },
      hitl_wait: {
        node: 'plan_confirm',
        design_doc: { title: '旧策划', gameplay: 'g', controls: 'c', levels: [] },
        action_url: '/hitl/resolve',
      },
    } as RunDetail
    expect(buildResumeHitl(run, '霓虹蛇')).toBeNull()
  })

  it('刷新后恢复美术 A/B 方案', () => {
    const run = {
      run_id: 'r-art',
      game_id: 'g1',
      status: 'paused',
      phase: 'art',
      entry_phase: 'plan',
      ws_url: '/ws/runs/r-art',
      current_hitl: { node: 'art_confirm' },
      hitl_wait: {
        node: 'art_confirm',
        design_doc: { title: '霓虹蛇', gameplay: 'g', controls: [], levels: [] },
        art_options: {
          options: [
            { id: 'A', name: '霓虹', summary: 'Canvas 粒子', recommended: true },
            { id: 'B', name: '纸雕', summary: 'CSS 纸片', recommended: false },
          ],
        },
      },
    } as RunDetail
    const hitl = buildResumeHitl(run, '霓虹蛇')
    expect(hitl?.node).toBe('art_confirm')
    expect(hitl?.art_options?.options).toHaveLength(2)
  })

  it('failed 终态即使残留 current_hitl 也不浮出 HITL 卡', () => {
    const failed: RunDetail = {
      run_id: 'r-fail',
      game_id: 'g1',
      status: 'failed',
      phase: 'qa',
      entry_phase: 'code',
      ws_url: '/ws/runs/r-fail',
      current_hitl: { node: 'qa_failed' },
    }
    expect(buildResumeHitl(failed, '霓虹蛇')).toBeNull()
  })

  it('paused + qa_failed 可恢复为 HITL', () => {
    const paused: RunDetail = {
      run_id: 'r-qa',
      game_id: 'g1',
      status: 'paused',
      phase: 'qa',
      entry_phase: 'code',
      ws_url: '/ws/runs/r-qa',
      current_hitl: { node: 'qa_failed' },
    }
    const hitl = buildResumeHitl(paused, '霓虹蛇')
    expect(hitl?.node).toBe('qa_failed')
    expect(hitl?.action_url).toContain('/hitl/resolve')
    const gameplay =
      typeof hitl?.design_doc === 'object' && hitl.design_doc && 'gameplay' in hitl.design_doc
        ? String(hitl.design_doc.gameplay)
        : ''
    expect(gameplay).toContain('试玩未通过')
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
