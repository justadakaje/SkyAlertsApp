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
26. **Manual re-run: the web app POSTs to the ingest project's `/api/manual/ingest`** with `MANUAL_TRIGGER_SECRET`, which is distinct from `CRON_SECRET` so the web project never holds the cron secret. The audit row is written *before* the call, and if that fails nothing is triggered. The call runs in `after()` within a 300 s `maxDuration`. The ingest lease prevents overlapping runs, and the button is disabled while a run is active. The ingest project keeps Vercel Authentication on its `*.vercel.app` URLs, so the call also sends that project's "Protection Bypass for Automation" secret (`MANUAL_TRIGGER_BYPASS`) as `x-vercel-protection-bypass`. The ingest endpoint stays doubly guarded, and nothing about it becomes public.
27. **Sign-in monitoring:** each sign-in writes a structured log line (`event: admin_sign_in`) for a Vercel log alert, and denied sign-ins are audited with the GitHub id that tried. The digest and settings pages are placeholders until Phase 3, when there is something to configure.

## 2026-11-01 — Phase 2 (ingest catch-up window)

28. **2026-11-01 · The catch-up window is per source and in data time. Both full alert streams are samples, and tier-1 transient classes are paged completely ·** This fixes the window that #17 left stuck: production run 1 and both local runs ended `partial` with "page cap hit: ['lsst:default']".
    - **Measured volume** (2026-11-01, ~25 read-only probes, see `docs/alerce-notes.md`):
      - The unfiltered LSST list holds 25,000 rows within the newest 5 h of one night. A full night is roughly **400–600 pages** of 100, and about half the rows repeat an object once per classifier version.
      - The unfiltered ZTF lists hold 100 rows per ~2 min of data.
      - At ≤1 req/s inside the 240 s budget, with ~90 s kept for enrichment (#18), a run can page about 140 pages. So **no page cap or floor makes either unfiltered stream complete**.
      - Filtered by classifier + class, the tier-1 transient classes are small. LSST SN (`stamp_classifier_rubin_beta_20260421`) is 4–12 pages a night. Each ZTF class (stamp SN; lc SNIa/SNIbc/SNII/SLSN/CV/Nova) is 1–2 pages a day.
    - **The old floor also hid a silent gap.** ZTF's newest data is ~3 days old, so `now − 2 d` sat above every ZTF row. Each ZTF source stopped after one page and reported `success` while taking only 100 rows a day. More generally, whenever ALeRCE stalled and then caught up, a wall-clock floor skipped the backlog without reporting it.
    - **Options weighed:**
      1. *Data-time floor, shorter lookback.* Adopted. It closes that blind spot. On its own it doesn't help, because one new LSST night is still ~500 pages.
      2. *Bigger or per-source cap.* Adopted as per-source caps. Raising the unfiltered LSST cap to 120 pages would still cover only ~5 h of one night.
      3. *Gap-aware status.* Adopted as the status rule: hitting the cap matters only if the oldest row reached is still newer than the floor.

      1 and 3 are the same mechanism. **Recommendation: that mechanism, plus per-source caps, plus splitting each stream into a sample and complete tier-1 class sources.** Tier-1 matches `TIER1_CLASSES`, which enrichment already prioritises.
    - **Sources:**
      - `lsst:default`: sample, 20 pages.
      - LSST SN: complete, cap 40.
      - ZTF `stamp_classifier` and `lc_classifier` unfiltered: sample, 1 page each. That's what they effectively got before.
      - ZTF stamp SN and lc SNIa/SNIbc/SNII/SLSN/CV/Nova: complete, cap 10 each.
    - **Rules:**
      - Each source's watermark is the newest `lastmjd` it saw in the last finished `success`/`partial` run that advanced it. It's stored per run in `ingest_runs.coverage` (migration 0005).
      - Floor = watermark − 1 d overlap, which re-covers the previous nightly batch for late arrivals. With no watermark yet, floor = newest row − 1.2 d (about one night). Either way the floor is bounded to 7 d.
      - A **complete** source must page below its floor. If it hits its cap first, the run is `partial`, and the error records `gap_mjd: [floor, oldest reached]`.
      - A **sample** source is truncated by design and never affects status.
    - **Change to #17:**
      - A source's window advances when *its own* coverage reached the floor, even if another source failed.
      - It also advances after a recorded page-cap gap. Holding it back is what wedged production: each later run needs even more pages, so it can never catch up.
      - It does not advance after a budget hit, a source error, a crash, or an abandoned lease. Those are transient, so the next run re-covers the range.
    - **Guards:**
      - A row dated more than 1 h past the wall clock can't move a watermark. One bad `lastmjd` would otherwise lift the floor above all real data.
      - LSST SN is `partial` if its newest row trails the survey's newest by more than 2 d. A renamed (dated) classifier would otherwise leave a frozen list that still "completes" daily. ZTF classifier names aren't dated, and the sparse lc classes would trip the check falsely.
    - **Verified live** (2026-11-01, branch code against real ALeRCE, writing into a throwaway local Postgres): two consecutive runs ended **`success`**: 122 requests in 137 s, then 113 requests in 125 s, each with 40 enrichments. Run 2's floors came from run 1's watermarks (LSST SN 8 → 5 pages).
    - **Budget, a day with a new night:** ~22 sample + 8–25 LSST SN + ~8–15 ZTF class requests, plus ≤80 for enrichment. That's ≤140 requests, about 150–190 s. The 240 s budget still cuts a bad day: the list phase becomes `partial`, and an enrichment cut leaves status unchanged (#18).
    - **Trade-offs:**
      - Non-transient classes (AGN, VS, bogus, asteroid, and ZTF periodic types) are only a newest-first sample. That was already true in practice, but it was never stated.
      - Objects labelled SN only by the older LSST `stamp_classifier_rubin_beta` fall outside the complete source.
      - Recorded gaps aren't backfilled automatically. That needs `lastmjd` range paging (follow-up).
      - Offset paging over large `lastmjd` tie groups can still reorder rows between pages. A Rubin visit puts hundreds of rows on one timestamp. This risk predates this change.
    - **Reversible:** sources, caps and overlap are constants in `ingest/skyalerts_ingest/ingest.py`, and the `coverage` column is additive. **OWNER:** sign off on complete coverage meaning tier-1 transient classes.

## 2026-11-02 — Hardening

29. **2026-11-02 · Vercel Firewall on `skyalerts-web`: rate limit and challenge on `/api/auth/`; Bot Protection log-only site-wide ·** This covers the SPEC §Security firewall item.
    - **Rules**, added and published by OWNER in the dashboard:
      1. *Rate limit admin sign-in:* path starts with `/api/auth/`; fixed window, 60 s, 10 requests per IP, then deny (429). One sign-in uses 2–4 requests (start, GitHub's callback, and challenge reloads).
      2. *Challenge admin sign-in:* same path, Vercel Security Checkpoint. OWNER confirmed GitHub sign-in still works through it.
      3. *Bot Protection* (managed ruleset): **log**.
    - **Why this scope:** `/api/auth/` is every API route the web app has (`github/start`, `github/callback`). Admin mutations are server actions on `/admin`, behind the session and CSRF checks (#24). The ingest and digest endpoints live in their own projects behind bearer secrets (#26).
    - **Deviation from SPEC ("bot protection on public pages"):** challenge mode would block link previews. iMessage fetches a preview from the sender's own device with a crawler user agent, which Vercel's verified-bot check can't confirm. Public pages are read-only, cached for 10 minutes, and query as `skyalerts_ro`, so a scraper costs function time, not data. Log mode shows bot traffic without breaking sharing. Switch to challenge if the logs show abuse.
    - **Verified live** (2026-11-02):
      - `/api/auth/github/start` answers with the Security Checkpoint (`x-vercel-mitigated: challenge`).
      - `/`, `/trends`, `/about` and `/opengraph-image` return 200, including for a `facebookexternalhit`/`Twitterbot` user agent.
      - The rate limit wasn't tripped on purpose, because it would lock the owner's own IP out for a minute.
    - **Operational note:** the Vercel API (and so the connector) returns 404 "Seawall Config not found" for this project's firewall config, even after publishing. Firewall changes go through the dashboard.
    - **Reversible:** dashboard toggles. Widen both rules to `/api/` if the web app gains a non-auth API route. **OWNER:** sign off on log-only bot protection.

## Pending / OWNER

- ~~Ingest scheduler~~ → decided, see #13.
- ~~GitHub user ID for /admin allowlist~~ → `16056018` (`justadakaje`), confirmed by OWNER 2026-11-01.
- **Complete coverage = tier-1 transient classes; the rest is a newest-first sample** (#28). Confirm, or name more classes (each costs pages per night).
- **Bot Protection log-only on public pages** (#29). Confirm, or switch to challenge (which costs link previews).
- **Security gate gaps** (`docs/security-checklist.md`, verified 2026-11-02):
  - In the `main` ruleset, require linear history, conversation resolution, and the `dependency-review` and `analyze (javascript-typescript)` checks.
  - Confirm the Resend key is "Sending access" for `sky.henseler.app` only.
  - Wire alerts for ingest failure, error spikes and `admin_sign_in`.
