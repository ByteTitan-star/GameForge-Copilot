function stripApiSuffix(url: string): string {
  return url.replace(/\/api\/v1\/?$/, '')
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api/v1'
const hostingBaseUrl =
  import.meta.env.VITE_HOSTING_BASE_URL ?? stripApiSuffix(apiBaseUrl)
const wsBaseUrl =
  import.meta.env.VITE_WS_BASE_URL ??
  hostingBaseUrl.replace(/^http/i, (m) => (m.toLowerCase() === 'https' ? 'wss' : 'ws'))

export const env = {
  apiBaseUrl,
  hostingBaseUrl,
  wsBaseUrl,
}
