import type { ApiErrorBody } from './types'

export class ApiError extends Error {
  readonly code: string
  readonly status: number
  readonly detail?: Record<string, unknown>

  constructor(status: number, body: ApiErrorBody['error']) {
    super(body.message)
    this.name = 'ApiError'
    this.status = status
    this.code = body.code
    this.detail = body.detail
  }
}

export function isApiError(err: unknown): err is ApiError {
  return err instanceof ApiError
}
