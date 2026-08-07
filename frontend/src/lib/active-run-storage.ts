const STORAGE_KEY = 'gf_active_run_v1'

export type StoredActiveRun = {
  gameId: string
  runId: string
  updatedAt: string
}

export function saveActiveRun(gameId: string, runId: string): void {
  try {
    const payload: StoredActiveRun = {
      gameId,
      runId,
      updatedAt: new Date().toISOString(),
    }
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
  } catch {
    /* ignore quota / private mode */
  }
}

export function readActiveRun(): StoredActiveRun | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const data = JSON.parse(raw) as StoredActiveRun
    if (!data?.gameId || !data?.runId) return null
    return data
  } catch {
    return null
  }
}

export function clearActiveRun(runId?: string): void {
  try {
    if (runId) {
      const current = readActiveRun()
      if (current?.runId !== runId) return
    }
    sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    /* ignore */
  }
}
