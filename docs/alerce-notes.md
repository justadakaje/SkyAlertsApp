# ALeRCE Notes

Researched 2026-11-01 against the live docs and the `alerce` Python client **2.3.1** (latest on PyPI). Items marked ⚠️ are undocumented and must be confirmed by the first live run of `ingest/skyalerts_ingest/explore.py` (Explore ALeRCE workflow).

## Status / coverage

- **Rubin (LSST):** ALeRCE's Rubin pipeline went public in early March 2026 (explorer at `lsst.alerce.online`, API, Python client, TAP). ALeRCE describes it as in an *iterative validation phase*; some capabilities are limited by ongoing Rubin alert-stream changes. Rubin alerts started streaming Feb 2026; the LSST 10-year survey formally started 2026-06-29.
- **ZTF:** still processed by ALeRCE on the legacy ZTF API. NSF funding covered ZTF operations through **2025–2026** — ⚠️ risk that ZTF alert volume drops or ends in 2027. Design must not assume ZTF is permanent.
- **Maintenance windows** are announced on the Rubin Community forum (ALeRCE category) — recent ones ran 4–6 h (2026-04-16, 06-17, 07-02). Ingest must tolerate multi-hour outages (retry next schedule, no alert spam on a single failed run).

## Endpoints

### ZTF — legacy API (`https://api.alerce.online`)

| Resource | Path |
|---|---|
| list objects | `GET /ztf/v1/objects` |
| object | `GET /ztf/v1/objects/{oid}` |
| detections | `GET /ztf/v1/objects/{oid}/detections` |
| non-detections | `GET /ztf/v1/objects/{oid}/non_detections` |
| light curve (det + non-det) | `GET /ztf/v1/objects/{oid}/lightcurve` |
| magstats | `GET /ztf/v1/objects/{oid}/magstats` |
| probabilities | `GET /ztf/v1/objects/{oid}/probabilities` |
| features | `GET /ztf/v1/objects/{oid}/features[/{name}]` |
| classifiers | `GET /ztf/v1/classifiers` |
| classes | `GET /ztf/v1/classifiers/{name}/{version}/classes` |
| forced photometry | `GET /v2/lightcurve/forced-photometry/{oid}` |

`/objects` query params: `classifier`, `class` (client maps `class_name`→`class`), `ndet` (range), `probability` (min), `firstmjd`/`lastmjd` (ranges), `ra`/`dec`/`radius` (arcsec cone), `page` (default 1), `page_size` (default 10), `count` (bool — skip it, counting is slow), `order_by`, `order_mode` (`ASC`/`DESC`). Response: `{"items": [...], ...pagination}`.

### LSST — multisurvey API (`https://api-lsst.alerce.online/`)

| Resource | Path | Key params |
|---|---|---|
| list objects | `GET object_api/list_objects` | `survey=lsst` + same filter names as ZTF but `n_det` (not `ndet`), `class_name` (not `class`), plus `ranking` |
| object | `GET object_api/object` | `survey_id`, `oid` |
| detections | `GET lightcurve_api/detections` | `survey_id`, `oid` |
| non-detections | `GET lightcurve_api/non_detections` | `survey_id`, `oid` |
| forced photometry | `GET lightcurve_api/forced-photometry` | `survey_id`, `oid` |
| light curve | `GET lightcurve_api/lightcurve` | `survey_id`, `oid` |
| probabilities | `GET probability_api/probability` | `survey_id`, `oid` |
| stamps | `GET stamps_api/stamp` | |

Note the inconsistency: list uses `survey`, per-object routes use `survey_id`. List response is also `{"items": [...]}`.

Not implemented for LSST in the client (likely not in the API yet): magstats, features, classifier/class listing. ⚠️ We'll need to discover LSST classifier names from object/probability responses.

The multisurvey API **rejects `survey=ztf`** ("ZTF is not yet supported in the multisurvey API") — two code paths are required for now.

### Other
- Stamps (ZTF): `https://avro.alerce.online/get_stamp`, `/get_avro`
- catsHTM crossmatch: `https://catshtm.alerce.online`
- TAP service also exists for LSST (SQL-style bulk queries) — candidate for backfill later.

## Auth & rate limits

