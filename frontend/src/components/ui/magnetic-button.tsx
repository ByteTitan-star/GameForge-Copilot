import {
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type CSSProperties,
  type PointerEvent,
} from 'react'
import { cn } from '@/lib/cn'

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'light' | 'dark' | 'soft'
}

const variants = {
  light:
    'bg-white text-black shadow-[0_10px_40px_rgba(0,0,0,0.25)] hover:shadow-[0_14px_48px_rgba(0,0,0,0.35)]',
  dark: 'bg-[#0F172A] text-white shadow-[0_10px_30px_rgba(15,23,42,0.25)] hover:bg-[#1E293B]',
  soft: 'bg-white/70 text-[#0F172A] border border-black/5 backdrop-blur-md hover:bg-white',
}

/** 轻微跟随指针的 CTA，触摸设备退化为普通按钮 */
export function MagneticButton({
  className,
  variant = 'light',
  type = 'button',
  children,
  ...props
}: Props) {
  const ref = useRef<HTMLButtonElement>(null)
  const [shift, setShift] = useState({ x: 0, y: 0 })

  function onPointerMove(e: PointerEvent<HTMLButtonElement>) {
    if (e.pointerType !== 'mouse') return
    const el = ref.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    const x = e.clientX - (rect.left + rect.width / 2)
    const y = e.clientY - (rect.top + rect.height / 2)
    setShift({ x: x * 0.18, y: y * 0.18 })
  }

  function reset() {
    setShift({ x: 0, y: 0 })
  }

  const style = {
    transform: `translate3d(${shift.x}px, ${shift.y}px, 0) scale(1)`,
  } as CSSProperties

  return (
    <button
      ref={ref}
      type={type}
      style={style}
      className={cn(
        'inline-flex cursor-pointer items-center justify-center gap-2 rounded-full px-6 py-3 text-sm font-semibold transition-[transform,box-shadow,background-color] duration-200 ease-out will-change-transform active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-50',
        variants[variant],
        className,
      )}
      {...props}
      onPointerMove={(e) => {
        props.onPointerMove?.(e)
        onPointerMove(e)
      }}
      onPointerLeave={(e) => {
        props.onPointerLeave?.(e)
        reset()
      }}
      onPointerUp={(e) => {
        props.onPointerUp?.(e)
        reset()
      }}
    >
      {children}
    </button>
  )
}
