import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ForgeComposer } from './ForgeComposer'

afterEach(cleanup)

describe('ForgeComposer 生成中', () => {
  it('busy 时展示等待占位、发送键灰底转圈且不可点', () => {
    render(
      <ForgeComposer
        value=""
        onChange={() => undefined}
        onSend={vi.fn()}
        disabled
        sendDisabled
        busy
        placeholder="描述一个你想玩的游戏……"
      />,
    )
    expect(screen.getByRole('textbox', { name: '生成中，请稍候…' })).toBeDisabled()
    const send = screen.getByRole('button', { name: '生成中，请稍候…' })
    expect(send).toBeDisabled()
    expect(send.className).not.toMatch(/linear-gradient/)
    expect(send.className).toMatch(/bg-slate-500/)
    expect(send.querySelector('.animate-spin')).toBeTruthy()
  })

  it('仅输入为空时发送键灰底，仍显示箭头', () => {
    render(
      <ForgeComposer
        value=""
        onChange={() => undefined}
        onSend={vi.fn()}
        placeholder="描述一个你想玩的游戏……"
      />,
    )
    const send = screen.getByRole('button', { name: '发送需求' })
    expect(send).toBeDisabled()
    expect(send.className).not.toMatch(/linear-gradient/)
    expect(send.className).toMatch(/bg-slate-500/)
    expect(send.querySelector('.animate-spin')).toBeNull()
  })
})
