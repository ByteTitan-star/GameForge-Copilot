import { renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { useT } from './use-t'

describe('useT', () => {
  it('同一 locale 下返回稳定的翻译函数引用', () => {
    const { result, rerender } = renderHook(() => useT())
    const first = result.current
    rerender()
    expect(result.current).toBe(first)
  })
})
