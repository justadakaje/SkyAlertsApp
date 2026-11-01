-- 0002_roles_and_grants: least-privilege roles (SPEC §Security → Data and secrets).
--
-- Roles are created here WITHOUT passwords so nothing secret lives in the repo.
-- Passwords are set out-of-band (ALTER ROLE ... PASSWORD) and stored only in
-- Vercel/GitHub encrypted env vars.
--
-- NOTE (Neon): roles created through the Neon console/API are made members of
-- neon_superuser. Create app roles with SQL (as below) so they stay plain logins.
--
--   skyalerts_admin   owner; runs migrations (Neon-managed; not created here)
--   skyalerts_ingest  ingest job: read/insert/update data tables, write ingest_runs
--   skyalerts_ro      public website: read-only on data tables + ingest_runs

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'skyalerts_ingest') THEN
        CREATE ROLE skyalerts_ingest LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOINHERIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'skyalerts_ro') THEN
        CREATE ROLE skyalerts_ro LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOINHERIT;
    END IF;
END
$$;

-- Guard rails: statement timeouts so a bad query can't pin the compute.
ALTER ROLE skyalerts_ingest SET statement_timeout = '60s';
ALTER ROLE skyalerts_ro     SET statement_timeout = '10s';
ALTER ROLE skyalerts_ro     SET default_transaction_read_only = on;

-- Nobody but the owner creates objects in public.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO skyalerts_ingest, skyalerts_ro;

-- Ingest: upsert data, no DELETE/TRUNCATE (retention is an admin job).
GRANT SELECT, INSERT, UPDATE ON objects, classifications, detections TO skyalerts_ingest;
GRANT SELECT, INSERT, UPDATE ON ingest_runs TO skyalerts_ingest;

-- Website: read-only.
GRANT SELECT ON objects, classifications, detections, ingest_runs TO skyalerts_ro;

-- audit_log: no grants yet; the Phase 2 admin role gets INSERT/SELECT only.
