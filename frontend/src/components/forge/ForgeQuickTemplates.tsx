import { Gamepad2, Heart, Users } from 'lucide-react'
import { useT } from '@/i18n/use-t'
import { cn } from '@/lib/cn'

const chips = [
  {
    key: 'retroShooter',
    promptKey: 'retroShooterPrompt',
    icon: Gamepad2,
    hover: 'hover:border-rose-300 hover:shadow-rose-200/50',
  },
  {
    key: 'coopAdventure',
    promptKey: 'coopAdventurePrompt',
    icon: Users,
    hover: 'hover:border-orange-300 hover:shadow-orange-200/50',
  },
  {
    key: 'cozyCollection',
    promptKey: 'cozyCollectionPrompt',
    icon: Heart,
    hover: 'hover:border-emerald-300 hover:shadow-emerald-200/50',
  },
] as const

type Props = {
  onPick: (text: string) => void
  className?: string
}

export function ForgeQuickTemplates({ onPick, className }: Props) {
  const t = useT()

  return (
    <div className={cn('space-y-2', className)}>
      <p className="font-mono text-[10px] tracking-[0.12em] text-[var(--gf-text-muted)] uppercase">
        {t('quickTemplates')}
      </p>
      <div className="flex flex-wrap gap-2">
        {chips.map(({ key, promptKey, icon: Icon, hover }) => {
          const label = t(key)
          return (
            <button
              key={key}
              type="button"
              onClick={() => onPick(t(promptKey))}
              className={cn(
                'gf-forge-template-chip gf-interactive flex cursor-pointer items-center gap-2 rounded-2xl border px-3 py-2 text-sm text-[var(--gf-text)] transition-all duration-200',
                hover,
              )}
            >
              <Icon className="h-4 w-4 text-[var(--gf-text-muted)]" />
              {label}
            </button>
          )
        })}
      </div>
    </div>
  )
}
