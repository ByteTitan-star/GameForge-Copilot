type ClientLogLevel = 'debug' | 'info' | 'warn' | 'error'

type ClientLogExtra = Record<string, unknown>

function beijingTimestamp(): string {
  const text = new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(new Date())
  return `${text.replace(' ', 'T')}+08:00`
}

function emit(level: ClientLogLevel, message: string, extra?: ClientLogExtra) {
  const payload = {
    ts: beijingTimestamp(),
    level: level.toUpperCase(),
    service: 'frontend',
    message,
    ...extra,
  }
  const line = JSON.stringify(payload)
  const consoleFn =
    level === 'error' ? console.error : level === 'warn' ? console.warn : console.log
  consoleFn(`[${payload.service}]`, message, extra ?? '')
  if (import.meta.env.DEV) {
    fetch('/__client_log', {
      method: 'POST',
      headers: { 'content-type': 'text/plain' },
      body: line,
    }).catch(() => {})
  }
}

export const clientLog = {
  debug: (message: string, extra?: ClientLogExtra) => emit('debug', message, extra),
  info: (message: string, extra?: ClientLogExtra) => emit('info', message, extra),
  warn: (message: string, extra?: ClientLogExtra) => emit('warn', message, extra),
  error: (message: string, extra?: ClientLogExtra) => emit('error', message, extra),
}

export function installClientLogHooks() {
  window.addEventListener('error', (ev) => {
    clientLog.error('window.error', {
      message: ev.message,
      filename: ev.filename,
      lineno: ev.lineno,
      colno: ev.colno,
    })
  })
  window.addEventListener('unhandledrejection', (ev) => {
    const reason = ev.reason
    clientLog.error('unhandledrejection', {
      reason: reason instanceof Error ? reason.message : String(reason),
    })
  })
}
