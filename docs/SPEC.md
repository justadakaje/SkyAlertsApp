# Sky Alerts — Project Spec & Sub-Agent Handoff

## Overview

Sky Alerts is a personal project that pulls astronomy alerts from the ALeRCE alert broker (ZTF today, Vera C. Rubin Observatory / LSST as it comes online) and turns them into something you can watch, read, and query. The project is hosted on Vercel at **sky.henseler.app**, with code in the GitHub repo **skyalerts**.

Goals:

- A public dashboard of fresh, interesting sky events (supernovae, variable stars, solar system objects, etc.).
- A weekly digest email in plain English.
- A personal alert database that grows over time and lets us look for trends.
- A ready-made "what the sky did this week" segment for podcast use.

Non-goals (for now): real-time alerting from the Kafka stream, public user accounts, mobile apps.

## Data Source: ALeRCE

- ALeRCE is one of the seven Rubin full-stream brokers and has processed ZTF alerts for years.
- Access paths: the public REST API and the official Python client (`pip install alerce`).
- Key concepts: **objects** (an astronomical source, identified by an OID), **detections** (individual light-curve points), and **classifications** (ML classifier outputs with probabilities, e.g. stamp classifier and light-curve classifier).
- First task for the data agent: confirm current endpoints, rate limits, Rubin vs. ZTF coverage, and field names against the live ALeRCE docs. Record findings in `docs/alerce-notes.md`.

## Architecture

- **Ingest job (Python):** scheduled pull (e.g. every few hours) of recent objects and their classifications from ALeRCE. Normalizes and upserts into the database. Idempotent and safe to re-run.
- **Database:** Postgres on Neon (decided), connected through the Vercel integration, starting on the free tier. Tables for objects, classifications, detections (sampled), and ingest runs. Indexes on discovery time, class, and coordinates.
- **Web app:** Next.js on Vercel. Reads from the database, never calls ALeRCE directly on page load.
- **Digest job:** weekly scheduled function that builds a summary from the database and sends an email.
- **Scheduling:** Vercel Cron for web-side jobs; ingest can run as a Vercel Python function or a GitHub Action, whichever handles runtime limits better. Agent should recommend one.
- **Secrets:** all credentials in Vercel environment variables. Nothing committed.

## Phases

### Phase 0 — Foundation

- Create the `skyalerts` GitHub repo, README, license, `.gitignore`, basic CI (lint + tests).
- Exploration script that pulls a handful of recent alerts and prints a summary of fields, classes, and freshness.
- Write `docs/alerce-notes.md`.

### Phase 1 — Ingest & Database

- Schema design and migrations.
- Ingest job with logging, retries, and backoff that respects rate limits.
- An `ingest_runs` table recording counts, duration, and errors per run.

### Phase 2 — Dashboard v1

- Home page: latest notable events, filterable by class and time window.
- Object detail page: classification probabilities, light curve chart, discovery time, sky position, link back to ALeRCE explorer.
- Simple stats page: counts by class per day/week. All of the above is public. Secure admin dashboard at /admin, owner-only sign-in: ingest run health and errors, manual re-run, digest preview and send, settings.
- Deploy to Vercel and attach **sky.henseler.app**.

### Phase 3 — Weekly Digest

- Weekly job that picks the top events (highest-confidence rare classes, brightest new transients, notable solar system objects).
- Short plain-English explanations for each event.
- Email delivery through Resend (decided), sending from henseler.email on a sending subdomain so Proton Mail's root MX records stay untouched. Start with a single recipient (the owner).

### Phase 4 — Trends & Podcast Segment

- Trend views: rates over time, class mix, seasonal patterns as data accumulates.
- Export a weekly "what the sky did this week" script/outline in Markdown for podcast use.

## Sub-Agent Workstreams

Each agent owns a lane, works on its own branch, and opens a pull request. The orchestrator reviews and merges.

- **Data Agent:** ALeRCE research, exploration script, ingest job, data-quality checks. Owns `ingest/` and `docs/alerce-notes.md`.
- **Database Agent:** schema, migrations, indexes, query performance, retention policy. Owns `db/`.
- **Frontend Agent:** Next.js app, pages, charts, styling, accessibility. Owns `web/`.
- **DevOps Agent:** repo setup, CI, Vercel project, environment variables, cron jobs, domain. Owns `.github/` and deployment config.
- **Digest & Content Agent:** weekly digest logic, email templates, plain-English summaries, podcast segment export. Owns `digest/`.
- **QA Agent:** tests across lanes, reviews PRs for correctness and security, verifies acceptance criteria.

## Security

Security is a release gate: no phase ships to production until this section's checks pass. Vercel runs serverless, so there is no OS or web server for us to patch; Vercel patches its platform. Our job is keeping our code, dependencies, configuration and access tight.

### Patching and dependencies

- Dependabot (or Renovate) on for npm and pip, with security updates merged within 7 days and critical ones within 48 hours.
- CI runs `npm audit`, `pip-audit` and GitHub CodeQL on every PR; high or critical findings block the merge.
- Lockfiles committed, versions pinned, and Next.js kept on a current supported release.
- Minimal dependencies: every new package needs a one-line justification in the PR.

### Hosting and network

- HTTPS only, with HSTS. Security headers on every response: Content-Security-Policy, X-Content-Type-Options, Referrer-Policy, Permissions-Policy and frame-ancestors 'none'.
- Vercel Firewall on, with rate limiting on API routes and bot protection on public pages.
- Preview deployments behind Vercel Deployment Protection, so only the production domain is public.

### Admin and auth

- Admin sign-in through GitHub OAuth, allowlisted to the owner's GitHub user ID (not just the username).
- Auth is checked server-side on every admin page and API route. Middleware alone is never the only guard.
- Secure, HttpOnly, SameSite session cookies, short sessions, and CSRF protection on admin actions.
- Admin actions (re-runs, sends, settings changes) written to an audit log table.

### Data and secrets

- All secrets in Vercel environment variables, separate for preview and production; GitHub secret scanning and push protection on.
- Least-privilege database roles: the public site uses a read-only role, the ingest job a write role, migrations an admin role.
- All queries parameterized; all ALeRCE data treated as untrusted input and escaped before rendering.
- Resend API key limited to sending only, from the sending subdomain.

### Repo and process

- Branch protection on main: PRs required, CI must pass, no force pushes.
- The QA agent runs a security review checklist on every PR touching auth, admin, API routes or dependencies.
- Monitoring: Vercel logs plus alerts on ingest failures, error spikes and admin sign-ins.

## Conventions

- Small, focused PRs with clear descriptions.
- Every module gets tests; ingest and digest logic need fixtures from real sample data.
- Structured logging; no silent failures.
- Ask the owner before major design decisions (stack changes, paid services, new data sources).
- Keep a running `docs/decisions.md` log of design choices and why.

## Acceptance Criteria

- Phase 0: repo exists, CI passes, exploration script runs and its summary is documented.
- Phase 1: ingest runs on schedule, is idempotent, and logs each run; database holds at least a week of data.
- Phase 2: dashboard is live at sky.henseler.app, loads quickly, and object pages show classifications and light curves.
- Phase 3: owner receives a readable weekly digest email.
- Phase 4: trend views work and a podcast segment outline is generated weekly.

## Open Questions

- Neon plan: when to move off the free tier as data grows.
- Resend DNS setup on henseler.email: confirm the sending subdomain records and that DMARC still passes alongside Proton Mail.
- Admin auth method (e.g. Auth.js with GitHub sign-in limited to the owner) and admin feature list.
- How to blend ZTF and Rubin data as Rubin alerts ramp up.
- Visual style and branding for the site.
