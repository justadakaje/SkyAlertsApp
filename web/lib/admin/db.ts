import 'server-only'

import { Pool } from 'pg'

// Admin pages use their own role (skyalerts_web_admin, db/migrations/0004): it can
// read data and ingest runs and append to audit_log, nothing else. Kept apart from
// the public read-only pool so a public-page bug can never write.
const g = globalThis as unknown as { skyalertsAdminPool?: Pool }

export function getAdminPool(): Pool {
  if (!g.skyalertsAdminPool) {
    const connectionString = process.env.ADMIN_DATABASE_URL
    if (!connectionString) throw new Error('ADMIN_DATABASE_URL is not set')
    const pool = new Pool({
      connectionString,
      max: 2,
      idleTimeoutMillis: 10_000,
      connectionTimeoutMillis: 8_000,
      application_name: 'skyalerts-admin',
    })
    pool.on('error', (err) => console.error(JSON.stringify({ msg: 'admin pg pool error', error: err.message })))
    g.skyalertsAdminPool = pool
  }
  return g.skyalertsAdminPool
}
