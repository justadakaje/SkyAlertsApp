# db/

Schema migrations for the Neon Postgres database: Vercel-managed Neon project `neon-skyalerts-pgsqldb`, database `neondb`, owner `neondb_owner`, AWS us-east-1, Postgres 18.

- `migrations/NNNN_name.sql`: applied in order, once each, one transaction per file, checksummed. Never edit an applied migration; add a new one.
- `migrate.py`: the runner. `DATABASE_URL=<admin dsn> uv run python migrate.py [--dry-run]`
- Migration files must not contain BEGIN/COMMIT/ROLLBACK (the runner wraps each file in a transaction). `DATABASE_URL` must be the **direct** Neon endpoint, not `-pooler` (advisory locks need a session).
- Production runs go through the **DB migrate** workflow (manual, `production` environment, owner approval, `DATABASE_URL_ADMIN` secret).
- `tests/`: integration tests against real Postgres (`TEST_DATABASE_URL` = superuser DSN on a throwaway server). CI runs them on `postgres:18`.

## Roles

| Role | Used by | Rights |
|---|---|---|
| `neondb_owner` | migrations | owner (created by the Vercel Neon integration) |
| `skyalerts_ingest` | ingest job (Vercel `skyalerts-ingest`) | SELECT/INSERT/UPDATE on data tables + `ingest_runs`; no DELETE; 60 s statement timeout |
| `skyalerts_ro` | public website | SELECT only; read-only transactions; 10 s statement timeout |

App roles are created by SQL (`0002`), **not** the Neon console/API. Neon makes console- and API-created roles members of `neon_superuser`. Passwords are set out-of-band (prefer `\password <role>` in psql, which hashes client-side) and stored only in encrypted env vars. `default_transaction_read_only` and timeouts are guard rails. The grants are the actual control.
