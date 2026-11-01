## What / why

<!-- One or two sentences. Link the SPEC phase and lane. -->

**Lane:** <!-- data | database | frontend | devops | digest | qa -->
**Phase:** <!-- 0–4 -->

## Validation

- [ ] Tests added/updated and passing locally
- [ ] Rollback: <!-- how to revert safely -->

## New dependencies

<!-- One line per new package: name — why it's needed (SPEC §Security). Write "none" if none. -->

## Security checklist (required if touching auth, admin, API routes, or dependencies)

- [ ] No secrets, tokens, or connection strings in code, fixtures, or logs
- [ ] All DB queries parameterized; ALeRCE data treated as untrusted and escaped before render
- [ ] Admin pages/routes check auth server-side (not middleware-only); allowlist is by GitHub user ID
- [ ] State-changing admin actions have CSRF protection and write to the audit log
- [ ] Least-privilege DB role used for this code path
- [ ] Security headers / CSP unaffected or updated deliberately
- [ ] See `docs/security-checklist.md` for the full QA list
