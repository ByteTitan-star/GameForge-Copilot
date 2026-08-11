import type { InputHTMLAttributes } from 'react'
import { cn } from '@/lib/cn'

type Props = InputHTMLAttributes<HTMLInputElement> & {
  label: string
  error?: string
  /** 'glass' 用于深色玻璃背景（如认证页 AuthShell）：浅色文字 + 半透明白底，避免黑底上近黑字看不清；'default' 走浅色画布 token。 */
  variant?: 'default' | 'glass'
}

export function Input({ id, label, error, variant = 'default', className, ...props }: Props) {
  const inputId = id ?? props.name
  const isGlass = variant === 'glass'
  return (
    <div className="space-y-1.5">
      <label
        htmlFor={inputId}
        className={cn('block text-xs font-medium', isGlass ? 'text-white/80' : 'gf-page-body')}
      >
        {label}
      </label>
      <input
        id={inputId}
        className={cn(
          'h-11 w-full rounded-lg px-3 text-sm',
          isGlass
            ? 'border border-white/15 bg-white/10 text-white outline-none transition-colors placeholder:text-white/45 focus:border-white/40 focus:ring-2 focus:ring-white/20'
            : 'gf-input',
          error && '!border-red-400',
          className,
        )}
        {...props}
      />
      {error ? (
        <p role="alert" className="text-xs text-red-300">
          {error}
        </p>
      ) : null}
    </div>
  )
}
