import { createContext, useContext } from 'react'

/**
 * 后台 toast 通道：AdminShell 持有 toast 状态并在此 context 下发 setToast，
 * 各 section 通过 useAdminToast() 推送反馈消息，避免 7 个 section 各自维护 toast。
 */
type ToastFn = (message: string) => void

export const AdminToastContext = createContext<ToastFn>(() => {})

export function useAdminToast(): ToastFn {
  return useContext(AdminToastContext)
}
