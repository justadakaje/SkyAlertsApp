-- 0001_init: core schema for Sky Alerts.
-- Applied by db/migrate.py as the owner role (skyalerts_admin) inside one transaction.
-- Conventions: (survey, oid) is the natural key everywhere; oid is text because
-- ZTF ids are strings ("ZTF26acdjxpj") and LSST ids are int64 (stored as text).
-- Times from ALeRCE are MJD (UTC); *_at columns are wall-clock timestamptz.

CREATE TABLE objects (
    survey                 text        NOT NULL CHECK (survey IN ('ztf', 'lsst')),
    oid                    text        NOT NULL CHECK (length(oid) BETWEEN 1 AND 64),
    meanra                 double precision CHECK (meanra >= 0 AND meanra < 360),
    meandec                double precision CHECK (meandec BETWEEN -90 AND 90),
    firstmjd               double precision,
    lastmjd                double precision,
    ndet                   integer CHECK (ndet >= 0),
    n_forced               integer CHECK (n_forced >= 0),
    stellar                boolean,
    top_class              text,
    top_classifier         text,
    top_classifier_version text,
    top_probability        real CHECK (top_probability BETWEEN 0 AND 1),
    raw                    jsonb       NOT NULL,
    first_ingested_at      timestamptz NOT NULL DEFAULT now(),
    last_ingested_at       timestamptz NOT NULL DEFAULT now(),
    last_ingest_run_id     bigint,
    PRIMARY KEY (survey, oid)
);

CREATE INDEX objects_lastmjd_idx      ON objects (lastmjd DESC);
CREATE INDEX objects_firstmjd_idx     ON objects (firstmjd DESC);
CREATE INDEX objects_class_recent_idx ON objects (top_class, lastmjd DESC);
-- Coarse positional index (dec band, then ra). Good enough for box queries at
-- our volume; revisit (PostGIS / HEALPix) if cone search becomes a feature.
CREATE INDEX objects_position_idx     ON objects (meandec, meanra);

CREATE TABLE classifications (
    survey             text        NOT NULL,
    oid                text        NOT NULL,
    classifier_name    text        NOT NULL,
    classifier_version text        NOT NULL DEFAULT '',
    class_name         text        NOT NULL,
    probability        real        NOT NULL CHECK (probability BETWEEN 0 AND 1),
    ranking            smallint    CHECK (ranking >= 1),
    ingested_at        timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (survey, oid, classifier_name, classifier_version, class_name),
    FOREIGN KEY (survey, oid) REFERENCES objects (survey, oid) ON DELETE CASCADE
);

CREATE INDEX classifications_class_idx
    ON classifications (classifier_name, class_name, probability DESC);

-- Sampled light-curve points (Phase 2 charts). Photometry kept in both forms:
-- ZTF reports magnitudes, LSST reports flux in nJy.
CREATE TABLE detections (
    survey         text             NOT NULL,
    oid            text             NOT NULL,
    measurement_id text             NOT NULL,
    mjd            double precision NOT NULL,
    band           text,
    mag            real,
    mag_err        real,
    flux_njy       double precision,
    flux_err_njy   double precision,
    raw            jsonb            NOT NULL,
    ingested_at    timestamptz      NOT NULL DEFAULT now(),
    PRIMARY KEY (survey, oid, measurement_id),
    FOREIGN KEY (survey, oid) REFERENCES objects (survey, oid) ON DELETE CASCADE
);

CREATE INDEX detections_object_time_idx ON detections (survey, oid, mjd);

CREATE TABLE ingest_runs (
    id                       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    started_at               timestamptz NOT NULL DEFAULT now(),
    finished_at              timestamptz,
    status                   text        NOT NULL DEFAULT 'running'
                             CHECK (status IN ('running', 'success', 'partial', 'failed')),
    trigger                  text        NOT NULL CHECK (trigger IN ('cron', 'manual', 'cli')),
    surveys                  text[]      NOT NULL,
    objects_seen             integer     NOT NULL DEFAULT 0,
    objects_upserted         integer     NOT NULL DEFAULT 0,
    classifications_upserted integer     NOT NULL DEFAULT 0,
    requests                 integer     NOT NULL DEFAULT 0,
    error_count              integer     NOT NULL DEFAULT 0,
    errors                   jsonb       NOT NULL DEFAULT '[]'::jsonb,
    duration_ms              integer,
    CHECK (finished_at IS NULL OR finished_at >= started_at)
);

CREATE INDEX ingest_runs_started_idx ON ingest_runs (started_at DESC);

ALTER TABLE objects
    ADD CONSTRAINT objects_last_ingest_run_fk
    FOREIGN KEY (last_ingest_run_id) REFERENCES ingest_runs (id) ON DELETE SET NULL;

-- Admin actions (Phase 2). Append-only for the web admin role; no UPDATE/DELETE grants.
CREATE TABLE audit_log (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    at               timestamptz NOT NULL DEFAULT now(),
    actor_github_id  bigint      NOT NULL,
    action           text        NOT NULL,
    target           text,
    details          jsonb       NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX audit_log_at_idx ON audit_log (at DESC);
