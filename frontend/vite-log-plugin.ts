import fs from 'node:fs'
import path from 'node:path'
import type { Plugin } from 'vite'

/** Dev-only: append browser logs to repo-root ``logs/frontend.log``. */
export function devLogFilePlugin(repoRoot: string): Plugin {
  const logDir = path.join(repoRoot, 'logs')
  const logFile = path.join(logDir, 'frontend.log')

  const append = (line: string) => {
    fs.mkdirSync(logDir, { recursive: true })
    fs.appendFileSync(logFile, `${line}\n`, 'utf8')
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
