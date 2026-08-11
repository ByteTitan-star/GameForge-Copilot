// 官方游戏封面图：slug → 静态图路径。
// 文件名与后端 OFFICIAL_CATALOG 的 slug 一一对应（backend/app/games/official.py），
// 图片放 frontend/public/official/{slug}.png；新增官方游戏时在此加一行 slug。
// 非官方游戏返回 null，由 PublicGameCard 回退到渐变封面。

const OFFICIAL_COVER_SLUGS: ReadonlySet<string> = new Set([
  'official-neon-snake',
  'official-pixel-runner',
  'official-tower-stub',
])

export function officialCoverUrl(slug: string): string | null {
  if (!OFFICIAL_COVER_SLUGS.has(slug)) return null
  return `${import.meta.env.BASE_URL}official/${slug}.png`
}
