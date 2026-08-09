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
      <label htmlFor={inputId} className="block text-xs font-medium gf-page-body">
        {label}
      </label>
      <input
        id={inputId}
        className={cn(
          'gf-input h-11 w-full rounded-lg px-3 text-sm',
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
