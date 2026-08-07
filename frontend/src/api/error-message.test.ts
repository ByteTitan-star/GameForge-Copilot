import { describe, expect, it } from 'vitest'
import { ErrorCode } from './enums'
import { ApiError } from './errors'
import { formatApiError, guideForCode } from './error-message'

describe('formatApiError', () => {
  it('配额与未验证给出引导文案', () => {
    expect(guideForCode(ErrorCode.QUOTA_EXCEEDED)).toMatch(/配额/)
    expect(guideForCode(ErrorCode.EMAIL_NOT_VERIFIED)).toMatch(/验证/)
    expect(
      formatApiError(new ApiError(429, { code: ErrorCode.QUOTA_EXCEEDED, message: 'x' })),
    ).toMatch(/配额/)
  })

  it('未知错误回退 message', () => {
    expect(
      formatApiError(new ApiError(500, { code: 'OTHER', message: '沙箱炸了' })),
    ).toBe('沙箱炸了')
  })

  it('网络/CORS 失败给出连接提示', () => {
    expect(formatApiError(new TypeError('Failed to fetch'), '注册失败')).toMatch(/无法连接后端/)
  })
})
