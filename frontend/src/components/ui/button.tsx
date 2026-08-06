import type { ButtonHTMLAttributes } from 'react'
import { cn } from '@/lib/cn'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'ink' | 'soft'

const variants: Record<Variant, string> = {
  primary:
    'bg-white text-black shadow-sm hover:bg-white/90 hover:shadow-md active:scale-[0.98]',
  secondary:
    'border border-white/25 bg-white/10 text-white backdrop-blur-md hover:bg-white/20 hover:border-white/40 active:scale-[0.98]',
  ghost: 'bg-transparent text-white/85 hover:bg-white/10 hover:text-white active:scale-[0.98]',
  danger: 'bg-red-500 text-white hover:bg-red-500/90 active:scale-[0.98]',
  ink: 'bg-[#0F172A] text-white shadow-sm hover:bg-[#1E293B] hover:shadow-md active:scale-[0.98]',
  soft:
    'border border-black/[0.06] bg-white text-[#0F172A] shadow-sm hover:border-black/10 hover:shadow-md active:scale-[0.98]',
}

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant
}

export function Button({ className, variant = 'primary', type = 'button', ...props }: Props) {
  return (
    <button
      type={type}
      className={cn(
        'inline-flex cursor-pointer items-center justify-center gap-2 rounded-xl px-5 py-2.5 text-sm font-medium transition-[transform,background-color,box-shadow,border-color,color] duration-200 ease-out disabled:cursor-not-allowed disabled:opacity-50',
        variants[variant],
        className,
      )}
      {...props}
    />
  )
}
