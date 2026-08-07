/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  readonly VITE_HOSTING_BASE_URL?: string
  readonly VITE_WS_BASE_URL?: string
  readonly VITE_OAUTH_ENABLED?: string
  readonly VITE_PUBLIC_GAMES_MOCK?: string
  readonly VITE_USAGE_BREAKDOWN_MOCK?: string
  readonly VITE_ADMIN_ANALYTICS_MOCK?: string
  readonly VITE_SUPPORT_EMAIL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
