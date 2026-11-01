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

## Pending / OWNER

- **Ingest scheduler (SPEC asks for a recommendation):** leaning **GitHub Actions cron** over a Vercel Python function — no 60–300 s function duration ceiling, free minutes on a private repo are sufficient for a few short runs/day, logs retained per run, and it keeps the ALeRCE-facing write role off the Vercel runtime. Trade-off: Actions cron can be delayed under load (fine at "every few hours"). Final call at Phase 1 kickoff.
- **GitHub user ID for /admin allowlist:** `16056018` (`justadakaje`). Confirm.
