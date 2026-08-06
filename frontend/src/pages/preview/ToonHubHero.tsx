import { useCallback, useEffect, useMemo, useState, type CSSProperties } from 'react'
import { ArrowLeft, ArrowRight } from 'lucide-react'

const IMAGES = [
  {
    src: 'https://fifth-gentle-45902158.figma.site/_components/v2/4de492f6d9cf8244ad5293233e5c6f52407d42fc/1.02464a56.png',
    bg: '#F4845F',
    panel: '#F79B7F',
  },
  {
    src: 'https://fifth-gentle-45902158.figma.site/_components/v2/4de492f6d9cf8244ad5293233e5c6f52407d42fc/2.b977faab.png',
    bg: '#6BBF7A',
    panel: '#85CC92',
  },
  {
    src: 'https://fifth-gentle-45902158.figma.site/_components/v2/4de492f6d9cf8244ad5293233e5c6f52407d42fc/3.4df853b4.png',
    bg: '#E882B4',
    panel: '#ED9DC4',
  },
  {
    src: 'https://fifth-gentle-45902158.figma.site/_components/v2/4de492f6d9cf8244ad5293233e5c6f52407d42fc/4.4457fbce.png',
    bg: '#6EB5FF',
    panel: '#8DC4FF',
  },
] as const

const TRANSITION =
  'transform 650ms cubic-bezier(0.4,0,0.2,1), filter 650ms cubic-bezier(0.4,0,0.2,1), opacity 650ms cubic-bezier(0.4,0,0.2,1), left 650ms cubic-bezier(0.4,0,0.2,1)'

const GRAIN_SVG =
  "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.08'/%3E%3C/svg%3E\")"

type Role = 'center' | 'left' | 'right' | 'back'

function roleForIndex(index: number, activeIndex: number): Role {
  const center = activeIndex
  const left = (activeIndex + 3) % 4
  const right = (activeIndex + 1) % 4
  const back = (activeIndex + 2) % 4
  if (index === center) return 'center'
  if (index === left) return 'left'
  if (index === right) return 'right'
  if (index === back) return 'back'
  return 'back'
}

function roleStyle(role: Role, isMobile: boolean): CSSProperties {
  const base: CSSProperties = {
    position: 'absolute',
    aspectRatio: '0.6 / 1',
    transition: TRANSITION,
    willChange: 'transform, filter, opacity',
  }

  switch (role) {
    case 'center':
      return {
        ...base,
        transform: `translateX(-50%) scale(${isMobile ? 1.25 : 1.68})`,
        filter: 'none',
        opacity: 1,
        zIndex: 20,
        left: '50%',
        height: isMobile ? '60%' : '92%',
        bottom: isMobile ? '22%' : 0,
      }
    case 'left':
      return {
        ...base,
        transform: 'translateX(-50%) scale(1)',
        filter: 'blur(2px)',
        opacity: 0.85,
        zIndex: 10,
        left: isMobile ? '20%' : '30%',
        height: isMobile ? '16%' : '28%',
        bottom: isMobile ? '32%' : '12%',
      }
    case 'right':
      return {
        ...base,
        transform: 'translateX(-50%) scale(1)',
        filter: 'blur(2px)',
        opacity: 0.85,
        zIndex: 10,
        left: isMobile ? '80%' : '70%',
        height: isMobile ? '16%' : '28%',
        bottom: isMobile ? '32%' : '12%',
      }
    case 'back':
      return {
        ...base,
        transform: 'translateX(-50%) scale(1)',
        filter: 'blur(4px)',
        opacity: 1,
        zIndex: 5,
        left: '50%',
        height: isMobile ? '13%' : '22%',
        bottom: isMobile ? '32%' : '12%',
      }
  }
}

