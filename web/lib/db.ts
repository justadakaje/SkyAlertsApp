import 'server-only'

import { Pool } from 'pg'

// One small pool per server instance. In production DATABASE_URL is the
// skyalerts_ro role on Neon's pooled endpoint; the role is read-only with a
// 10 s statement timeout (db/migrations/0002), so the grants are the real guard.
const g = globalThis as unknown as { skyalertsPool?: Pool }

export function getPool(): Pool {
  if (!g.skyalertsPool) {
    const connectionString = process.env.DATABASE_URL
    if (!connectionString) throw new Error('DATABASE_URL is not set')
    const pool = new Pool({
      connectionString,
      max: 3,
      idleTimeoutMillis: 10_000,
      connectionTimeoutMillis: 8_000,
      application_name: 'skyalerts-web',
    })
    // An idle client dropping (e.g. Neon scaling to zero) must not crash the server.
    pool.on('error', (err) => console.error(JSON.stringify({ msg: 'pg pool error', error: err.message })))
    g.skyalertsPool = pool
  }
  return g.skyalertsPool
}
