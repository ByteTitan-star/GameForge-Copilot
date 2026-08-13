import { apiRequest } from './client'

export type FeedbackRequest = {
  run_id: string
  message?: string
  error_summary?: string
}

export type FeedbackResponse = {
  submitted: boolean
}

/** forge 失败时「联系管理员」：代发一封反馈邮件给管理员（用户不接触邮箱）。 */
export function submitFeedback(body: FeedbackRequest, accessToken: string) {
  return apiRequest<FeedbackResponse>('/me/feedback', {
    method: 'POST',
    token: accessToken,
    body,
  })
}