export function ToonHubHero() {
  const [activeIndex, setActiveIndex] = useState(0)
  const [isAnimating, setIsAnimating] = useState(false)
  const [isMobile, setIsMobile] = useState(
    () => typeof window !== 'undefined' && window.innerWidth < 640,
  )

  useEffect(() => {
    IMAGES.forEach((item) => {
      const img = new Image()
      img.src = item.src
    })
  }, [])

  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < 640)
    onResize()
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  const navigate = useCallback(
    (dir: 'next' | 'prev') => {
      if (isAnimating) return
      setIsAnimating(true)
      setActiveIndex((prev) => (dir === 'next' ? (prev + 1) % 4 : (prev + 3) % 4))
      window.setTimeout(() => setIsAnimating(false), 650)
    },
    [isAnimating],
  )

  const activeBg = useMemo(() => IMAGES[activeIndex].bg, [activeIndex])

  return (
    <div
      className="relative w-full overflow-hidden"
      style={{
        backgroundColor: activeBg,
        transition: 'background-color 650ms cubic-bezier(0.4,0,0.2,1)',
        fontFamily: 'Inter, sans-serif',
      }}
    >
      <div className="relative w-full" style={{ height: '100vh', overflow: 'hidden' }}>
        {/* Grain overlay */}
        <div
          className="pointer-events-none absolute inset-0"
          style={{
            zIndex: 50,
            opacity: 0.4,
            backgroundImage: GRAIN_SVG,
            backgroundSize: '200px 200px',
            backgroundRepeat: 'repeat',
          }}
          aria-hidden
        />

        {/* Giant ghost text */}
        <div
          className="pointer-events-none absolute inset-x-0 flex select-none items-center justify-center"
          style={{ zIndex: 2, top: '18%' }}
        >
          <span
            style={{
              fontFamily: 'Anton, sans-serif',
              fontSize: 'clamp(90px, 28vw, 380px)',
              fontWeight: 900,
              color: '#fff',
              opacity: 1,
              lineHeight: 1,
              textTransform: 'uppercase',
              letterSpacing: '-0.02em',
              whiteSpace: 'nowrap',
            }}
          >
            3D SHAPE
          </span>
        </div>

        {/* Brand */}
        <div
          className="absolute top-6 left-4 text-xs font-semibold uppercase sm:left-8"
          style={{ zIndex: 60, color: '#fff', opacity: 0.9, letterSpacing: '0.18em' }}
        >
          TOONHUB
        </div>

        {/* Carousel */}
        <div className="absolute inset-0" style={{ zIndex: 3 }}>
          {IMAGES.map((item, index) => {
            const role = roleForIndex(index, activeIndex)
            return (
              <div key={item.src} style={roleStyle(role, isMobile)}>
                <img
                  src={item.src}
                  alt=""
                  draggable={false}
                  style={{
                    width: '100%',
                    height: '100%',
                    objectFit: 'contain',
                    objectPosition: 'bottom center',
                  }}
                />
              </div>
            )
          })}
        </div>

        {/* Bottom-left copy + nav */}
        <div
          className="absolute bottom-6 left-4 max-w-[320px] sm:bottom-20 sm:left-24"
          style={{ zIndex: 60 }}
        >
          <p
            className="mb-2 text-base font-bold uppercase tracking-widest sm:mb-3 sm:text-[22px]"
            style={{ color: '#fff', opacity: 0.95, letterSpacing: '0.02em' }}
          >
            TOONHUB FIGURINES
          </p>
          <p
            className="mb-4 hidden text-xs sm:mb-5 sm:block sm:text-sm"
            style={{ color: '#fff', opacity: 0.85, lineHeight: 1.6 }}
          >
            The artwork is stunning, shipped fully prepared. The finish is a vision, the 3D craft
            is flawless. Many thanks! Wishing you the win. Order now.
          </p>
          <div className="flex gap-3">
            <button
              type="button"
              aria-label="Previous"
              onClick={() => navigate('prev')}
              className="flex h-12 w-12 cursor-pointer items-center justify-center rounded-full border-2 border-white bg-transparent text-white transition-[transform,background-color] duration-150 hover:scale-[1.08] hover:bg-white/12 sm:h-16 sm:w-16"
            >
              <ArrowLeft size={26} strokeWidth={2.25} />
            </button>
            <button
              type="button"
              aria-label="Next"
              onClick={() => navigate('next')}
              className="flex h-12 w-12 cursor-pointer items-center justify-center rounded-full border-2 border-white bg-transparent text-white transition-[transform,background-color] duration-150 hover:scale-[1.08] hover:bg-white/12 sm:h-16 sm:w-16"
            >
              <ArrowRight size={26} strokeWidth={2.25} />
            </button>
          </div>
        </div>

        {/* Bottom-right link */}
        <a
          href="#discover"
          className="absolute bottom-6 right-4 flex items-center gap-2 uppercase no-underline transition-opacity duration-200 hover:opacity-100 sm:bottom-20 sm:right-10"
          style={{
            zIndex: 60,
            fontFamily: 'Anton, sans-serif',
            fontSize: 'clamp(20px, 4vw, 56px)',
            fontWeight: 400,
            color: '#fff',
            opacity: 0.95,
            letterSpacing: '-0.02em',
            lineHeight: 1,
            cursor: 'pointer',
          }}
        >
          DISCOVER IT
          <ArrowRight className="h-5 w-5 sm:h-8 sm:w-8" strokeWidth={2.25} />
        </a>
      </div>
    </div>
  )
}
