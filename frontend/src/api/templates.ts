import { apiRequest } from './client'

export type GameTemplate = {
  template_id: string
  title: string
  description: string
  requirement_seed: string
  tags: string[]
  engine: string
  playable: boolean
  play_url: string | null
}

const TAG_EMOJI: Record<string, string> = {
  arcade: '🕹️',
  survival: '🛡️',
  platformer: '🏃',
  racing: '🏎️',
  rhythm: '🎵',
  casual: '🎯',
  physics: '⚙️',
  puzzle: '🧩',
  strategy: '🎯',
  action: '⚔️',
  shooter: '🔫',
  space: '🚀',
  stealth: '🥷',
  logic: '🧠',
  math: '🔢',
  simulation: '📊',
  sandbox: '🧪',
  creative: '🎨',
  management: '📈',
  keyboard: '⌨️',
  mouse: '🖱️',
  music: '🎶',
  grid: '▦',
  timing: '⏱️',
  exploration: '🧭',
  resource: '💎',
  factory: '🏭',
  economy: '💰',
  'turn-based': '♟️',
  territory: '🗺️',
  particles: '✨',
  generative: '🌀',
  drawing: '✏️',
  educational: '📚',
  trajectory: '🎯',
  building: '🏗️',
  traffic: '🚦',
  ecosystem: '🌿',
  automation: '⚡',
  match: '🔗',
  laser: '🔦',
  procedural: '🎲',
  memory: '🧠',
  circuit: '🔌',
  'tower-defense': '🏰',
  'one-button': '👆',
}

export const templatesApi = {
  async list(): Promise<GameTemplate[]> {
    try {
      const rows = await apiRequest<GameTemplate[]>('/templates')
      return rows
    } catch {
      return []
    }
  },
}

export function templateEmoji(id: string, tags: string[] = []): string {
  const legacy: Record<string, string> = {
    snake: '🐍',
    runner: '🏃',
    tower: '🏰',
    blank: '✨',
  }
  if (legacy[id]) return legacy[id]
  for (const tag of tags) {
    const emoji = TAG_EMOJI[tag]
    if (emoji) return emoji
  }
  return '🎮'
}
