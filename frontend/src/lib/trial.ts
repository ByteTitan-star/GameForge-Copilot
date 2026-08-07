/** 试用预览账号：只读看 UI / 预置样例，不落盘、不配 Key、不跑生成。 */

export const TRIAL_EMAIL = 'demo@gameforge.dev'
export const TRIAL_PASSWORD = 'password123'

export function isTrialEmail(email: string | null | undefined): boolean {
  return (email ?? '').trim().toLowerCase() === TRIAL_EMAIL
}

export function isTrialUser(user: { email?: string | null } | null | undefined): boolean {
  return isTrialEmail(user?.email)
}
