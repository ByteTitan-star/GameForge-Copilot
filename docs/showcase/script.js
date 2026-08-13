document.documentElement.classList.add('has-js')

const header = document.querySelector('[data-header]')
const revealItems = document.querySelectorAll('.reveal')

function updateHeader() {
  header?.classList.toggle('is-scrolled', window.scrollY > 16)
}

updateHeader()
window.addEventListener('scroll', updateHeader, { passive: true })

if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
  revealItems.forEach((item) => item.classList.add('is-visible'))
} else {
  const observer = new IntersectionObserver(
    (entries, currentObserver) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return
        entry.target.classList.add('is-visible')
        currentObserver.unobserve(entry.target)
      })
    },
    { rootMargin: '0px 0px -8% 0px', threshold: 0.08 },
  )

  revealItems.forEach((item, index) => {
    item.style.transitionDelay = `${Math.min(index % 6, 4) * 55}ms`
    observer.observe(item)
  })
}
