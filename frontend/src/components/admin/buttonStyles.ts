/**
 * 后台操作按钮样式（token 驱动，替代旧 AdminPage 里用 <Button variant="ghost"> 加 ! 覆盖的写法）。
 * 主操作走主题渐变；破坏性操作用语义红；中性操作走 chip 风。跨主题一致。
 */
export const btnPrimary =
  'gf-interactive gf-btn-primary inline-flex h-8 cursor-pointer items-center gap-1.5 !rounded-lg !px-3 !text-xs disabled:cursor-not-allowed disabled:opacity-50'

export const btnDanger =
  'gf-interactive inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-lg border border-red-500/30 bg-red-500/10 !px-3 !text-xs font-medium text-red-500 transition hover:bg-red-500/20 disabled:cursor-not-allowed disabled:opacity-50'

export const btnNeutral =
  'gf-interactive inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--gf-border)] bg-[var(--gf-surface)] !px-3 !text-xs gf-page-muted transition hover:text-[var(--gf-text)] disabled:cursor-not-allowed disabled:opacity-50'
