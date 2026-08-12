import { afterEach, describe, expect, it, vi } from 'vitest'
import { downloadFile } from './download-file'

describe('downloadFile', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('clicks a temporary link with the requested filename and releases the blob URL', () => {
    const createObjectURL = vi.fn().mockReturnValue('blob:game-version')
    const revokeObjectURL = vi.fn()
    const append = vi.spyOn(document.body, 'append')
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    vi.stubGlobal('URL', { createObjectURL, revokeObjectURL })

    downloadFile(new Blob(['<!doctype html>']), 'my-game-v2.html')

    expect(append).toHaveBeenCalledWith(
      expect.objectContaining({ download: 'my-game-v2.html', href: 'blob:game-version' }),
    )
    expect(click).toHaveBeenCalledOnce()
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:game-version')
  })
})
