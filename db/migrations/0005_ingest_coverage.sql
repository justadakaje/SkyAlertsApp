-- 0005_ingest_coverage: per-source paging coverage for each run. The ingest job
-- reads each source's catch-up watermark (newest lastmjd seen) from here instead of
-- the wall-clock start of the last successful run. See docs/decisions.md #28.

ALTER TABLE ingest_runs
    ADD COLUMN coverage jsonb NOT NULL DEFAULT '{}'::jsonb;

GRANT UPDATE (coverage) ON ingest_runs TO skyalerts_ingest;
