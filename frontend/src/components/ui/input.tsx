import type { InputHTMLAttributes } from 'react'
import { cn } from '@/lib/cn'

type Props = InputHTMLAttributes<HTMLInputElement> & {
  label: string
  error?: string
}

export function Input({ id, label, error, className, ...props }: Props) {
  const inputId = id ?? props.name
  return (
    <div className="space-y-1.5">
      <label htmlFor={inputId} className="block text-xs font-medium text-white/80">
        {label}
      </label>
      <input
        id={inputId}
        className={cn(
          'h-11 w-full rounded-lg border border-white/20 bg-white/10 px-3 text-sm text-white outline-none backdrop-blur-md transition placeholder:text-white/35 focus-visible:ring-2 focus-visible:ring-white/45',
          error && 'border-red-400/80',
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
