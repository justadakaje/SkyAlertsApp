# web/

The public Sky Alerts site (Next.js 16, App Router), served at **https://sky.henseler.app**. It reads from Postgres as `skyalerts_ro` and never calls ALeRCE on page load.

| Route | What it shows |
|---|---|
| `/` | Latest events, filterable by class, survey and time window; "most notable" or newest first; artifacts hidden by default |
| `/objects/[survey]/[oid]` | One object: class and plain-English blurb, key facts, light curve, classifier probabilities, sky position, ALeRCE link |
| `/stats` | Totals, new objects per day (stacked by class group), per-class counts by week |

`/admin` (GitHub sign-in, owner only) comes in a follow-up PR.

## Run locally

```bash
cd web
npm ci --ignore-scripts
DATABASE_URL=postgresql://skyalerts_ro:<password>@localhost:5432/<db> npm run dev
```

For a local database, start Postgres 18, apply `db/migrations` with `db/migrate.py`, then run the ingest CLI (`ingest/README.md`) to pull a day of real data.

```bash
npm run lint    # eslint + tsc --noEmit
npm test        # vitest (pure logic + query parameter binding)
npm run build
```

## Configuration

| Env var | Where | Value |
|---|---|---|
| `DATABASE_URL` | Vercel (Production; Preview gets its own) | `skyalerts_ro` connection string, Neon **pooled** endpoint, `sslmode=require` |

Nothing else is secret. The role is read-only with a 10 s statement timeout (`db/migrations/0002`).

## Design notes

- **Security:** per-request nonce CSP in `proxy.ts`; static headers in `next.config.ts`; every SQL value is a bind parameter (`lib/queries.ts`); survey/oid/class inputs are allowlisted or pattern-checked (`lib/filters.ts`) before they reach the database.
- **Caching:** every page renders per request (the nonce requires it), but query results are cached for 10 minutes (`lib/data.ts`).
- **Charts:** server-rendered SVG with native hover titles and a data table under each chart. Colours come from a palette checked for colour-vision deficiency. See `docs/decisions.md` #19–23.
