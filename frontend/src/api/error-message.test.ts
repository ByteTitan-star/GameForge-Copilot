import { describe, expect, it } from 'vitest'
import { ErrorCode } from './enums'
import { ApiError } from './errors'
import { formatApiError, guideForCode } from './error-message'
import { messages } from '@/i18n/messages'

const tZh = (key: keyof (typeof messages)['zh']) => messages.zh[key]
const tEn = (key: keyof (typeof messages)['en']) => messages.en[key]

describe('formatApiError', () => {
  it('配额与未验证给出本地化引导文案', () => {
    expect(guideForCode(ErrorCode.QUOTA_EXCEEDED, undefined, tZh)).toMatch(/配额/)
    expect(guideForCode(ErrorCode.EMAIL_NOT_VERIFIED, undefined, tZh)).toMatch(/验证/)
    expect(
      formatApiError(new ApiError(429, { code: ErrorCode.QUOTA_EXCEEDED, message: 'x' }), 'fallback', tZh),
    ).toMatch(/配额/)
  })

  it('未知错误回退 message', () => {
    expect(
      formatApiError(new ApiError(500, { code: 'OTHER', message: '沙箱炸了' })),
    ).toBe('沙箱炸了')
  })

  it('LLM 配置失败展示后端具体原因', () => {
    expect(
      formatApiError(
        new ApiError(400, {
          code: ErrorCode.LLM_CONFIG_INVALID,
          message: '连通测试失败: LLM 调用失败 HTTP 404: Not Found',
        }),
        'fallback',
        tZh,
      ),
    ).toMatch(/404/)
  })

  it('网络/CORS 失败给出本地化连接提示', () => {
    expect(formatApiError(new TypeError('Failed to fetch'), '注册失败', tZh)).toMatch(/无法连接后端/)
    expect(formatApiError(new TypeError('Failed to fetch'), 'Sign-up failed', tEn)).toMatch(
      /Cannot reach the backend/,
    )
  })

  it('登录凭据错误在英文界面显示英文提示', () => {
    const err = new ApiError(401, { code: ErrorCode.UNAUTHORIZED, message: '邮箱或密码错误' })
    expect(formatApiError(err, tEn('errLoginFailed'), tEn)).toBe('Incorrect email or password.')
  })

  it('登录凭据错误在中文界面显示中文提示', () => {
    const err = new ApiError(401, { code: ErrorCode.UNAUTHORIZED, message: '邮箱或密码错误' })
    expect(formatApiError(err, tZh('errLoginFailed'), tZh)).toBe('邮箱或密码不正确')
  })

  it('会话失效与凭据错误区分', () => {
    const sessionErr = new ApiError(401, { code: ErrorCode.UNAUTHORIZED, message: '未登录或 token 失效' })
    expect(formatApiError(sessionErr, 'fallback', tEn)).toBe('Your session has expired. Please sign in again.')
    expect(formatApiError(sessionErr, 'fallback', tZh)).toBe('登录已失效，请重新登录')
  })

  it('无 translator 时不注入硬编码 UNAUTHORIZED 文案', () => {
    const err = new ApiError(401, { code: ErrorCode.UNAUTHORIZED, message: '邮箱或密码错误' })
    expect(formatApiError(err, 'Sign-in failed')).toBe('邮箱或密码错误')
  })
})
