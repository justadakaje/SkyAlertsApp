# Decisions Log

Format: date · decision · why · reversibility. Newest at the bottom. Items marked **OWNER** need sign-off before they're final.

## 2026-11-01 — Phase 0

1. **License: MIT.** Repo is private; MIT keeps the option to open-source with no relicensing. Trivially reversible while private.
2. **Python tooling: `uv` + `pyproject.toml` + committed `uv.lock`.** Satisfies "lockfiles committed, versions pinned"; Dependabot supports the `uv` ecosystem natively; fast CI installs. Reversible (can export to `requirements.txt` with hashes).
3. **Talk to ALeRCE REST directly with `httpx`, not the official `alerce` client.** The `alerce` 2.3.1 client pulls pandas, astropy, matplotlib and ipython (heavy, large CVE surface, bad fit for serverless), sets no request timeout, and has no retry/backoff. Our thin client adds timeouts, a client-side rate limiter, and retry with exponential backoff + `Retry-After` handling. We mirror the client's endpoint map (see `docs/alerce-notes.md`) so behaviour stays comparable. Reversible: the client is one module behind a small interface.
4. **Dev dependencies kept to `pytest` + `ruff`.** HTTP is mocked with `httpx.MockTransport` (built in), so no `respx`/`responses`.
5. **Exploration runs in GitHub Actions (manual dispatch), not from the agent workspace.** The orchestration workspace's egress allowlist blocks `*.alerce.online`; Actions runners have open egress. The workflow writes the summary to the job summary and uploads JSON samples as an artifact, which become the "real sample data" fixtures required by SPEC §Conventions.
6. **Test fixtures are schema-derived until the first real Actions run.** Fixtures under `ingest/tests/fixtures/` are built from the documented ALeRCE response models and are labelled `synthetic`. Replace them with captured samples from the first Explore run (tracked as a Phase 0 exit item).
7. **Lane/branch model.** Branches are `<lane>/<topic>` (e.g. `devops/phase0-ci`, `data/phase0-explore`). One PR per lane per topic; orchestrator merges with squash.
8. **Self-imposed ALeRCE rate limit: ≤1 request/second, serial (no concurrency).** ALeRCE publishes no rate limit. Being a polite consumer of a free academic service matters more than throughput; ingest volume (a few hundred objects every few hours) fits comfortably. Tunable via env var.

9. **Repo is public (OWNER-approved 2026-11-01), not private.** On a user-owned private repo GitHub offers no secret scanning/push protection, CodeQL requires a paid org plan, and branch protection requires Pro. Public gives every SPEC §Security control natively for free. Nothing sensitive is in the repo by policy (all secrets in Vercel/GitHub encrypted env vars); the admin allowlist ID is public information. Reversible (can be made private later, losing those controls).

10. **Repo is `justadakaje/SkyAlertsApp`** (OWNER-created). SPEC says `skyalerts`; SPEC left unchanged as written, this entry is the override. An older private `justadakaje/skyalerts` also exists. It is unused and can be archived.
11. **Digest sends from `sky.henseler.app`, not a subdomain of henseler.email (OWNER decision, 2026-11-01).** This keeps Proton Mail's henseler.email zone completely untouched. Resend domain is `sky.henseler.app`, region `us-east-1` (permanent), sending only, open/click tracking off. DNS lives at Porkbun: `resend._domainkey.sky` TXT (DKIM), `send.sky` MX + TXT (SPF/bounce), `rsend.sky` CNAME, `_dmarc.sky` TXT `v=DMARC1; p=none;`. Nothing sits at the `sky` apex, so Phase 2 can still add `sky` CNAME → Vercel. Note: a `*.henseler.app` wildcard CNAME → pixie.porkbun.com exists. Because `send.sky` now exists, `sky.henseler.app` is an empty non-terminal and no longer matches that wildcard. It won't resolve until Phase 2 adds its CNAME. Tighten DMARC to `p=quarantine` after 2–4 weeks of clean reports.
12. **Repo settings are applied by the owner in the UI.** The agent's GitHub proxy blocks settings writes (security & analysis, branch protection/rulesets). The agent opens PRs and reads CI. The owner toggles settings per `docs/security-checklist.md`.

