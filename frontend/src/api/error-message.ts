import type { MessageKey } from '@/i18n/messages'
import { ErrorCode } from './enums'
import { ApiError, isApiError } from './errors'

export type ErrorTranslator = (key: MessageKey) => string

function isInvalidCredentialsMessage(message?: string): boolean {
  if (!message) return false
  const lower = message.toLowerCase()
  return (
    message.includes('邮箱或密码') ||
    message.includes('密码不正确') ||
    lower.includes('password') ||
    lower.includes('credentials')
  )
}

/** 将契约错误码映射为可行动引导文案（需传入 t 才会本地化；无 t 时不注入硬编码文案） */
export function guideForCode(
  code: string,
  message: string | undefined,
  t?: ErrorTranslator,
): string | null {
  if (!t) {
    if (code === ErrorCode.LLM_CONFIG_INVALID && message) return message
    return null
  }
  switch (code) {
    case ErrorCode.EMAIL_NOT_VERIFIED:
      return t('errEmailNotVerified')
    case ErrorCode.QUOTA_EXCEEDED:
      return t('errQuotaExceeded')
    case ErrorCode.RATE_LIMITED:
      return t('errRateLimited')
    case ErrorCode.LLM_CONFIG_INVALID:
      return message || t('errLlmConfigInvalid')
    case ErrorCode.UNAUTHORIZED:
      return isInvalidCredentialsMessage(message)
        ? t('errInvalidCredentials')
        : t('errSessionExpired')
    default:
      return null
  }
}

export function formatApiError(
  err: unknown,
  fallback = '请求失败',
  t?: ErrorTranslator,
): string {
  if (isApiError(err)) {
    const guided = guideForCode(err.code, err.message, t)
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
      if (t) return t('errNetworkFailed')
      return (
        err.message.includes('无法连接后端')
          ? err.message
          : '无法连接后端：请确认 API 已在 http://127.0.0.1:8000 启动；' +
            '若刚拉代码，请在 backend/ 执行 uv run alembic upgrade head'
      )
    }
    return err.message || (t ? t('errNetworkFailed') : '无法连接后端，请确认 API 已启动')
  }
  if (err instanceof Error && err.message) return err.message
  return fallback
}

export function isQuotaOrVerifyError(err: unknown): err is ApiError {
  return (
    isApiError(err) &&
    (err.code === ErrorCode.QUOTA_EXCEEDED || err.code === ErrorCode.EMAIL_NOT_VERIFIED)
  )
}
