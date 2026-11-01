-- 0004_web_admin_role: least-privilege role for the /admin web area (SPEC §Security → Admin and auth).
--
-- Created WITHOUT a password (set out-of-band, see 0002 and decisions.md #15).
-- Read-only on the four data tables + ingest_runs, and append-only (SELECT +
-- column-scoped INSERT) on audit_log. Manual ingest re-runs go through the
-- authenticated ingest endpoint, not SQL.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'skyalerts_web_admin') THEN
        CREATE ROLE skyalerts_web_admin LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOINHERIT;
    END IF;
END
$$;

ALTER ROLE skyalerts_web_admin SET statement_timeout = '10s';

GRANT USAGE ON SCHEMA public TO skyalerts_web_admin;

GRANT SELECT ON objects, classifications, detections, ingest_runs TO skyalerts_web_admin;

-- audit_log: append-only, and column-scoped so the role can't choose id or backdate at.
GRANT SELECT ON audit_log TO skyalerts_web_admin;
GRANT INSERT (actor_github_id, action, target, details) ON audit_log TO skyalerts_web_admin;