13. **Ingest runs as a Vercel Python function triggered by Vercel Cron (OWNER decision 2026-11-01, overriding the GitHub Actions recommendation).** Constraints on the Hobby plan (confirmed in Vercel docs 2026-11-01):
    - **Cron runs at most once a day**, with ±59 min timing. More frequent schedules fail at deploy. Pro ($20/mo) allows per-minute.
    - **Functions get 300 s max duration** and 2 GB memory.

    Design consequences:
    - **Daily schedule.** Acceptable: the live run showed Rubin data arrives ~23 h after observation as a nightly batch.
    - **Under ~150 requests per run.** Use LSST list rows (they already carry class and probability) and ZTF per-classifier list queries. No per-object probability fan-out in the cron path.
    - **Separate Vercel project `skyalerts-ingest`** (root `ingest/`). The write-role secret never sits in the public web project's env.
    - **Migrations run from a GitHub Actions workflow** behind a `production` environment that needs owner approval. The admin connection string stays a GitHub secret and never goes to Vercel.
    - **The Neon integration must not auto-inject its owner `DATABASE_URL` into any project.** Each project gets only its own role's connection string.
    - **Manual re-run from /admin (Phase 2)** covers missed or late crons.

    Reversible: the ingest entrypoint is a plain function, so moving it to Actions or Pro later is config-only.

14. **Neon project `skyalerts` created through the Neon connector (OWNER-approved 2026-11-01):** project `billowing-haze-89704982`, AWS us-east-1, Postgres 17, free tier, database `skyalerts`, owner role `skyalerts_admin`. Roles created through the Neon API land in `neon_superuser` (CREATEDB, CREATEROLE, BYPASSRLS), and that membership can't be revoked. So the app roles `skyalerts_ingest` and `skyalerts_ro` are created by SQL in migration 0002 as plain logins. The two API-created roles were deleted with owner approval. Postgres-level defense in depth: per-role `statement_timeout`, and read-only transactions by default for `skyalerts_ro`.

15. **The agent never handles database passwords or other runtime secrets.** Putting app-role passwords through the agent's tool calls was blocked as credential leakage, which is correct. The owner sets role passwords (Neon SQL editor or `psql \\password`) and pastes connection strings and `CRON_SECRET` straight into Vercel and GitHub encrypted settings. The agent manages schema and config only.

