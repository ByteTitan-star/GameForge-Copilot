/** GameForge 工坊主题 — 改编自外部 Hero 参考（非 agency 文案，浅色工作台） */

export type WorkshopDesignRef = 'atelier' | 'forma' | 'taskly' | 'arcade'

export const WORKSHOP_DESIGN_PROMPTS: Record<
  WorkshopDesignRef,
  { zh: string; en: string }
> = {
  atelier: {
    zh: '暗色电影感只用于侧栏点缀；主内容区浅底、Instrument 风格标题感、全屏动态光斑可选。导航高对比，CTA 圆角胶囊。',
    en: 'Cinematic accent on the shell only; light canvas for games/forge/settings. High-contrast nav, pill CTAs, optional video-style glow orbs.',
  },
  forma: {
    zh: '圆角卡片 + 毛玻璃顶栏；主色偏蓝，表单/卡片白底阴影。适合「我的游戏」列表与设置页信息块。',
    en: 'Rounded cards and frosted nav pill; blue accent on white surfaces with soft shadows for games list and settings.',
  },
  taskly: {
    zh: 'Liquid Glass 侧栏：强 blur、内高光描边；电光蓝主色。按钮带渐变与 hover 缩放，光晕可调。',
    en: 'Liquid-glass sidebar with strong blur and inset highlight; electric-blue accent, gradient buttons, adjustable glow.',
  },
  arcade: {
    zh: '街机霓虹主辅色落在浅蓝底上；保留动态背景与渐变主按钮，适配小游戏创作工坊气质。',
    en: 'Arcade neon primary/secondary on a light blue canvas; dynamic orbs and gradient CTAs for game-forge workflows.',
  },
}

export const THEME_SCHEMA_VERSION = 2
