-- 0003_enrichment: per-object light-curve and probability enrichment tracking.

ALTER TABLE objects
    ADD COLUMN enriched_at      timestamptz,
    ADD COLUMN enriched_lastmjd double precision;

ALTER TABLE ingest_runs
    ADD COLUMN objects_enriched    integer NOT NULL DEFAULT 0,
    ADD COLUMN detections_upserted integer NOT NULL DEFAULT 0;

GRANT UPDATE (objects_enriched, detections_upserted) ON ingest_runs TO skyalerts_ingest;
