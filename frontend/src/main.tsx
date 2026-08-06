import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { env } from '@/lib/env'
import { useAuthStore } from '@/stores/auth-store'

async function prepare() {
  if (env.useMock) {
    const { worker } = await import('@/mocks/browser')
    await worker.start({
      onUnhandledRequest: 'bypass',
      quiet: true,
    })
  }
}

useAuthStore.persist.onFinishHydration(() => {
  useAuthStore.getState().setHydrated(true)
})
if (useAuthStore.persist.hasHydrated()) {
  useAuthStore.getState().setHydrated(true)
}

void prepare().then(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
})
