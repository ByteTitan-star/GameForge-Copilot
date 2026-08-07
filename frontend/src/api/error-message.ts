import { ErrorCode } from './enums'
import { ApiError, isApiError } from './errors'

/** 将契约错误码映射为可行动引导文案 */
export function formatApiError(err: unknown, fallback = '请求失败'): string {
  if (!isApiError(err)) return fallback
  return guideForCode(err.code) ?? (err.message || fallback)
}

export function guideForCode(code: string): string | null {
  switch (code) {
    case ErrorCode.EMAIL_NOT_VERIFIED:
      return '邮箱未验证：请先到设置页完成验证后再发起生成。'
    case ErrorCode.QUOTA_EXCEEDED:
      return '今日 token 配额已用尽：请明天再试，或联系管理员提高配额。'
    case ErrorCode.RATE_LIMITED:
      return '请求过于频繁，请稍后再试。'
    case ErrorCode.LLM_CONFIG_INVALID:
      return 'LLM 配置无效或连通失败：请到设置页检查 apikey / base_url。'
    case ErrorCode.UNAUTHORIZED:
      return '登录已失效，请重新登录。'
    default:
      return null
  }
}

export function isQuotaOrVerifyError(err: unknown): err is ApiError {
  return (
    isApiError(err) &&
    (err.code === ErrorCode.QUOTA_EXCEEDED || err.code === ErrorCode.EMAIL_NOT_VERIFIED)
  )
}
