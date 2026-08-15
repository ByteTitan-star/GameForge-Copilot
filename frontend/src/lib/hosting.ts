import { env } from './env'
import { authApi } from '@/api/auth'
import { gamesApi } from '@/api/games'
import { useAuthStore } from '@/stores/auth-store'

function joinUrl(base: string, path: string): string {
  const b = base.replace(/\/$/, '')
  const p = path.startsWith('/') ? path : `/${path}`
  return `${b}${p}`
}

// dev 给 artifact URL 加版本戳破浏览器强缓存（改产物/CSP 后刷新即生效）；生产留空走后端 ETag
const ARTIFACT_VER = import.meta.env.DEV ? `${Date.now()}` : ''

export function playArtifactUrl(slug: string): string {
  const q = ARTIFACT_VER ? `?v=${ARTIFACT_VER}` : ''
  return joinUrl(env.hostingBaseUrl, `/play/${encodeURIComponent(slug)}${q}`)
}

export function templatePlayUrl(templateId: string): string {
  const q = ARTIFACT_VER ? `?v=${ARTIFACT_VER}` : ''
  return joinUrl(
    env.hostingBaseUrl,
    `/play/template/${encodeURIComponent(templateId)}${q}`,
  )
}

export function draftArtifactUrl(gameId: string, version: number | string): string {
  const q = ARTIFACT_VER ? `?v=${ARTIFACT_VER}` : ''
  return joinUrl(
    env.hostingBaseUrl,
    `/draft/${encodeURIComponent(gameId)}/${encodeURIComponent(String(version))}${q}`,
  )
}

/** preview token 路径（Vite 多文件 dist），iframe 可直接加载无需 Bearer */
export function isPreviewTokenUrl(src: string): boolean {
  return /\/preview\//.test(src)
}

/** 向 API 申请短期 preview token，返回可 iframe 加载的完整 URL */
export async function mintDraftPreviewUrl(
  gameId: string,
  version: number | string,
  accessToken: string,
): Promise<string> {
  const ver = typeof version === 'number' ? version : Number.parseInt(String(version), 10)
  const { preview_url } = await gamesApi.createPreviewToken(gameId, ver, accessToken)
  const base = resolveHostingUrl(preview_url)
  return ARTIFACT_VER ? `${base}${base.includes('?') ? '&' : '?'}v=${ARTIFACT_VER}` : base
}

/** 将 WS/API 返回的相对 preview_url 解析为可加载地址 */
export function resolveHostingUrl(url: string): string {
  if (/^https?:\/\//i.test(url) || url.startsWith('blob:')) {
    return url
  }
  if (url.startsWith('/')) return joinUrl(env.hostingBaseUrl, url)
  return url
}

export function wsRunUrl(runId: string, accessToken: string, after = 0): string {
  const base = env.wsBaseUrl.replace(/\/$/, '')
  const params = new URLSearchParams({ token: accessToken })
  if (after > 0) params.set('after', String(after))
  return `${base}/ws/runs/${encodeURIComponent(runId)}?${params.toString()}`
}

/** 草稿托管需 Bearer；iframe 无法带头，改为 fetch → blob URL */
export async function fetchDraftHtml(
  gameId: string,
  version: number | string,
  accessToken: string,
): Promise<string> {
  const url = draftArtifactUrl(gameId, version)
  let token = accessToken
  let res = await fetch(url, {
    headers: { Authorization: `Bearer ${token}`, Accept: 'text/html' },
  })

  // access token 只有短 TTL；草稿 iframe 通过 fetch 加载时也必须走同一套
  // refresh 机制，否则页面打开超过 15 分钟后会稳定得到 401。最多刷新一次，
  // 避免失效 refresh token 导致请求循环。
  if (res.status === 401) {
    const state = useAuthStore.getState()
    if (state.access_token === accessToken && state.user && state.refresh_token) {
      try {
        const refreshed = await authApi.refresh(state.refresh_token)
        state.setSession({
          user: state.user,
          access_token: refreshed.access_token,
          refresh_token: refreshed.refresh_token,
        })
        token = refreshed.access_token
        res = await fetch(url, {
          headers: { Authorization: `Bearer ${token}`, Accept: 'text/html' },
        })
      } catch {
        // 保留原始 401，交由上层显示可重试的加载错误。
      }
    }
  }
  if (!res.ok) {
    if (res.status === 401) {
      throw new Error('登录状态已过期，请刷新页面后重试')
    }
    throw new Error(`草稿加载失败 (${res.status})`)
  }
  return res.text()
}

export async function fetchDraftBlobUrl(
  gameId: string,
  version: number | string,
  accessToken: string,
): Promise<string> {
  const html = await fetchDraftHtml(gameId, version, accessToken)
  return URL.createObjectURL(new Blob([html], { type: 'text/html' }))
}
