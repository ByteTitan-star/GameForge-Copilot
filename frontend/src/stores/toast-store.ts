import { create } from "zustand";

export type ToastType = "success" | "error" | "info" | "warning";

export interface Toast {
  id: string;
  type: ToastType;
  message: string;
  duration: number; // ms，0 = 不自动消失
}

interface ToastInput {
  type: ToastType;
  message: string;
  duration?: number;
  id?: string;
}

interface ToastState {
  toasts: Toast[];
  push: (t: ToastInput) => string;
  dismiss: (id: string) => void;
  clear: () => void;
}

// 各类型默认展示时长（ms）：错误给长一些便于看清
const DEFAULT_DURATION: Record<ToastType, number> = {
  success: 2500,
  error: 5000,
  info: 3000,
  warning: 3000,
};

const MAX_VISIBLE = 4;

let _seq = 0;
const genId = (): string => {
  _seq += 1;
  return `t-${Date.now().toString(36)}-${_seq.toString(36)}`;
};

export const useToastStore = create<ToastState>((set, get) => ({
  toasts: [],
  push: ({ type, message, duration, id }) => {
    const toastId = id ?? genId();
    const realDuration = duration ?? DEFAULT_DURATION[type];
    set((s) => ({
      // 同 message 去重 + 堆叠上限，防 WS 多次 fatal 触发刷屏
      toasts: [
        ...s.toasts.filter((t) => t.message !== message).slice(-(MAX_VISIBLE - 1)),
        { id: toastId, type, message, duration: realDuration },
      ],
    }));
    if (realDuration > 0) {
      setTimeout(() => get().dismiss(toastId), realDuration);
    }
    return toastId;
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
  clear: () => set({ toasts: [] }),
}));

/**
 * 非 hook 便捷对象：内部用 getState() 绕开 hook 约束，
 * 可在事件回调、API 拦截器等非组件环境直接调用。
 */
export const toast = {
  success: (message: string, duration?: number) =>
    useToastStore.getState().push({ type: "success", message, duration }),
  error: (message: string, duration?: number) =>
    useToastStore.getState().push({ type: "error", message, duration }),
  info: (message: string, duration?: number) =>
    useToastStore.getState().push({ type: "info", message, duration }),
  warning: (message: string, duration?: number) =>
    useToastStore.getState().push({ type: "warning", message, duration }),
};
