import type { WsEnvelope } from '@/api/ws-types'
import { wsRunUrl } from '@/lib/hosting'
import { clientLog } from '@/lib/client-log'

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
  /** 断线自动重连次数；persistent=true 时忽略上限 */
  maxRetries?: number
  /** 页面存活期间持续重连（刷新后由 HTTP+新 WS 接管） */
  persistent?: boolean
}

export function connectRunWs(options: ConnectOptions): RunWsHandle {
  const persistent = options.persistent ?? false
  const maxRetries = options.maxRetries ?? (persistent ? Number.POSITIVE_INFINITY : 3)
  let retries = 0
  let closed = false
  let socket: WebSocket | null = null
  let retryTimer: number | null = null

  function open() {
    if (closed) return
    const url = wsRunUrl(options.runId, options.accessToken)
    socket = new WebSocket(url)

    socket.onopen = () => {
      retries = 0
    }

    socket.onmessage = (msg) => {
      const ev = parseWsEnvelope(String(msg.data))
      if (ev) options.onEvent(ev)
    }
    socket.onerror = (err) => {
      clientLog.error('ws.error', { runId: options.runId })
      options.onError?.(err)
    }
    socket.onclose = (ev) => {
      if (ev.code !== 1000) {
        clientLog.warn('ws.close', { runId: options.runId, code: ev.code, reason: ev.reason })
      }
      options.onClose?.(ev)
      if (closed) return
      if (ev.code === 4401 || ev.code === 4403) return
      if (!persistent && retries >= maxRetries) return
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
