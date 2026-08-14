import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type SidebarState = {
  collapsed: boolean
  toggle: () => void
}

// 侧边栏折叠状态：保存在本浏览器，刷新后保持。仅桌面端使用。
export const useSidebarStore = create<SidebarState>()(
  persist(
    (set) => ({
      collapsed: false,
      toggle: () => set((s) => ({ collapsed: !s.collapsed })),
    }),
    { name: 'gf-sidebar' },
  ),
)
