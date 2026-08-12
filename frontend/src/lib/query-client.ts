import { QueryClient } from '@tanstack/react-query'

// 全局 React Query 单例。放在独立模块，避免 auth-store ↔ App.tsx 之间的循环依赖。
// App.tsx 的 QueryClientProvider 与 auth-store 的 logout（登出/换号时清缓存）共用同一个实例。
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})
