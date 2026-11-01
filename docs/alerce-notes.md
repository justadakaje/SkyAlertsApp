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

### Probability (both surveys, confirmed live 2026-11-01)
`classifier_name`, `classifier_version`, `class_name`, `probability`, `ranking`.
- **LSST:** `classifier_version` is returned as an **integer** on `/probability_api/probability` (e.g. `1`, `201`, `202` — whereas `list_objects` returns a string like `"2.0.2"`). Coerce `classifier_version` to text. Classifiers seen: `nuclear_classifier`, `stamp_classifier_rubin_beta`, `stamp_classifier_rubin_beta_20260421`.
- **ZTF:** `/ztf/v1/objects/{oid}/probabilities` returns rows across all historical `(classifier_name, classifier_version)` pairs (~26 combos / ~338 rows on a multi-year object), including `lc_classifier`, `lc_classifier_top`, `lc_classifier_transient`, `lc_classifier_periodic`, `lc_classifier_stochastic`, `lc_classifier_BHRF_forced_phot*`, `LC_classifier_ATAT_forced_phot(beta)`, `LC_classifier_BHRF_forced_phot(beta)`, `stamp_classifier`, and `stamp_classifier_2025_beta`. Keep only the top 3 (`ranking <= 3`) per `(classifier_name, classifier_version)` to bound storage.

### Detections (confirmed live 2026-11-01)
- **ZTF (`/ztf/v1/objects/{oid}/detections`):** rows have **no `measurement_id` and no `oid`**. The unique detection ID is `candid` (string, e.g. `"714503484115010001"`). Band is `fid` (`1`=`g`, `2`=`r`, `3`=`i`). Photometry is `magpsf` and `sigmapsf` (plus `magpsf_corr`, `sigmapsf_corr`, `sigmapsf_corr_ext`, `magap`, `sigmagap`, `magapbig`, `sigmagapbig`, `diffmaglim`). Other fields: `tid`, `mjd`, `pid`, `isdiffpos` (`1`/`-1`), `nid`, `distnr`, `ra`, `dec`, `rb`, `rbversion`, `drb` (sometimes omitted on older/unscored rows), `rfid`, `has_stamp`, `corrected`, `dubious`, `step_id_corr`, `phase`, `parent_candid`.
- **LSST (`/lightcurve_api/detections?survey_id=lsst&oid={oid}`):** `oid` (int64), `measurement_id` (int64), `mjd`, `band` (int) + `band_map` (`{"6":"u","1":"g","2":"r","3":"i","4":"z","5":"y"}`), `psfFlux` and `psfFluxErr` (difference flux in nJy — **can be negative** when `isNegative` is true, so only convert to AB mag when `psfFlux > 0`), `scienceFlux`, `scienceFluxErr`, `templateFlux`, `templateFluxErr`, `apFlux`, `apFluxErr`, `snr`, `psfFlux_flag`, `isNegative`, `has_stamp`, plus astrometry/shape/dipole/pixel flags (~100 keys per row; store a slim whitelist in `detections.raw`).

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

## LSST volume probe — 2026-11-01 ~19:35 UTC (local, ~20 requests at ≤1 req/s)

Basis for decision #28.
- **The unfiltered list is far too deep to page.** Newest-first at `page_size=100`:
  - page 1 is at `lastmjd` 61344.3188
  - page 20 is at 61344.22
  - page 100 is at 61344.19
  - page 250 is at 61344.11

  That's 25,000 rows within ~5 h of one night, so a full night is roughly 400–600 pages. Deep pages take 1.1–1.8 s each.
- **Rows repeat per classifier.** An unfiltered page holds only ~50–90 distinct `oid`s, because each object comes back once per stamp classifier (`stamp_classifier_rubin_beta_20260421` and the older `stamp_classifier_rubin_beta`).
- **Ties are huge.** A single Rubin visit puts hundreds of rows on the same `lastmjd`: pages 50 and 100 each sat on a single value. Offset paging inside a tie group isn't guaranteed stable.
- **Class mix** (1,662 objects from the newest pages): AGN 50%, bogus 32%, asteroid 14%, VS 4%, SN 1.3%.
- **`class_name` needs `classifier`.** Without it the API answers HTTP 400 `class_name needs a classifier: pass classifier too.`. With both, the rows are top-class (`ranking` 1) and one per object.
- **SN per night:** `stamp_classifier_rubin_beta_20260421` + `SN` covered night 61344 in pages 1–4. Night 61343 took ≥8 pages. The older classifier lags: its page 1 spans 61343.08–61344.28.
- **ZTF is a firehose too.** The unfiltered `stamp_classifier` page 1 spans only 61342.5536–61342.5546, about 1.5 min of data, and 20 pages reach about 17 min back. By class (`classifier` + `class`):
  - stamp SN: page 1 spans 1.1 d, page 5 reaches 5.3 d back
  - lc SNIa: page 1 spans 8.4 d
  - lc SNIbc: 3.4 d
  - lc SNII: 1.5 d
  - lc SLSN: 3.0 d
  - lc CV/Nova: 1.0 d

  `CV/Nova` works as a query value.
- **Freshness (open item 4):** at 19:35 UTC the newest LSST row (61344.3188, 2026-10-31 07:39 UTC) was ~36 h old. The night ending 2026-11-01 ~10:00 UTC wasn't in ALeRCE yet. ZTF's newest was 61342.55 (~78 h).

## Open items to verify on first live run
1. ~~LSST `list_objects` response field names and pagination keys.~~ Done (see above).
2. Max accepted `page_size` on both APIs.
3. Whether either API returns 429 / `Retry-After` under load.
4. ~~Actual freshness: lag between `lastmjd` and wall clock for newest objects, per survey.~~ LSST ~23–36 h, ZTF ≥65 h (see probes above).
5. LSST classifier names present in probability responses.

## Sources
- [ALeRCE Python client docs](https://alerce.readthedocs.io/en/latest/apis.html), [Models](https://alerce.readthedocs.io/en/latest/models.html), [Migration guide](https://alerce.readthedocs.io/en/latest/migration_guide.html)
- `alerce` 2.3.1 wheel: `alerce/default_config.json`, `ms_search.py`, `ztf_search.py`
- [ALeRCE API docs](https://alerceapi.readthedocs.io/)
- [ALeRCE is now live processing Rubin alerts](https://community.lsst.org/t/alerce-is-now-live-processing-rubin-alerts/11632)
- [Rubin Early Science Program](https://rubinobservatory.org/for-scientists/resources/early-science)
- [NSF funds ZTF to work with Vera Rubin](https://www.ztf.caltech.edu/new/nsf-funds-ztf-to-work-with-vera-rubin.html)
