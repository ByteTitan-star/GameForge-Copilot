import { describe, expect, it } from 'vitest'
import { btnDanger, btnDangerSolid, btnNeutral, btnPrimary } from './buttonStyles'

/**
 * 后台按钮样式契约冒烟测试。
 *
 * 保护 P1-3 的设计意图：破坏性按钮（btnDanger）行内默认弱化、父级 tr.group
 * 悬停/聚焦时强化；主操作（btnPrimary）与中性按钮（btnNeutral）保持常显，
 * 不引入 group-hover 弱化逻辑。任一退化都会被这里的字符串断言拦下。
 */
describe('admin buttonStyles 契约', () => {
  it('btnDanger 默认弱化 + 行 hover/focus-within 强化（破坏性按钮退到次层级）', () => {
    expect(btnDanger).toContain('opacity-60')
    expect(btnDanger).toContain('group-hover:opacity-100')
    expect(btnDanger).toContain('group-focus-within:opacity-100')
  })

  it('btnPrimary / btnNeutral 保持常显，不挂 group-hover 弱化（主操作始终可发现）', () => {
    expect(btnPrimary).not.toContain('group-hover:opacity-100')
    expect(btnNeutral).not.toContain('group-hover:opacity-100')
  })

  it('四档按钮统一基础尺寸（h-8 / rounded-lg / focus-visible ring）', () => {
    for (const cls of [btnPrimary, btnNeutral, btnDanger]) {
      expect(cls).toContain('h-8')
      expect(cls).toContain('rounded-lg')
      expect(cls).toContain('focus-visible:ring-2')
    }
  })

  it('btnDanger 次级浅红降噪音；btnDangerSolid 实心红保留升级感', () => {
    expect(btnDanger).toMatch(/bg-red-500\/10/)
    expect(btnDanger).toMatch(/text-rose-700/)
    // 实心红用于 ConfirmModal 最终确认，更醒目
    expect(btnDangerSolid).toContain('bg-red-500')
    expect(btnDangerSolid).not.toMatch(/bg-red-500\/10/)
  })
})
