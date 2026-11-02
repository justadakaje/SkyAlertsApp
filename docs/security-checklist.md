# Security Release Gate

Derived from SPEC §Security. A phase ships to production only when every applicable box is checked. QA agent runs the PR section on every PR touching auth, admin, API routes or dependencies.

**Last verified 2026-11-02** against the live site, GitHub's API, Vercel, Neon (`pg_roles`) and Resend, not from memory. An unchecked box with a **Gap** note is open work; the open items are also listed under "Pending / OWNER" in `decisions.md`.

## Repo & process (Phase 0)
- [x] Repo public; Dependabot alerts + security updates on
- [x] Secret scanning + push protection on
- [x] Private vulnerability reporting on
- [x] CodeQL (security-extended) on PRs, `main`, weekly (python, javascript-typescript, actions)
- [ ] `pip-audit` (+ `npm audit --audit-level=high` from Phase 2) and dependency review (fail ≥ high) block merges
  - `pip-audit` (ingest, db, digest) and `npm audit` run inside the lane jobs behind `ci-ok`, so they block.
  - **Gap:** `dependency-review` runs on every PR but isn't a required check, so a failure doesn't block a merge.
- [ ] Branch protection on `main`: PR required, `ci-ok` + CodeQL required, linear history, no force push, no deletion, conversation resolution
  - In place (ruleset "main ruleset", no bypass actors): PR required, `ci-ok` + `analyze (python)` + `analyze (actions)` required and up to date, CodeQL code-scanning gate (high+), no force push, no deletion.
  - **Gap:** linear history isn't required (merge commits are allowed), conversation resolution isn't required, and `analyze (javascript-typescript)` isn't a required check.
- [x] Actions pinned to commit SHAs; default `GITHUB_TOKEN` read-only; `persist-credentials: false`
- [x] Lockfiles committed (`ingest/uv.lock`, `db/uv.lock`, `digest/uv.lock`, `web/package-lock.json`)

## Data & secrets (Phase 1+)
- [x] All secrets in Vercel/GitHub encrypted env vars, separate preview vs production
  - Every runtime secret is a Production-only *Sensitive* variable in the project that uses it (web, ingest, digest). Previews get none.
- [x] DB roles: `skyalerts_ro` (public web, digest), `skyalerts_web_admin` (admin, #25), `skyalerts_ingest` (write), migrations as `neondb_owner` only
  - Replaces the planned `skyalerts_admin`: migrations run as `neondb_owner` (see `db/README.md`), and no app holds that role.
  - No app role is superuser, can create roles or databases, bypasses RLS, or can `CREATE` in `public`. `skyalerts_ingest` has no `DELETE`. `skyalerts_web_admin` can only `INSERT` the four audit columns.
- [x] All SQL parameterized; ALeRCE payloads validated + treated as untrusted
  - No SQL built by string formatting in Python or by template interpolation in web `query()` calls; CodeQL security-extended covers SQL injection.
- [x] Ingest logs contain no connection strings or tokens

## Hosting & network (Phase 2+)
- [x] HTTPS + HSTS (`max-age=63072000; includeSubDomains`)
- [x] CSP, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `Permissions-Policy`, `frame-ancestors 'none'`
  - Per-request nonce CSP with `strict-dynamic`, `object-src 'none'`, `base-uri 'self'` and `form-action 'self'`, plus `X-Frame-Options: DENY` and COOP `same-origin`.
- [x] Vercel Firewall on; rate limit on `/api/*`; bot protection on public pages
  - Rate limit (10/min per IP) and challenge on `/api/auth/`, which is every API route the web app has.
  - Bot Protection is on in **log** mode for public pages, to keep link previews working (#29, OWNER to confirm).
- [x] Preview deployments behind Deployment Protection
  - All three projects use Vercel Authentication on everything except custom domains.
  - Each production `<project>.vercel.app` alias is public by Vercel's design; every endpoint on the ingest and digest aliases requires its own bearer secret.

## Admin & auth (Phase 2+)
- [x] GitHub OAuth; allowlist by numeric user ID (`16056018`), not username
- [x] Server-side auth check on every admin page + route (middleware is not the only guard)
  - Every page, layout and route under `app/admin` except the login page calls `requireAdmin()`/`currentAdmin()`, and all three server actions call `requireAdminForm()`.
- [x] Session cookies `Secure; HttpOnly; SameSite=Lax|Strict`, short TTL (`__Host-` prefix, Lax, 8 h)
- [x] CSRF protection on admin mutations (session-bound token, checked by `requireAdminForm()`)
- [x] Audit log table records every admin action
  - Sign-in, denied sign-in, sign-out, `ingest.rerun` and `digest.send`. The audit row is written before the side effect.
- [ ] Alerts on admin sign-in
  - **Gap:** each sign-in writes an `admin_sign_in` log line (#27), but no alert is wired to it yet.

## Email (Phase 3)
- [ ] Resend key scoped to sending only, sending subdomain only
  - One key (`skyalerts-digest`); the domain `sky.henseler.app` is verified with sending enabled.
  - **Gap:** the Resend connector doesn't show a key's permission, so OWNER confirms "Sending access" limited to `sky.henseler.app`.
- [x] SPF/DKIM/DMARC pass for the subdomain; **root MX on henseler.email unchanged (Proton Mail)**
  - SPF on `send.sky.henseler.app` (`include:amazonses.com`), DKIM at `resend._domainkey.sky.henseler.app`, DMARC at `_dmarc.sky.henseler.app`. `henseler.email` MX still points to Proton.
  - DMARC is `p=none` (monitoring only); move to `p=quarantine` once a few weeks of reports look clean.

## Monitoring
- [ ] Alerts on ingest failure, error spikes, admin sign-in
  - **Gap:** none are wired. `/admin` shows ingest health, but nothing pushes an alert.
