import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { installClientLogHooks } from '@/lib/client-log'
import { applyTheme } from '@/lib/theme/apply-theme'
import { DEFAULT_THEME_SETTINGS } from '@/lib/theme/presets'
import { useAuthStore } from '@/stores/auth-store'
import { useThemeStore } from '@/stores/theme-store'

applyTheme(DEFAULT_THEME_SETTINGS)

useThemeStore.persist.onFinishHydration(() => {
  applyTheme(useThemeStore.getState().settings)
})
if (useThemeStore.persist.hasHydrated()) {
  applyTheme(useThemeStore.getState().settings)
}

useAuthStore.persist.onFinishHydration(() => {
  useAuthStore.getState().setHydrated(true)
})
if (useAuthStore.persist.hasHydrated()) {
  useAuthStore.getState().setHydrated(true)
}

installClientLogHooks()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
