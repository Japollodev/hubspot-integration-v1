# HubSpot CRM Importer

Turns a business-card photo (and later, a PDF) into a validated HubSpot contact, with a downloadable PDF summary.
The feature roadmap is in [HubSpot_CRM_Importer_Build_Plan.md](HubSpot_CRM_Importer_Build_Plan.md). This repo currently contains the **boilerplate only**: no build-plan step has been implemented.

| Layer | Stack |
|---|---|
| Frontend | React 19 · TypeScript (strict) · Tailwind CSS v4 · Vite · Vitest |
| Backend | Python 3.12 · FastAPI · pydantic-settings · pytest · ruff · mypy (strict) |
| Tooling | uv · npm (Node 22 via Volta) · Docker · GitHub Actions |

## Prerequisites
- [uv](https://docs.astral.sh/uv/) (installs Python 3.12 automatically)
- Node 22: pinned in `frontend/package.json`. Volta switches to it automatically; otherwise use Node ≥ 20.19.
- Docker (optional)

## Quick start
```bash
cp .env.example .env      # fill in keys as later steps need them
make install
make dev                  # API on :8000, UI on http://localhost:5173
```
The header badge should read **Backend: ok**.

## Common commands
| Command | What it does |
|---|---|
| `make dev` | FastAPI with reload + Vite with HMR (Vite proxies `/api` → :8000) |
| `make check` | Lint, format check, type check and tests for both apps (same as CI) |
| `make format` | Auto-fix formatting |
| `make serve` | Build the frontend, then FastAPI serves it at http://localhost:8000/ |
| `make docker` | Build and run the production container on :8000 |

## How it fits together
- **Production:** one process. FastAPI serves the JSON API under `/api/*` and the built React app (`frontend/dist`) at `/`. Unknown non-API paths fall back to `index.html`; unknown `/api/*` paths return a JSON 404.
- **Development:** Vite serves the UI on :5173 and proxies `/api` to FastAPI on :8000, so frontend code always calls relative `/api/...` URLs.
- **Errors:** every API error uses one shape: `{"error": {"code", "message", "details?"}}`. Raise `AppError` in the backend. The frontend's `apiFetch` turns errors into `ApiError`.
- **Config:** all settings come from env vars or `.env` via [backend/app/core/config.py](backend/app/core/config.py).
- **API docs:** http://localhost:8000/api/docs

## Layout
```
backend/app/
  main.py               app factory, router + static/SPA mounting
  core/                 config, logging, error envelope
  api/router.py         everything mounted under /api
  api/routes/           one module per resource (health.py today)
  schemas/              shared Pydantic models
  services/extraction/  Step 3 & 9: OpenAI extraction, PDF input
  services/hubspot/     Steps 4–5: lookup, create, fill-blank updates
  services/pdf/         Step 6: PDF summary
  db/                   Step 8: SQLite import status
frontend/src/
  lib/api.ts            typed fetch wrapper (all backend calls)
  components/           shared UI
  features/             one folder per feature (Step 1 → features/upload)
```

## Conventions for build-plan steps
- Add API endpoints as `backend/app/api/routes/<name>.py` and register them in `api/router.py`. Step 1's `POST /uploads` is served at **`POST /api/uploads`**.
- Add third-party dependencies in the step that first needs them (`uv add …` / `npm install …`).
- Use the HubSpot **test** account for every CRM operation. Never commit `.env`, uploads or `data/`.
