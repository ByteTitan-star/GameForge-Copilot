import fs from 'node:fs'
import path from 'node:path'
import type { Plugin } from 'vite'

const BEIJING_TZ = 'Asia/Shanghai'

/** Daily folder ``YY-MM-DD`` in Beijing time, e.g. ``26-08-07``. */
export function beijingDateKey(when = new Date()): string {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('en-GB', {
      timeZone: BEIJING_TZ,
      year: '2-digit',
      month: '2-digit',
      day: '2-digit',
    })
      .formatToParts(when)
      .map((p) => [p.type, p.value]),
  )
  return `${parts.year}-${parts.month}-${parts.day}`
}

/** ISO-like timestamp with ``+08:00`` offset (Beijing). */
export function beijingTimestamp(when = new Date()): string {
  const text = new Intl.DateTimeFormat('sv-SE', {
    timeZone: BEIJING_TZ,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(when)
  return `${text.replace(' ', 'T')}+08:00`
}

/** Dev-only: append browser logs to ``logs/YY-MM-DD/frontend.log``. */
export function devLogFilePlugin(repoRoot: string): Plugin {
  const logRoot = path.join(repoRoot, 'logs')

  const append = (line: string) => {
    const dayDir = path.join(logRoot, beijingDateKey())
    fs.mkdirSync(dayDir, { recursive: true })
    fs.appendFileSync(path.join(dayDir, 'frontend.log'), `${line}\n`, 'utf8')
  }

  return {
    name: 'gameforge-dev-log-file',
    configureServer(server) {
      server.middlewares.use('/__client_log', (req, res, next) => {
        if (req.method !== 'POST') {
          next()
          return
        }
        let body = ''
        req.on('data', (chunk) => {
          body += chunk
        })
        req.on('end', () => {
          if (body.trim()) {
            append(body.trim())
          }
          res.statusCode = 204
          res.end()
        })
        req.on('error', () => {
          res.statusCode = 500
          res.end()
        })
      })
    },
  }
}
