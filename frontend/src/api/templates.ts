import { apiRequest } from './client'
import { GAME_TEMPLATES } from '@/constants/templates'

export type GameTemplate = {
  template_id: string
  title: string
  description: string
  requirement_seed: string
  tags: string[]
}

const FALLBACK: GameTemplate[] = GAME_TEMPLATES.filter((t) => t.id !== 'blank').map((t) => ({
  template_id: t.id,
  title: t.id,
  description: '',
  requirement_seed: t.requirement_seed,
  tags: [t.id],
}))

export const templatesApi = {
  async list(): Promise<GameTemplate[]> {
    try {
      const rows = await apiRequest<GameTemplate[]>('/templates')
      if (rows.length > 0) return rows
    } catch {
      /* fallback */
    }
    return FALLBACK
  },
}

export function templateEmoji(id: string): string {
  const map: Record<string, string> = {
    snake: '🐍',
    runner: '🏃',
    tower: '🏰',
    blank: '✨',
  }
  return map[id] ?? '🎮'
}
