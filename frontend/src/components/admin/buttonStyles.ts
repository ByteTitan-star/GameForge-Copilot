/**
 * 后台操作按钮样式（token 驱动）。admin 作用域内 .gf-btn-primary 已被 CSS 覆盖为实心品牌色，
 * 所以 btnPrimary 仍走 .gf-btn-primary（保留 :active scale）；其余三档语义化：
 * - btnPrimary：主操作（审批通过 / 应用配额 / 保存）
 * - btnDanger：破坏性操作的「次级」入口（列表行内 reject / takedown / delete），浅红降噪音
 * - btnDangerSolid：破坏性操作的「最终确认」（ConfirmModal），实心红保留升级感
 * - btnNeutral：中性操作（降权 / 启用 / 清除覆盖）
 * 统一 h-8 / rounded-lg / focus-visible ring，跨主题一致。
 *
 * btnDanger 行内默认弱化（opacity-60），父级 tr.group 悬停/聚焦时强化——降低视觉噪音，
 * 同时把破坏性操作退到「需要交互才显眼」的层级。配齐触屏：group-focus-within 兜底键盘/点击聚焦。
 */
const BASE =
  'gf-interactive inline-flex h-8 cursor-pointer items-center justify-center gap-1.5 rounded-lg !px-3 !text-xs font-medium transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgba(var(--gf-primary-rgb),0.4)]'

export const btnPrimary = `gf-interactive gf-btn-primary ${BASE}`

// 破坏性按钮：常驻但弱化，行 hover/focus-within 强化。tr 需挂 group 类。
export const btnDanger = `${BASE} !bg-red-500/10 !text-rose-700 opacity-60 ring-1 ring-inset ring-red-500/20 transition-opacity duration-150 hover:!opacity-100 hover:!bg-red-500/15 group-hover:opacity-100 group-focus-within:opacity-100`

/** 实心红：ConfirmModal 最终确认破坏性操作用（不走 BASE 的 ring，避免和红冲突） */
export const btnDangerSolid =
  'gf-interactive inline-flex h-9 cursor-pointer items-center justify-center gap-2 rounded-lg bg-red-500 px-4 py-2 text-sm font-medium text-white transition-colors duration-150 hover:bg-rose-600 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400'

export const btnNeutral = `${BASE} !bg-[var(--gf-surface)] gf-page-muted ring-1 ring-inset ring-[var(--gf-border)] hover:!text-[var(--gf-text)]`
