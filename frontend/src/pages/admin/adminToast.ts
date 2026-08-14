import { createContext, useContext } from 'react'

/**
 * 后台 toast 通道：AdminShell 持有 toast 状态并在此 context 下发推送函数，
 * 各 section 通过 useAdminToast() 反馈操作结果，避免 7 个 section 各自维护 toast。
 *
 * variant：info（默认，role=status，礼貌播报成功/提示）与 error（role=alert，立即播报失败）。
 * 成功路径不必传 variant；失败路径传 'error'，确保屏幕阅读器能感知错误。
 */
export type ToastVariant = 'info' | 'error'

export type AdminToast = (message: string, variant?: ToastVariant) => void

export const AdminToastContext = createContext<AdminToast>(() => {})

export function useAdminToast(): AdminToast {
  return useContext(AdminToastContext)
}
