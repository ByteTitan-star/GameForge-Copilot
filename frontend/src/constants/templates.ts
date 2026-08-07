export type GameTemplate = {
  id: string
  titleKey: 'templateSnake' | 'templateRunner' | 'templateTower' | 'templateBlank'
  emoji: string
  requirement_seed: string
}

export const GAME_TEMPLATES: GameTemplate[] = [
  {
    id: 'snake',
    titleKey: 'templateSnake',
    emoji: '🐍',
    requirement_seed:
      '做一个经典贪吃蛇：方向键控制，吃豆子加分，撞墙或撞到自己游戏结束；霓虹配色，速度随分数略增。',
  },
  {
    id: 'runner',
    titleKey: 'templateRunner',
    emoji: '🏃',
    requirement_seed:
      '做一个横版跑酷：空格跳跃，躲避障碍，收集金币；像素风，难度逐渐上升，显示距离得分。',
  },
  {
    id: 'tower',
    titleKey: 'templateTower',
    emoji: '🏰',
    requirement_seed:
      '做一个简易塔防：鼠标放置炮塔，怪物沿固定路径前进；至少 3 种塔、5 波敌人，显示金币与生命。',
  },
  {
    id: 'blank',
    titleKey: 'templateBlank',
    emoji: '✨',
    requirement_seed: '',
  },
]

export function getTemplateById(id: string): GameTemplate | undefined {
  return GAME_TEMPLATES.find((t) => t.id === id)
}
