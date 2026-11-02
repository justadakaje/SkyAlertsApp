# web/

The public Sky Alerts site (Next.js 16, App Router), served at **https://sky.henseler.app**. It reads from Postgres as `skyalerts_ro` and never calls ALeRCE on page load.

| Route | What it shows |
|---|---|
| `/` | Latest events, filterable by class, survey and time window; "most notable" or newest first; artifacts hidden by default |
| `/objects/[survey]/[oid]` | One object: class and plain-English blurb, key facts, light curve, classifier probabilities, sky position, ALeRCE link |
| `/stats` | Totals, new objects per day (stacked by class group), per-class counts by week |
| `/trends` | 90-day daily small multiples by class group, 12-week 100%-stacked class mix, week-over-week comparison |
| `/about` | Plain-English guide to Sky Alerts, how to read light curves and sky maps, class groups, and data credits |
| `/skyalerts-explainer.html` | Static interactive architecture and pipeline explainer ("How It Works") |
| `/admin` | Owner only (GitHub sign-in): ingest health, runs and their errors, manual re-run, weekly digest preview/send, audit log, config status |
| `/admin/digest/podcast` | Owner only: downloads this week's podcast outline as `sky-this-week-<week_end>.md` |

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
| `ADMIN_DATABASE_URL` | Vercel (Production) | `skyalerts_web_admin` connection string (`db/migrations/0004`) |
| `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` | Vercel (Production) | GitHub OAuth App. Callback URL `https://sky.henseler.app/api/auth/github/callback`; local dev needs its own OAuth App with a `http://localhost:3000/...` callback |
| `ADMIN_SESSION_SECRET` | Vercel (Production) | Random, at least 32 characters (`openssl rand -base64 48`). Rotating it signs everyone out |
| `ADMIN_GITHUB_IDS` | Vercel (Production) | `16056018`. Numeric GitHub user ids, comma-separated; never usernames |
| `MANUAL_TRIGGER_URL` | Vercel (Production) | `https://<skyalerts-ingest domain>/api/manual/ingest` |
| `MANUAL_TRIGGER_SECRET` | Vercel (Production, both projects) | Random, at least 32 characters; the same value in `skyalerts-ingest` |
| `MANUAL_TRIGGER_BYPASS` | Vercel (Production), optional | The ingest project's "Protection Bypass for Automation" secret. Needed while `skyalerts-ingest` keeps Vercel Authentication on its `*.vercel.app` URLs; sent as `x-vercel-protection-bypass` |
| `DIGEST_URL` | Vercel (Production) | Base URL of the digest service (`https://skyalerts-digest.vercel.app`) |
| `DIGEST_TRIGGER_SECRET` | Vercel (Production, both projects) | Random, at least 32 characters; shared with `skyalerts-digest` for `/api/preview/digest` and `/api/manual/digest` |

`DATABASE_URL` is read-only with a 10 s statement timeout (`db/migrations/0002`). Admin is disabled (fail closed) unless the GitHub, session and allowlist variables are all set. Preview deployments should not get the admin variables.

## Design notes

- **Security:** per-request nonce CSP in `proxy.ts`; static headers in `next.config.ts`; every SQL value is a bind parameter (`lib/queries.ts`); survey/oid/class inputs are allowlisted or pattern-checked (`lib/filters.ts`) before they reach the database.
- **Caching:** every page renders per request (the nonce requires it), but query results are cached for 10 minutes (`lib/data.ts`).
- **Admin:** signed `__Host-` session cookie, CSRF token on every form, allowlist re-checked per request, append-only audit log. See `docs/decisions.md` #24–27.
- **Charts:** server-rendered SVG with native hover titles and a data table under each chart. Colours come from a palette checked for colour-vision deficiency. See `docs/decisions.md` #19–23.
