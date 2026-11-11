-- 0007_retention_policy: Bounded retention helper for un-enriched bogus artifacts.
-- Keeps skyalerts_ingest without table-level DELETE privileges while allowing it
-- to prune un-enriched 'bogus' rows older than max_age_days (default 30 days).

CREATE OR REPLACE FUNCTION prune_old_artifacts(
    max_age_days double precision DEFAULT 30.0,
    ref_mjd double precision DEFAULT NULL
)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    wall_mjd double precision;
    effective_ref double precision;
    cutoff_mjd double precision;
    deleted_count integer;
BEGIN
    IF max_age_days < 7.0 THEN
        RAISE EXCEPTION 'max_age_days must be at least 7.0 (got %)', max_age_days;
    END IF;
    wall_mjd := extract(epoch FROM now()) / 86400.0 + 40587.0;
    effective_ref := LEAST(COALESCE(ref_mjd, wall_mjd), wall_mjd);
    cutoff_mjd := effective_ref - max_age_days;
    DELETE FROM objects
     WHERE top_class = 'bogus'
       AND enriched_at IS NULL
       AND lastmjd IS NOT NULL
       AND lastmjd < cutoff_mjd;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END
$$;

REVOKE ALL ON FUNCTION prune_old_artifacts(double precision, double precision) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION prune_old_artifacts(double precision, double precision) TO skyalerts_ingest;
