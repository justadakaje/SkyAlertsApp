# `skyalerts_digest` — Weekly Sky Alerts Digest

Phase 3 & 4 weekly Sky Alerts digest: selects notable events from Postgres over a 7-day window, renders plain-English Markdown and HTML summaries plus a weekly podcast segment script/outline (`render_podcast`), and delivers the email (with the podcast outline attached) through Resend from `sky.henseler.app`.

## Modules

- `skyalerts_digest/classes.py`: ALeRCE class metadata (`KNOWN`, `GROUPS`, `TRANSIENT_CLASSES`, `LOW_PRIORITY_CLASSES`, `ARTIFACT_CLASS`, `class_info`, `group_of`), ported verbatim from `web/lib/classes.ts`.
- `skyalerts_digest/select.py`: `select_digest(conn, week_end)` — parameterized read-only SQL queries over `[week_end - 7 days, week_end]` returning frozen dataclasses (`Digest`, `DigestObject`, `SolarSystemSection`, `WeekStats`, `GroupCount`):
  - **Headliners:** up to 5 highest-confidence transient-tier objects (`SN`, `SNIa`, `SNIbc`, `SNII`, `SLSN`, `TDE`, `KN`, `CV/Nova`) first detected in the week (`top_probability DESC`, `lastmjd DESC`).
  - **Brightest new:** up to 3 objects first detected in the week with the brightest detection (`min(mag)` in `detections`), excluding `bogus` and `asteroid`. Omitted when there are no magnitude detections.
  - **Solar system:** total count of `asteroid` objects first detected in the week plus up to 3 examples.
  - **Week in numbers:** new objects by class group, total non-artifact objects tracked, and light-curve points stored.
  - `bogus` artifacts are excluded everywhere.
- `skyalerts_digest/render.py`: `render_markdown(digest)` and `render_html(digest)` — plain-English summaries with class blurbs, object links (`https://sky.henseler.app/objects/<survey>/<oid>`), full `html.escape` sanitization on all upstream values, and a friendly "quiet week" message when no new events were recorded.
- `skyalerts_digest/podcast.py`: `render_podcast(digest)` — Markdown script/outline for a 3–5 minute spoken segment titled `What the sky did this week · <Mon D>–<Mon D>`, including Cold open, Headliners, Brightest new, Solar-system roundup, By the numbers, Outro, and `[Show notes]` plain links. Strips Markdown control characters and raw HTML from untrusted upstream values.
- `skyalerts_digest/config.py`: `DigestConfig.from_env()` — validates `DATABASE_URL`, `RESEND_API_KEY`, `DIGEST_FROM` (must use `@sky.henseler.app`), and `DIGEST_TO` (1–5 comma-separated addresses). Validation errors never echo secret or address values.
- `skyalerts_digest/send.py`: `send_digest(digest, cfg, client)` — POSTs `{from, to, subject, html, text, attachments}` to `https://api.resend.com/emails` with `Idempotency-Key: digest-<week_end YYYY-MM-DD>`, attaching the podcast outline as `sky-this-week-<week_end>.md` (base64 UTF-8), a 10 s timeout, and one retry on `429`/`5xx` (honouring `Retry-After` up to 10 s). Logs recipient count and domain only, never full addresses or the API key.
- `skyalerts_digest/web.py`: WSGI entrypoint (`skyalerts_digest.web:app`) serving `GET /api/cron/digest`, `POST /api/manual/digest`, and `POST /api/preview/digest`.
- `skyalerts_digest/logutil.py`: JSON-lines structured logging to stderr.
- `skyalerts_digest/__main__.py`: CLI entrypoint (`python -m skyalerts_digest`) for local preview.

## Deployment: Vercel project `skyalerts-digest` (Root Directory `digest/`)

- **Project name:** `skyalerts-digest` with Root Directory set to `digest/`.
- **Entrypoint:** `skyalerts_digest.web:app` (WSGI, configured via `[tool.vercel]` in `pyproject.toml`).
- **Routes:**
  - `GET /api/cron/digest` — invoked by Vercel Cron with `Authorization: Bearer $CRON_SECRET`.
  - `POST /api/manual/digest` — invoked manually (or from `/admin`) with `Authorization: Bearer $DIGEST_TRIGGER_SECRET`.
  - `POST /api/preview/digest` — invoked from `/admin` with `Authorization: Bearer $DIGEST_TRIGGER_SECRET`; selects and renders `digest_markdown` and `podcast_markdown` (`status`, `week_end`, `subject`, `headliners`, `digest_markdown`, `podcast_markdown`) without sending email.
- **Cron schedule (`digest/vercel.json`):** `0 14 * * 1` — Mondays at 14:00 UTC, one hour after the daily 13:00 UTC ingest job. Computes `week_end` as today `00:00:00 UTC`.
- **Function config:** `maxDuration: 60` seconds on `skyalerts_digest/web.py`.
- **Environment variables (Production only):**
  - `DATABASE_URL`: read-only `skyalerts_ro` connection string to Neon database `neondb` (`sslmode=require`).
  - `RESEND_API_KEY`: Resend sending-only API key scoped to `sky.henseler.app`.
  - `DIGEST_FROM`: optional; defaults to `Sky Alerts <digest@sky.henseler.app>`. Must end with `@sky.henseler.app` or `@sky.henseler.app>`.
  - `DIGEST_TO`: comma-separated list of 1–5 recipient email addresses (e.g. `owner@example.com`).
  - `CRON_SECRET`: random secret (at least 16 characters; 32+ recommended) sent by Vercel Cron as `Authorization: Bearer <CRON_SECRET>`.
  - `DIGEST_TRIGGER_SECRET`: random secret (at least 32 characters), distinct from `CRON_SECRET`, used to authorize `POST /api/manual/digest` and `POST /api/preview/digest`.
  - `LOG_LEVEL`: optional (defaults to `INFO`).

## Manual Trigger & Preview

Preview this week's digest and podcast outline without sending email:

```bash
curl -X POST "https://<skyalerts-digest-deployment>/api/preview/digest" \
  -H "Authorization: Bearer $DIGEST_TRIGGER_SECRET" \
  -H "x-vercel-protection-bypass: $VERCEL_AUTOMATION_BYPASS_SECRET"
```

Trigger a digest send manually against the deployed Vercel project (include `x-vercel-protection-bypass` if Deployment Protection is enabled on `*.vercel.app`):

```bash
curl -X POST "https://<skyalerts-digest-deployment>/api/manual/digest" \
  -H "Authorization: Bearer $DIGEST_TRIGGER_SECRET" \
  -H "x-vercel-protection-bypass: $VERCEL_AUTOMATION_BYPASS_SECRET"
```

Render Markdown locally (read-only, no email sent):

```bash
DATABASE_URL=postgresql://... uv --directory digest run python -m skyalerts_digest --week-end 2026-11-01
```

Render HTML locally:

```bash
DATABASE_URL=postgresql://... uv --directory digest run python -m skyalerts_digest --week-end 2026-11-01 --html
```

## Lint & Tests

```bash
uv --directory digest run ruff check .
uv --directory digest run ruff format .
uv --directory digest run pytest -q
```
