import { ErrorCode } from './enums'
import { ApiError, isApiError } from './errors'

/** 将契约错误码映射为可行动引导文案 */
export function formatApiError(err: unknown, fallback = '请求失败'): string {
  if (isApiError(err)) {
    const guided = guideForCode(err.code, err.message)
    if (guided) return guided
    return err.message || fallback
  }
  if (err instanceof TypeError) {
    const lower = err.message.toLowerCase()
    if (
      lower.includes('failed to fetch') ||
      lower.includes('networkerror') ||
      lower.includes('load failed') ||
      err.message.includes('无法连接后端')
    ) {
      return (
        err.message.includes('无法连接后端')
          ? err.message
          : '无法连接后端：请确认 API 已在 http://127.0.0.1:8000 启动；' +
            '若刚拉代码，请在 backend/ 执行 uv run alembic upgrade head'
      )
    }
    return err.message || '无法连接后端，请确认 API 已启动'
  }
  if (err instanceof Error && err.message) return err.message
  return fallback
}

export function guideForCode(code: string, message?: string): string | null {
  switch (code) {
    case ErrorCode.EMAIL_NOT_VERIFIED:
      return '邮箱未验证：请先到设置页完成验证后再发起生成。'
    case ErrorCode.QUOTA_EXCEEDED:
      return '今日 token 配额已用尽：请明天再试，或联系管理员提高配额。'
    case ErrorCode.RATE_LIMITED:
      return '请求过于频繁，请稍后再试。'
    case ErrorCode.LLM_CONFIG_INVALID:
      if (message) return message
      return 'LLM 配置无效或连通失败：请检查 apikey、model 与 base_url。'
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
