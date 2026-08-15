import { useMemo } from 'react'
import { RotateCcw, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { CustomColorField } from '@/components/theme/CustomColorField'
import { useT } from '@/i18n/use-t'
import { cn } from '@/lib/cn'
import { WORKSHOP_DESIGN_PROMPTS } from '@/lib/theme/design-prompts'
import { THEME_PRESETS } from '@/lib/theme/presets'
import type { ThemeGlow } from '@/lib/theme/types'
import { useLocaleStore } from '@/stores/locale-store'
import { useThemeStore } from '@/stores/theme-store'

type ThemePanelProps = {
  className?: string
}

const glowOptions: { id: ThemeGlow; labelZh: string; labelEn: string }[] = [
  { id: 'off', labelZh: '关闭', labelEn: 'Off' },
  { id: 'soft', labelZh: '柔和', labelEn: 'Soft' },
  { id: 'strong', labelZh: '强烈', labelEn: 'Strong' },
]

export function ThemePanel({ className }: ThemePanelProps) {
  const t = useT()
  const locale = useLocaleStore((s) => s.locale)
  const settings = useThemeStore((s) => s.settings)
  const applyPreset = useThemeStore((s) => s.applyPreset)
  const setCustomColors = useThemeStore((s) => s.setCustomColors)
  const setGradientAngle = useThemeStore((s) => s.setGradientAngle)
  const setDynamicBackground = useThemeStore((s) => s.setDynamicBackground)
  const setGlow = useThemeStore((s) => s.setGlow)
  const resetTheme = useThemeStore((s) => s.resetTheme)

  const activePreset = THEME_PRESETS.find((p) => p.id === settings.presetId)

  const colorFields = useMemo(
    () =>
      [
        { key: 'primary' as const, label: t('themePrimary'), hint: t('themePrimaryHint') },
        { key: 'secondary' as const, label: t('themeSecondary'), hint: t('themeSecondaryHint') },
        { key: 'background' as const, label: t('themeBackground'), hint: t('themeBackgroundHint') },
      ] as const,
    [t],
  )

  return (
    <div className={cn('space-y-6', className)}>
      <p className="gf-banner-info rounded-xl px-4 py-3 text-sm leading-relaxed">{t('themeLocalHint')}</p>

      <section className="space-y-3">
        <h3 className="gf-page-body text-sm font-medium">{t('themePresets')}</h3>
        <p className="gf-page-muted text-xs leading-relaxed">{t('themePresetHint')}</p>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {THEME_PRESETS.map((preset) => {
            const active = settings.presetId === preset.id
            const name = locale === 'zh' ? preset.name : preset.nameEn
            const blurb = WORKSHOP_DESIGN_PROMPTS[preset.style]
            return (
              <button
                key={preset.id}
                type="button"
                onClick={() => applyPreset(preset.id)}
                className={cn(
                  'gf-interactive gf-preset-card cursor-pointer rounded-xl p-3 text-left transition',
                  active && 'gf-preset-card-active',
                )}
              >
                <span
                  className="mb-2 block h-8 rounded-lg border border-black/[0.04]"
                  style={{
                    background: `linear-gradient(${preset.gradientAngle ?? 135}deg, ${preset.colors.secondary}, ${preset.colors.primary})`,
                  }}
                />
                <span className="gf-page-body block text-sm font-medium">{name}</span>
                <span className="gf-page-muted mt-1 block text-[10px] leading-snug">
                  {locale === 'zh' ? blurb.zh : blurb.en}
                </span>
              </button>
            )
          })}
        </div>
        {activePreset ? (
          <p className="gf-page-muted rounded-xl bg-black/[0.02] px-3 py-2 text-xs leading-relaxed ring-1 ring-[var(--gf-border)]">
            {locale === 'zh'
              ? WORKSHOP_DESIGN_PROMPTS[activePreset.style].zh
              : WORKSHOP_DESIGN_PROMPTS[activePreset.style].en}
          </p>
        ) : null}
      </section>

      <section className="gf-glass space-y-4 rounded-2xl p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="gf-page-body text-sm font-medium">{t('themeCustomPalette')}</h3>
          {settings.presetId === 'custom' ? (
            <span className="gf-chip-active rounded-md px-2 py-0.5 text-[11px]">{t('themeCustomBadge')}</span>
          ) : null}
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          {colorFields.map(({ key, label, hint }) => (
            <CustomColorField
              key={key}
              colorKey={key}
              label={label}
              hint={hint}
              value={settings.colors[key]}
              onCommit={(colorKey, normalized) => setCustomColors({ [colorKey]: normalized })}
            />
          ))}
        </div>

        <label className="block space-y-2">
          <div className="gf-page-muted flex items-center justify-between text-xs">
            <span>{t('themeGradientAngle')}</span>
            <span className="gf-page-body font-mono">{settings.gradientAngle}°</span>
          </div>
          <input
            type="range"
            min={0}
            max={360}
            value={settings.gradientAngle}
            onChange={(e) => setGradientAngle(Number(e.target.value))}
            className="gf-range w-full"
          />
        </label>

        <div className="flex flex-wrap gap-4">
          <label className="gf-page-body flex cursor-pointer items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={settings.dynamicBackground}
              onChange={(e) => setDynamicBackground(e.target.checked)}
              className="gf-checkbox h-4 w-4 rounded accent-[var(--gf-primary)]"
            />
            {t('themeDynamicBg')}
          </label>
        </div>

        <div className="space-y-2">
          <span className="gf-page-muted block text-xs">{t('themeGlow')}</span>
          <div className="flex flex-wrap gap-2">
            {glowOptions.map(({ id, labelZh, labelEn }) => (
              <button
                key={id}
                type="button"
                onClick={() => setGlow(id)}
                className={cn(
                  'gf-interactive cursor-pointer rounded-lg px-3 py-1.5 text-xs transition',
                  settings.glow === id ? 'gf-chip-active' : 'gf-chip',
                )}
              >
                {locale === 'zh' ? labelZh : labelEn}
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="gf-glass rounded-2xl p-5">
        <h3 className="gf-page-body text-sm font-medium">{t('themePreview')}</h3>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            type="button"
            className="gf-btn-primary gf-interactive inline-flex items-center gap-2 px-5 py-2.5 text-sm"
          >
            <Sparkles className="h-4 w-4" />
            {t('themePreviewButton')}
          </button>
          <span className="gf-text-accent text-sm">{t('themePreviewLink')}</span>
          <span className="gf-chip rounded-lg px-3 py-1 text-xs">{t('themePreviewChip')}</span>
        </div>
      </section>

      <div className="flex justify-end">
        <Button
          type="button"
          variant="ghost"
          className="!text-[var(--gf-text-muted)] hover:!text-[var(--gf-text)]"
          onClick={() => resetTheme()}
        >
          <RotateCcw className="mr-2 h-4 w-4" />
          {t('themeReset')}
        </Button>
      </div>
    </div>
  )
}
