# Fixtures

- **Real live captures (2026-11-01):** `lsst_detections_live.json`, `ztf_detections_live.json`, `lsst_probabilities_live.json`, `ztf_probabilities_live.json` (plus LSST field shapes in `lsst_objects.json`).
- **Synthetic (schema-derived):** `ztf_objects.json`, `ztf_probabilities.json`, `ztf_classifiers.json`, and the values in `lsst_objects.json`. Kept unchanged so existing unit tests that depend on them remain stable.
