/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  readonly VITE_HOSTING_BASE_URL?: string
  readonly VITE_WS_BASE_URL?: string
  readonly VITE_OAUTH_ENABLED?: string
  readonly VITE_SUPPORT_EMAIL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
