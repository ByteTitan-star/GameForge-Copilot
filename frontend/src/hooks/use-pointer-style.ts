import { useCallback, useRef, useState, type CSSProperties, type PointerEvent } from 'react'

/** 指针相对元素中心的归一化偏移，用于光晕 / 轻微倾斜 */
export function usePointerStyle(maxTilt = 6) {
  const ref = useRef<HTMLElement | null>(null)
  const [style, setStyle] = useState<CSSProperties>({})

  const onPointerMove = useCallback(
    (e: PointerEvent<HTMLElement>) => {
      const el = ref.current
      if (!el) return
      const rect = el.getBoundingClientRect()
      const x = e.clientX - rect.left
      const y = e.clientY - rect.top
      const px = (x / rect.width) * 100
      const py = (y / rect.height) * 100
      const rx = ((y / rect.height) - 0.5) * -maxTilt
      const ry = ((x / rect.width) - 0.5) * maxTilt
      setStyle({
        '--spot-x': `${px}%`,
        '--spot-y': `${py}%`,
        transform: `perspective(900px) rotateX(${rx}deg) rotateY(${ry}deg)`,
      } as CSSProperties)
    },
    [maxTilt],
  )

  const onPointerLeave = useCallback(() => {
    setStyle({
      '--spot-x': '50%',
      '--spot-y': '40%',
      transform: 'perspective(900px) rotateX(0deg) rotateY(0deg)',
    } as CSSProperties)
  }, [])

  return { ref, style, onPointerMove, onPointerLeave }
}
