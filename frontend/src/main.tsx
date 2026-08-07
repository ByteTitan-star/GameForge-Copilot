import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { useAuthStore } from '@/stores/auth-store'

useAuthStore.persist.onFinishHydration(() => {
  useAuthStore.getState().setHydrated(true)
})
if (useAuthStore.persist.hasHydrated()) {
  useAuthStore.getState().setHydrated(true)
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
