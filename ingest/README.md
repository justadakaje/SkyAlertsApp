# ingest/

ALeRCE client, Phase 0 exploration script, and the daily ingest job.

## Run locally
```bash
uv sync --frozen
uv run pytest                              # set TEST_DATABASE_URL for the DB tests
DATABASE_URL=<skyalerts_ingest dsn> uv run python -m skyalerts_ingest.ingest --surveys lsst,ztf
DATABASE_URL=<skyalerts_ingest dsn> uv run python -m skyalerts_ingest.sso --max 30
```

## Deployment: Vercel project `skyalerts-ingest` (Root Directory `ingest/`)
- Entrypoint: `skyalerts_ingest.web:app` (WSGI, `[tool.vercel]` in pyproject). Routes: `GET /api/cron/ingest` and `GET /api/cron/identify` (Vercel Cron), plus `POST /api/manual/ingest` and `POST /api/manual/identify` (owner-triggered re-runs from `/admin`).
- Crons: `0 13 * * *` (`ingest`) and `30 13 * * *` (`identify`) (Hobby: once a day each, firing within the 13:00 UTC hour after the Chilean night and ALeRCE processing).
- `maxDuration` is 300 s. Each job budgets 240 s.
- Env vars (Production only):
  - `DATABASE_URL`: `skyalerts_ingest` connection string to database `neondb` with `sslmode=require`. The pooled `-pooler` endpoint is fine: the run lease uses a transaction-scoped lock.
  - `CRON_SECRET`: random, at least 16 characters. Vercel sends it as `Authorization: Bearer …`.
  - `MANUAL_TRIGGER_SECRET`: random, at least 32 characters, separate from `CRON_SECRET`. Sent as `Authorization: Bearer …` to `POST /api/manual/ingest` and `POST /api/manual/identify`; also set in the web project (Production env) as the caller's copy so `/admin` never holds `CRON_SECRET`.
  - optional (`ingest`): `INGEST_MAX_PAGES` (20, the cap for sources without their own), `INGEST_PAGE_SIZE` (100), `INGEST_TIME_BUDGET_S` (240), `INGEST_ENRICH_MAX` (40), `ALERCE_MIN_INTERVAL_S` (1.0), `LOG_LEVEL`
  - optional (`identify`): `IDENTIFY_MAX` (30), `IDENTIFY_TIME_BUDGET_S` (240), `SKYBOT_MIN_INTERVAL_S` (1.0), `SKYBOT_URL`

## Behaviour
- **Sources** (in order; later rows win `top_class`):
  - Neither unfiltered stream can be paged completely in one run: a Rubin night is ~500 pages, and ZTF is 100 rows per ~2 min of data. Each is a newest-first **sample**, and stopping at its cap is not a gap.
    - `lsst:default`: 20 pages.
    - `ztf:stamp_classifier` and `ztf:lc_classifier`: 1 page each.
  - The tier-1 transient classes are **complete**:
    - `lsst:stamp_classifier_rubin_beta_20260421:SN`: up to 40 pages.
    - `ztf:stamp_classifier:SN` and `ztf:lc_classifier:{SNIa,SNIbc,SNII,SLSN,CV/Nova}`: up to 10 pages each.
  - ZTF lc always wins over stamp for `top_class`.
- **Paging:** newest-first, 100 per page. Stops at a short page, once rows are older than the source's catch-up floor, at the page cap, or at the time budget.
- **Enrichment:** after list paging (unless the list phase hit the time budget), up to `INGEST_ENRICH_MAX` (40) objects touched in the run (excluding `bogus`/`asteroid` and objects where `enriched_lastmjd >= lastmjd`) are enriched in priority order (Tier 1 transients → Tier 2 variable/other → Tier 3 AGN/QSO/Blazar, then `top_probability DESC`, `lastmjd DESC`). Each object fetches detections (keeping up to 200 newest with a slim `raw` whitelist) and probabilities (keeping `ranking <= 3` per classifier/version) within the shared time budget. Enrichment errors or budget exhaustion are logged without demoting the run status.
- **Safety:** idempotent upserts. A lease row in `ingest_runs`, claimed under a transaction-scoped advisory lock, makes duplicate or overlapping cron calls skip. Runs left `running` for more than 10 min are closed as failed.
- **Catch-up** (`docs/decisions.md` #28): each complete source keeps a watermark in data time: the newest `lastmjd` it saw, stored in `ingest_runs.coverage` (migration 0005).
  - Floor = watermark − 1 day of overlap. With no watermark yet, floor = newest row − 1.2 days. Either way it is bounded to 7 days.
  - A complete source that hits its page cap before the floor makes the run `partial` and records `gap_mjd` in `errors`. Its window still advances, so the gap is reported once.
  - A budget hit or a failed source doesn't advance that source's window; the next run re-covers it.
  - Rows dated more than 1 h in the future are ignored for watermarks.
  - LSST SN is flagged if it falls more than 2 days behind the LSST sample. The classifier name is dated, so a rename would freeze it.
- **Run log:** every run writes an `ingest_runs` row with status, counts (`objects_seen`, `objects_upserted`, `classifications_upserted`, `objects_enriched`, `detections_upserted`), request count, errors, and per-source `coverage` (floor, newest/oldest `lastmjd`, pages, outcome).

## Asteroid identification (`skyalerts_ingest.sso`)
- Queries IMCCE SkyBoT (`conesearch.php`, `-rd=0.003` deg / 10.8", MPC codes `I41` for ZTF and `X05` for LSST) at `(meanra, meandec, firstmjd)` for up to `IDENTIFY_MAX` (30) `top_class = 'asteroid'` objects that have no `sso_identifications` row or whose `error` row is older than 1 day (ZTF first, then `top_probability DESC`, `lastmjd DESC`).
- Stores the closest match in `sso_identifications` when separation `d <= 10"` (`status = 'matched'`), otherwise `no_match` (or `error` on upstream failure, without echoing upstream bodies). Stops cleanly when `IDENTIFY_TIME_BUDGET_S` (240 s) is reached. See `docs/decisions.md` #29.
