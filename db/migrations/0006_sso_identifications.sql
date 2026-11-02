-- 0006_sso_identifications: Solar System object (asteroid) identifications from IMCCE SkyBoT.
-- Queries asteroid alerts at (meanra, meandec, firstmjd) and stores the closest match within 10".
-- See docs/decisions.md #30.

CREATE TABLE sso_identifications (
    survey            text             NOT NULL CHECK (survey IN ('ztf', 'lsst')),
    oid               text             NOT NULL CHECK (length(oid) BETWEEN 1 AND 64),
    obs_mjd           double precision NOT NULL,
    queried_at        timestamptz      NOT NULL DEFAULT now(),
    status            text             NOT NULL CHECK (status IN ('matched', 'no_match', 'error')),
    sso_number        integer          CHECK (sso_number >= 1),
    sso_name          text             CHECK (length(sso_name) BETWEEN 1 AND 128),
    sso_class         text             CHECK (length(sso_class) <= 64),
    predicted_mag     real,
    sep_arcsec        real             CHECK (sep_arcsec >= 0),
    ra_rate_arcsec_h  real,
    dec_rate_arcsec_h real,
    geo_dist_au       double precision CHECK (geo_dist_au > 0),
    helio_dist_au     double precision CHECK (helio_dist_au > 0),
    error             text             CHECK (length(error) <= 500),
    CHECK ((status = 'matched') = (sso_name IS NOT NULL AND sep_arcsec IS NOT NULL)),
    CHECK ((status = 'error') = (error IS NOT NULL)),
    PRIMARY KEY (survey, oid),
    FOREIGN KEY (survey, oid) REFERENCES objects (survey, oid) ON DELETE CASCADE
);

CREATE INDEX sso_identifications_name_idx   ON sso_identifications (sso_name);
CREATE INDEX sso_identifications_status_idx ON sso_identifications (status, queried_at);

GRANT SELECT, INSERT, UPDATE ON sso_identifications TO skyalerts_ingest;
GRANT SELECT ON sso_identifications TO skyalerts_ro, skyalerts_web_admin;
