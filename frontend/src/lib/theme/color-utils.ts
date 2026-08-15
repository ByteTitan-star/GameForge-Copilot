/** 解析 #RGB / #RRGGBB，供 CSS rgba() 变量使用 */

export function normalizeHex(input: string): string | null {
  const raw = input.trim()
  if (/^#[0-9a-fA-F]{6}$/.test(raw)) return raw.toUpperCase()
  if (/^#[0-9a-fA-F]{3}$/.test(raw)) {
    const [, r, g, b] = raw
    return `#${r}${r}${g}${g}${b}${b}`.toUpperCase()
  }
  return null
}

export function sanitizeThemeColors<T extends { primary: string; secondary: string; background: string }>(
  colors: T,
  fallback: T,
): T {
  return {
    ...colors,
    primary: normalizeHex(colors.primary) ?? fallback.primary,
    secondary: normalizeHex(colors.secondary) ?? fallback.secondary,
    background: normalizeHex(colors.background) ?? fallback.background,
  }
}

export function hexToRgb(hex: string): { r: number; g: number; b: number } | null {
  const n = normalizeHex(hex)
  if (!n) return null
  const r = parseInt(n.slice(1, 3), 16)
  const g = parseInt(n.slice(3, 5), 16)
  const b = parseInt(n.slice(5, 7), 16)
  return { r, g, b }
}

/** sRGB 相对亮度 0–1 */
export function relativeLuminance(hex: string): number {
  const rgb = hexToRgb(hex)
  if (!rgb) return 0
  const channel = (c: number) => {
    const s = c / 255
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * channel(rgb.r) + 0.7152 * channel(rgb.g) + 0.0722 * channel(rgb.b)
}

/** 主按钮文字：渐变中间色亮度决定黑/白字 */
export function contrastTextOn(primary: string, secondary: string): string {
  const a = hexToRgb(primary)
  const b = hexToRgb(secondary)
  if (!a || !b) return '#FFFFFF'
  const lum =
    (0.2126 * (a.r + b.r) / 2 + 0.7152 * (a.g + b.g) / 2 + 0.0722 * (a.b + b.b) / 2) / 255
  return lum > 0.62 ? '#0F172A' : '#FFFFFF'
}
