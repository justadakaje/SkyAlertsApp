# `skyalerts_digest` — Weekly Sky Alerts Digest

Phase 3 groundwork for the weekly Sky Alerts digest. Selects notable events from Postgres over a 7-day window and renders plain-English Markdown and HTML summaries (no email delivery yet).

## Modules

- `skyalerts_digest/classes.py`: ALeRCE class metadata (`KNOWN`, `GROUPS`, `TRANSIENT_CLASSES`, `LOW_PRIORITY_CLASSES`, `ARTIFACT_CLASS`, `class_info`, `group_of`), ported verbatim from `web/lib/classes.ts`.
- `skyalerts_digest/select.py`: `select_digest(conn, week_end)` — parameterized read-only SQL queries over `[week_end - 7 days, week_end]` returning frozen dataclasses (`Digest`, `DigestObject`, `SolarSystemSection`, `WeekStats`, `GroupCount`):
  - **Headliners:** up to 5 highest-confidence transient-tier objects (`SN`, `SNIa`, `SNIbc`, `SNII`, `SLSN`, `TDE`, `KN`, `CV/Nova`) first detected in the week (`top_probability DESC`, `lastmjd DESC`).
  - **Brightest new:** up to 3 objects first detected in the week with the brightest detection (`min(mag)` in `detections`), excluding `bogus` and `asteroid`. Omitted when there are no magnitude detections.
  - **Solar system:** total count of `asteroid` objects first detected in the week plus up to 3 examples.
  - **Week in numbers:** new objects by class group, total non-artifact objects tracked, and light-curve points stored.
  - `bogus` artifacts are excluded everywhere.
- `skyalerts_digest/render.py`: `render_markdown(digest)` and `render_html(digest)` — plain-English summaries with class blurbs, object links (`https://sky.henseler.app/objects/<survey>/<oid>`), full `html.escape` sanitization on all upstream values, and a friendly "quiet week" message when no new events were recorded.
- `skyalerts_digest/__main__.py`: CLI entrypoint (`python -m skyalerts_digest`).

## Usage

Render Markdown for the 7 days ending `2026-11-01T00:00:00Z`:

```bash
DATABASE_URL=postgresql://... uv --directory digest run python -m skyalerts_digest --week-end 2026-11-01
```

Render HTML:

```bash
DATABASE_URL=postgresql://... uv --directory digest run python -m skyalerts_digest --week-end 2026-11-01 --html
```

## Lint & Tests

```bash
uv --directory digest run ruff check .
uv --directory digest run ruff format .
uv --directory digest run pytest -q
```
