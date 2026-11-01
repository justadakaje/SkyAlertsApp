# ingest/

ALeRCE client, Phase 0 exploration script, and the daily ingest job.

## Run locally
```bash
uv sync --frozen
uv run pytest                              # set TEST_DATABASE_URL for the DB tests
DATABASE_URL=<skyalerts_ingest dsn> uv run python -m skyalerts_ingest.ingest --surveys lsst,ztf
```

## Deployment: Vercel project `skyalerts-ingest` (Root Directory `ingest/`)
- Entrypoint: `skyalerts_ingest.web:app` (WSGI, `[tool.vercel]` in pyproject). The only route is `GET /api/cron/ingest`.
- Cron: `0 13 * * *` (Hobby: once a day, fires within the 13:00 UTC hour). That's after the Chilean night and ALeRCE processing.
- `maxDuration` is 300 s. The job budgets 240 s and records `partial` if it runs out.
- Env vars (Production only):
  - `DATABASE_URL`: `skyalerts_ingest` connection string to database `neondb` with `sslmode=require`. The pooled `-pooler` endpoint is fine: the run lease uses a transaction-scoped lock.
  - `CRON_SECRET`: random, at least 16 characters. Vercel sends it as `Authorization: Bearer …`.
  - optional: `INGEST_MAX_PAGES` (20), `INGEST_PAGE_SIZE` (100), `INGEST_TIME_BUDGET_S` (240), `INGEST_ENRICH_MAX` (40), `ALERCE_MIN_INTERVAL_S` (1.0), `LOG_LEVEL`

## Behaviour
- **Sources:** LSST (rows carry the top class), then ZTF `stamp_classifier`, then ZTF `lc_classifier` (lc wins `top_class`).
- **Paging:** newest-first, 20 pages × 100 per source. Stops at short pages, once rows are older than the catch-up window (last good run − 1 day, bounded to 2–7 days), at the page cap, or at the time budget.
- **Enrichment:** after list paging (unless the list phase hit the time budget), up to `INGEST_ENRICH_MAX` (40) objects touched in the run (excluding `bogus`/`asteroid` and objects where `enriched_lastmjd >= lastmjd`) are enriched in priority order (Tier 1 transients → Tier 2 variable/other → Tier 3 AGN/QSO/Blazar, then `top_probability DESC`, `lastmjd DESC`). Each object fetches detections (keeping up to 200 newest with a slim `raw` whitelist) and probabilities (keeping `ranking <= 3` per classifier/version) within the shared time budget. Enrichment errors or budget exhaustion are logged without demoting the run status.
- **Safety:** idempotent upserts. A lease row in `ingest_runs`, claimed under a transaction-scoped advisory lock, makes duplicate or overlapping cron calls skip. Runs left `running` for more than 10 min are closed as failed.
- **Catch-up:** only a fully successful run moves the window forward. A partial run (page cap or budget hit, a source failed, rows rejected) is re-covered next time, up to 7 days back.
- **Run log:** every run writes an `ingest_runs` row with status, counts (`objects_seen`, `objects_upserted`, `classifications_upserted`, `objects_enriched`, `detections_upserted`), request count and errors.