16. **Database of record is the Vercel-managed Neon project `neon-skyalerts-pgsqldb` (OWNER decision 2026-11-01).** Project `lively-leaf-84959387`, Postgres 18, database `neondb`, owner `neondb_owner`, us-east-1, connected to no Vercel project, so no auto-injected owner URL. Migrations 0001 and 0002 were applied there through the Neon connector, with checksums matching `migrate.py`. The console-created `skyalerts` project from #14 is superseded and pending deletion with owner approval. CI moved to Postgres 18.
17. **The ingest run lock is a lease row, not a session advisory lock** (QA finding on PR #7). Session locks leak behind Neon's PgBouncer transaction pooling, and also when Vercel kills the function, which would make every later run skip silently. Now: a transaction-scoped `pg_advisory_xact_lock` guards check-and-insert of a `running` row, and rows older than 10 min are closed as failed. Only `success` runs advance the catch-up window, and hitting the page cap counts as `partial`.
18. **2026-11-01 · Bounded per-object enrichment runs inside the daily ingest cron ·** Phase 2 object pages need light curves (`detections`) and full classifier breakdowns (`classifications`). Enriching up to 40 priority objects (`INGEST_ENRICH_MAX=40`, excluding `bogus`/`asteroid`, tiered with transients first, and skipping objects whose `lastmjd` has not advanced since `enriched_lastmjd`) takes 40 × 2 requests at ≤1 req/s ≈ 80–90 s. Combined with list paging (the first live run used 22 requests in 22 s), the total stays well inside the 240 s time budget. Detections are capped at the 200 newest per object with a slim `raw` key whitelist, and probabilities are capped at `ranking <= 3` per `(classifier_name, classifier_version)` to keep Neon free-tier storage small. Enrichment errors or budget exhaustion do not demote run `status`, preserving the list-phase catch-up window gate (#17) · **Reversible:** `INGEST_ENRICH_MAX` tunes or disables enrichment via env var without code changes.

## 2026-11-01 — Phase 2 (public dashboard)

19. **Web stack: Next.js 16 (App Router) + TypeScript 6, plain CSS, `pg`, no chart library.** Four runtime dependencies: `next`, `react`, `react-dom`, `pg`. Plain CSS instead of Tailwind keeps the dependency list short. `pg` instead of `@neondatabase/serverless` means the same driver runs locally, in CI and on Vercel (Neon's pooled endpoint). Charts are server-rendered SVG, which needs no client JavaScript and so keeps the CSP strict. TypeScript is pinned to 6.x: 7.0 is the native-compiler rewrite released days ago, and Dependabot ignores its major version until we adopt it on purpose. Reversible.
20. **Nonce-based CSP via `proxy.ts`, so every page renders per request; database reads are cached for 10 minutes** (`unstable_cache`, keyed by a 10-minute time bucket). Ingest runs once a day, so cached reads lose nothing and keep the free-tier Neon compute asleep between visits. Static headers (HSTS 2 years with subdomains, nosniff, frame DENY, Referrer-Policy, Permissions-Policy, COOP) live in `next.config.ts`. Reversible: SRI-based CSP (experimental in Next 16) would allow static pages later.
21. **Light curves:** ZTF is plotted in magnitudes, using ALeRCE's corrected apparent magnitude (`magpsf_corr`) when `corrected` is true. Uncorrected negative differences (`isdiffpos = -1`) have no meaningful magnitude and are left off, with a count in the caption. LSST is plotted as difference flux in µJy, where negative values are real measurements. g/r/i overlay on one chart in a palette checked for colour-vision deficiency; any other band set switches to one panel per band, because six hues can't stay distinguishable.
22. **Artifacts (`bogus`, roughly a third of LSST rows) are hidden by default** behind a "Show artifacts" toggle. "Most notable" ordering uses the same tiers as ingest enrichment (#18): explosions and outbursts first, active galaxies last.
23. **ALeRCE explorer link for LSST objects is `alerce.online/object/?oid=<id>&survey=lsst`.** It is the form reported working on the Rubin community forum; ALeRCE hasn't documented one. Re-check if links break.

## 2026-11-01 — Phase 2 (admin)

24. **Admin sign-in is a small GitHub OAuth flow written in-house, not Auth.js.** We have one user and one provider, and the hand-written version is about 150 audited lines with no new dependencies. Details:
    - **OAuth:** web application flow requesting no scopes. The access token is used once to read the numeric user id, then discarded.
    - **Session:** stateless HMAC-SHA256-signed cookie `__Host-skyalerts_admin` (HttpOnly, Secure, SameSite=Lax, 8 h, Web Crypto).
    - **Allowlist:** numeric ids in `ADMIN_GITHUB_IDS`, re-checked on every request, so removing an id takes effect immediately. Rotating `ADMIN_SESSION_SECRET` signs everyone out. Missing or weak config disables admin (fail closed).
    - **OAuth state:** a 10-minute `__Host-` cookie, compared by HMAC.
    - **CSRF:** every admin form carries a token bound to that sign-in, verified in the action, on top of Next's server-action Origin/Host check and SameSite.
    - **Where auth is checked:** the admin layout *and* every page and action call `requireAdmin()`. The proxy is not a guard.

    Reversible: the session API is three functions.
25. **Admin uses its own database role, `skyalerts_web_admin` (migration 0004), via `ADMIN_DATABASE_URL`.** It has SELECT on data tables and `ingest_runs`, and append-only `INSERT (actor_github_id, action, target, details)` on `audit_log`, with no UPDATE or DELETE anywhere. Public pages keep using `skyalerts_ro` through a separate pool, so a public-page bug can't write.
26. **Manual re-run: the web app POSTs to the ingest project's `/api/manual/ingest`** with `MANUAL_TRIGGER_SECRET`, which is distinct from `CRON_SECRET` so the web project never holds the cron secret. The audit row is written *before* the call, and if that fails nothing is triggered. The call runs in `after()` within a 300 s `maxDuration`. The ingest lease prevents overlapping runs, and the button is disabled while a run is active.
27. **Sign-in monitoring:** each sign-in writes a structured log line (`event: admin_sign_in`) for a Vercel log alert, and denied sign-ins are audited with the GitHub id that tried. The digest and settings pages are placeholders until Phase 3, when there is something to configure.

## Pending / OWNER

- ~~Ingest scheduler~~ → decided, see #13.
- ~~GitHub user ID for /admin allowlist~~ → `16056018` (`justadakaje`), confirmed by OWNER 2026-11-01.
