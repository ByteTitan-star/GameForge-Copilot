import { env } from './env'

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

export function draftArtifactUrl(gameId: string, version: number | string): string {
  const q = ARTIFACT_VER ? `?v=${ARTIFACT_VER}` : ''
  return joinUrl(
    env.hostingBaseUrl,
    `/draft/${encodeURIComponent(gameId)}/${encodeURIComponent(String(version))}${q}`,
  )
}

/** 将 WS/API 返回的相对 preview_url 解析为可加载地址 */
export function resolveHostingUrl(url: string): string {
  if (/^https?:\/\//i.test(url) || url.startsWith('blob:')) {
    return url
  }
  if (url.startsWith('/')) return joinUrl(env.hostingBaseUrl, url)
  return url
}

export function wsRunUrl(runId: string, accessToken: string): string {
  const base = env.wsBaseUrl.replace(/\/$/, '')
  return `${base}/ws/runs/${encodeURIComponent(runId)}?token=${encodeURIComponent(accessToken)}`
}

/** 草稿托管需 Bearer；iframe 无法带头，改为 fetch → blob URL */
export async function fetchDraftBlobUrl(
  gameId: string,
  version: number | string,
  accessToken: string,
): Promise<string> {
  const url = draftArtifactUrl(gameId, version)
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${accessToken}`, Accept: 'text/html' },
  })
  if (!res.ok) {
    throw new Error(`草稿加载失败 (${res.status})`)
  }
  const html = await res.text()
  return URL.createObjectURL(new Blob([html], { type: 'text/html' }))
}
