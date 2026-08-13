const header = document.querySelector('[data-header]')

function updateHeader() {
  header?.classList.toggle('is-scrolled', window.scrollY > 16)
}

updateHeader()
window.addEventListener('scroll', updateHeader, { passive: true })
