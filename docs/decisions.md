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

## Pending / OWNER

- ~~Ingest scheduler~~ → decided, see #13.
- **GitHub user ID for /admin allowlist:** `16056018` (`justadakaje`). Confirm.