- Public, no auth for the endpoints we use.
- ⚠️ **No published rate limit** (checked API docs + client docs). The official client has no throttling, no retry, and **no request timeout**.
- Our policy (see decisions #8): serial requests, ≤1 req/s, 30 s timeout, retry on 429/5xx/transport errors with exponential backoff + jitter, honour `Retry-After`, max 5 attempts. Set a descriptive `User-Agent` with a contact address so ALeRCE can reach us instead of blocking us.

## Field names

### ZTF object (list + single)
`oid`, `ndethist`, `ncovhist`, `mjdstarthist`, `mjdendhist`, `corrected`, `stellar`, `ndet`, `g_r_max`, `g_r_max_corr`, `g_r_mean`, `g_r_mean_corr`, `firstmjd`, `lastmjd`, `deltajd`, `meanra`, `meandec`, `sigmara`, `sigmadec`, `class`, `classifier`, `probability`, `step_id_corr`.

- `class`/`classifier`/`probability` = top class for the requested classifier; default `lc_classifier`, ranking 1.
- Docs list `ndethist` as string though it's a count — ⚠️ coerce defensively.
- Times are **MJD** (UTC). Unix seconds = `(mjd − 40587) × 86400`.

### Probability (both surveys)
`classifier_name`, `classifier_version`, `class_name`, `probability`, `ranking`.

### Detections
- **ZTF:** `oid`, `measurement_id`, `pid`, `diffmaglim`, `isdiffpos`, `nid`, `magpsf`, `sigmapsf`, `magap`, `sigmagap`, `distnr`, `rb`, `rbversion`, `drb`, `drbversion`, `magapbig`, `sigmagapbig`, `rfid`, `magpsf_corr`, `sigmapsf_corr`, `sigmapsf_corr_ext`, `corrected`, `dubious`, `parent_candid`, `has_stamp` (+ `mjd`, `fid` expected ⚠️).
- **LSST:** `oid` (**integer**), `measurement_id`, `parentDiaSourceId`, `psfFlux`, `psfFluxErr` (nJy), `psfFlux_flag`, `psfFlux_flag_edge`, `psfFlux_flag_noGoodPixels`.

### Key ZTF ↔ LSST differences (drives schema)
| Concern | ZTF | LSST |
|---|---|---|
| OID | string, e.g. `ZTF21aaeyldq` | integer (64-bit), e.g. `170032901203689551` |
| Photometry | magnitudes (`magpsf`) | flux in nJy (`psfFlux`) → mag = −2.5·log10(flux_nJy) + 31.4 |
| Bands | g, r (i) via `fid` | u g r i z y |
| List object fields | documented (above) | ⚠️ undocumented — capture from first run |

Schema implication: `oid` stored as `text` with a `survey` column; composite key `(survey, oid)`. Store raw payload (`jsonb`) alongside normalized columns so LSST schema drift doesn't lose data.

### Classifiers (ZTF, from docs)
- `stamp_classifier` — early classification from first-alert image stamps (classes include SN, AGN, VS, asteroid, bogus).
- `lc_classifier` — hierarchical random forest on light-curve features (e.g. `hierarchical_random_forest_1.0.0`; classes include SNIa, SNIbc, SNII, SLSN, AGN, QSO, Blazar, CV/Nova, YSO, LPV, E, DSCT, RRL, CEP, Periodic-Other).
- ⚠️ Current versions/class lists to be dumped by the explore script via `/classifiers`.

## Live run findings — 2026-11-01 (Explore ALeRCE run 41281922239, 25 objects/survey)

- **ZTF API redirects:** `GET /ztf/v1/objects` answers **308 → `/ztf/v1/objects/`** (same for `/classifiers`). The client now uses trailing slashes and follows same-origin redirects only (max 3). Cross-host redirects are still refused.
- **LSST list fields (confirmed):** `oid` (int64), `sid`, `tid`, `meanra`, `meandec`, `sigmara`, `sigmadec`, `firstmjd`, `lastmjd`, `deltamjd`, `n_det`, `n_forced`, `n_non_det`, `stellar` (always null so far), `class_name`, `classifier_name`, `classifier_version`, `probability`, `ranking`. Pagination wrapper: `{"items": [...]}`.
- **LSST classifier:** `stamp_classifier_rubin_beta_20260421` (v2.0.2) on most rows, older `stamp_classifier_rubin_beta` on some. Classes seen: `bogus`, `VS`, `asteroid`, `AGN`.
- **Data quality:** **13 of 25 newest LSST objects were classed `bogus`** (mean top probability 0.81). Ingest and the dashboard must filter or down-rank bogus.
- **Freshness:** the newest LSST last detection was **~23 h old** at query time, and all 25 came from one night. Plan for "last night's sky", not real-time.
- **Latency:** LSST requests took 0.3–0.9 s. No 429s at ≤1 req/s.
- Artifacts can't be downloaded from the agent workspace (the GitHub blob storage host isn't on its allowlist). Findings come from job logs. You can download the raw samples from the run page.

### ZTF (re-run after the redirect fix: run 41282173932)
- Works through the trailing-slash routes.
- **Without a `classifier` filter, `class`/`classifier`/`probability` come back null on every list row.** Ingest must query per classifier, or fetch `/probabilities` per object.
- Probability classifiers seen: `stamp_classifier` (`stamp_classifier_1.0.4`) and `stamp_classifier_2025_beta` (`2.1.1_beta`). `lc_classifier` didn't appear in this sample (all 25 objects had a single detection).
- `ndethist` really is a **string**. Coerce it.
- **Freshness:** newest ZTF last detection was **65.5 h old** (2026-10-29). ZTF cadence is slowing or patchy, so it can't be the "fresh" signal. Treat Rubin as primary and ZTF as secondary.

## Open items to verify on first live run
1. ~~LSST `list_objects` response field names and pagination keys.~~ Done (see above).
2. Max accepted `page_size` on both APIs.
3. Whether either API returns 429 / `Retry-After` under load.
4. Actual freshness: lag between `lastmjd` and wall clock for newest objects, per survey.
5. LSST classifier names present in probability responses.

## Sources
- [ALeRCE Python client docs](https://alerce.readthedocs.io/en/latest/apis.html), [Models](https://alerce.readthedocs.io/en/latest/models.html), [Migration guide](https://alerce.readthedocs.io/en/latest/migration_guide.html)
- `alerce` 2.3.1 wheel: `alerce/default_config.json`, `ms_search.py`, `ztf_search.py`
- [ALeRCE API docs](https://alerceapi.readthedocs.io/)
- [ALeRCE is now live processing Rubin alerts](https://community.lsst.org/t/alerce-is-now-live-processing-rubin-alerts/11632)
- [Rubin Early Science Program](https://rubinobservatory.org/for-scientists/resources/early-science)
- [NSF funds ZTF to work with Vera Rubin](https://www.ztf.caltech.edu/new/nsf-funds-ztf-to-work-with-vera-rubin.html)
