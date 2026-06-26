# NetGuard

A network intrusion-detection demo application, built as a set of microservices
to exercise a GitOps-driven DevOps platform end to end (per-service CI, container
scanning, progressive delivery, observability, and AI-assisted recovery).

A LightGBM model classifies network flows (NSL-KDD); results stream live to a
React dashboard, and an LLM-based AIOps engine diagnoses Kubernetes incidents.

## Architecture

Five services + Redis + PostgreSQL. The full design — diagrams, data flows, and
the Redis bus contract — is in [`docs/04-microservices-architecture.md`](docs/04-microservices-architecture.md).

| Service | Responsibility |
|---|---|
| `frontend` | React dashboard + nginx edge router (the only public entry) |
| `backend-api` | dashboard gateway: live `/ws`, metrics, Prometheus/Loki proxies |
| `inference` | LightGBM scoring (`/predict`, `/model-info`) |
| `collector` | NSL-KDD replay / synthetic traffic / attack injection → Redis |
| `aiops-engine` | incident diagnosis pipeline (Triage→Evidence→RCA→Postmortem) |

Data path: `collector → inference → Redis → backend-api → browser`.

## Quickstart

With Docker:

```bash
cp .env.example .env     # set GROQ_API_KEY for AIOps diagnosis; the rest runs as-is
docker compose up --build
# open http://localhost:8080
```

Without Docker (needs python3, redis-server, node/npm):

```bash
export GROQ_API_KEY=...   # optional, only for AIOps diagnosis
./scripts/dev.sh
# open http://localhost:3000   (Ctrl-C to stop)
```

## Development

Each service is self-contained and independently tested (no model/Redis/Groq/
cluster needed — tests use injected fakes):

```bash
cd services/<service>
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest      # unit + API tests
.venv/bin/ruff check .          # lint
```

## Repository layout

```
services/
  inference/      collector/      backend-api/      aiops-engine/
frontend/         React app + nginx edge router
docs/             architecture & design
deploy/           postgres schema (compose)
.github/          per-service CI (lint, test, hadolint, build, Trivy)
docker-compose.yml
```

## Configuration

All configuration is via environment variables (`pydantic-settings`). Non-secret
values have safe defaults; **secrets have no default and are never committed** —
see [`.env.example`](.env.example). Containers run as a non-root user.
