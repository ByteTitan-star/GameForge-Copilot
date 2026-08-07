import type { WsEnvelope } from '@/api/ws-types'
import { wsRunUrl } from '@/lib/hosting'

export type RunWsHandle = {
  close: () => void
}

export function parseWsEnvelope(raw: string): WsEnvelope | null {
  try {
    const data = JSON.parse(raw) as WsEnvelope
    if (!data || typeof data !== 'object' || typeof data.type !== 'string') return null
    return data
  } catch {
    console.warn('[ws] invalid envelope', raw.slice(0, 120))
    return null
  }
}

type ConnectOptions = {
  runId: string
  accessToken: string
  onEvent: (ev: WsEnvelope) => void
  onError?: (err: Event) => void
  onClose?: (ev: CloseEvent) => void
  /** 断线自动重连次数，默认 3；access 过期（4401）不重连 */
  maxRetries?: number
}

export function connectRunWs(options: ConnectOptions): RunWsHandle {
  const maxRetries = options.maxRetries ?? 3
  let retries = 0
  let closed = false
  let socket: WebSocket | null = null
  let retryTimer: number | null = null

  function open() {
    if (closed) return
    const url = wsRunUrl(options.runId, options.accessToken)
    socket = new WebSocket(url)

    socket.onmessage = (msg) => {
      const ev = parseWsEnvelope(String(msg.data))
      if (ev) options.onEvent(ev)
    }
    socket.onerror = (err) => options.onError?.(err)
    socket.onclose = (ev) => {
      options.onClose?.(ev)
      if (closed) return
      // 4401 鉴权失败 / 4403 无权限：不再重试
      if (ev.code === 4401 || ev.code === 4403) return
      if (retries >= maxRetries) return
      retries += 1
      retryTimer = window.setTimeout(open, Math.min(1000 * retries, 4000))
    }
  }

  open()

  return {
    close: () => {
      closed = true
      if (retryTimer != null) window.clearTimeout(retryTimer)
      socket?.close()
      socket = null
    },
  }
}
