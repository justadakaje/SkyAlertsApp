# Sky Alerts App

Astronomy alerts from the [ALeRCE](https://alerce.science) broker (ZTF + Vera C. Rubin / LSST), stored in Neon Postgres and served at **https://sky.henseler.app**.

- Public dashboard of fresh sky events (supernovae, variables, solar-system objects)
- Owner-only `/admin` (GitHub OAuth, allowlisted by GitHub user ID)
- Weekly plain-English digest email via Resend
- Weekly "what the sky did this week" podcast segment export

The spec is the source of truth: [`docs/SPEC.md`](docs/SPEC.md). Design decisions: [`docs/decisions.md`](docs/decisions.md). ALeRCE API findings: [`docs/alerce-notes.md`](docs/alerce-notes.md).

## Layout

| Path | Lane | Contents |
|---|---|---|
| `ingest/` | Data | ALeRCE client, exploration script, ingest job |
| `db/` | Database | Schema, migrations (Phase 1) |
| `web/` | Frontend | Next.js app (Phase 2) |
| `digest/` | Digest & Content | Weekly digest + podcast export (Phase 3–4) |
| `.github/` | DevOps | CI, CodeQL, Dependabot, scheduled jobs |
| `docs/` | Orchestrator | Spec, decisions, notes, security checklist |

## Quick start (ingest)

```bash
cd ingest
uv sync --frozen
uv run pytest
uv run python -m skyalerts_ingest.explore --survey ztf --limit 25
```

The exploration script needs outbound HTTPS to `api.alerce.online` / `api-lsst.alerce.online`. It can also be run on GitHub Actions via the **Explore ALeRCE** workflow (manual dispatch); the summary is posted to the job summary and uploaded as an artifact.

## Security

Security is a release gate (see SPEC §Security and [`docs/security-checklist.md`](docs/security-checklist.md)). Never commit secrets — all credentials live in Vercel / GitHub encrypted environment variables.
