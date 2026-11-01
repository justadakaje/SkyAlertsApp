# Security Release Gate

Derived from SPEC §Security. A phase ships to production only when every applicable box is checked. QA agent runs the PR section on every PR touching auth, admin, API routes or dependencies.

## Repo & process (Phase 0)
- [ ] Repo public; Dependabot alerts + security updates on
- [ ] Secret scanning + push protection on
- [ ] Private vulnerability reporting on
- [ ] CodeQL (security-extended) on PRs, `main`, weekly
- [ ] `pip-audit` (+ `npm audit --audit-level=high` from Phase 2) and dependency review (fail ≥ high) block merges
- [ ] Branch protection on `main`: PR required, `ci-ok` + CodeQL required, linear history, no force push, no deletion, conversation resolution
- [ ] Actions pinned to commit SHAs; default `GITHUB_TOKEN` read-only; `persist-credentials: false`
- [ ] Lockfiles committed (`ingest/uv.lock`, later `web/package-lock.json`)

## Data & secrets (Phase 1+)
- [ ] All secrets in Vercel/GitHub encrypted env vars, separate preview vs production
- [ ] DB roles: `skyalerts_ro` (web), `skyalerts_ingest` (write), `skyalerts_admin` (migrations only)
- [ ] All SQL parameterized; ALeRCE payloads validated + treated as untrusted
- [ ] Ingest logs contain no connection strings or tokens

## Hosting & network (Phase 2+)
- [ ] HTTPS + HSTS (`max-age≥31536000; includeSubDomains`)
- [ ] CSP, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `Permissions-Policy`, `frame-ancestors 'none'`
- [ ] Vercel Firewall on; rate limit on `/api/*`; bot protection on public pages
- [ ] Preview deployments behind Deployment Protection

## Admin & auth (Phase 2+)
- [ ] GitHub OAuth; allowlist by numeric user ID (`16056018`), not username
- [ ] Server-side auth check on every admin page + route (middleware is not the only guard)
- [ ] Session cookies `Secure; HttpOnly; SameSite=Lax|Strict`, short TTL
- [ ] CSRF protection on admin mutations
- [ ] Audit log table records every admin action
- [ ] Alerts on admin sign-in

## Email (Phase 3)
- [ ] Resend key scoped to sending only, sending subdomain only
- [ ] SPF/DKIM/DMARC pass for the subdomain; **root MX on henseler.email unchanged (Proton Mail)**

## Monitoring
- [ ] Alerts on ingest failure, error spikes, admin sign-in
