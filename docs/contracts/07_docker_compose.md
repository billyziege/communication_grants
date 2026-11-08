# Contract 07 — Docker Compose & README

**Status:** Ready for implementation  
**Depends on:** All prior contracts (00–06)  
**This is the final contract.**

---

## 1. Purpose and Scope

Wire the full stack into a local Docker Compose deployment and write the project README. Commit all untracked work (contracts 00–07) as a single initial-implementation commit.

**In scope:**
- `Dockerfile.api` — Python API image
- `Dockerfile.frontend` — Multi-stage Node build → Nginx image
- `nginx.conf` — Nginx reverse-proxy config
- `docker-compose.yml` — Three services: `api`, `frontend`, `db-builder`
- `.env.example` — Template for local configuration
- `.dockerignore`
- `README.md` — Project overview, setup, and usage
- Git commit of all untracked work

**Out of scope:**
- TLS / HTTPS
- Production hardening (rate limiting, auth, etc.)
- CI/CD pipelines

---

## 2. `Dockerfile.api`

```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml .
RUN python3 -m pip install --no-cache-dir .
COPY db/ db/
COPY api/ api/
ENV PYTHONUNBUFFERED=1
CMD ["python3", "-m", "uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

The image installs only the runtime dependencies listed in `pyproject.toml`. It does not include test dependencies or the `frontend/` or `docs/` directories.

---

## 3. `Dockerfile.frontend`

Multi-stage build: Node compiles the Vite + Relay app; Nginx serves the static output.

```dockerfile
# ── Stage 1: build ──────────────────────────────────────────────────────────
FROM node:20-slim AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: serve ──────────────────────────────────────────────────────────
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

If `frontend/package-lock.json` does not exist, run `npm install` in `frontend/` first to generate it, then commit it.

---

## 4. `nginx.conf`

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    # Proxy GraphQL requests to the API service
    location /graphql {
        proxy_pass         http://api:8000/graphql;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_read_timeout 60s;
    }

    # SPA fallback — all other routes serve index.html
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

---

## 5. `docker-compose.yml`

```yaml
services:

  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    environment:
      GRANTS_DB_PATH: /data/grants.db
    volumes:
      - grants_data:/data:ro
    ports:
      - "8000:8000"   # exposes GraphiQL at http://localhost:8000/graphql
    restart: unless-stopped
    depends_on: []    # db-builder is a one-shot; api starts independently

  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
    ports:
      - "3000:80"     # app available at http://localhost:3000
    depends_on:
      - api
    restart: unless-stopped

  db-builder:
    build:
      context: .
      dockerfile: Dockerfile.api   # reuses the same image
    profiles:
      - build
    environment:
      GRANTS_DB_PATH: /data/grants.db
    volumes:
      - grants_data:/data
      - ${DATA_DIR:-./data}:/raw   # downloaded ZIPs and manifest land here on the host
    command: >
      python3 db/build_db.py
        --start-year ${START_YEAR:-2015}
        --data-dir /raw
        --db-path /data/grants.db

volumes:
  grants_data:
    driver: local
```

**Volume notes:**
- `grants_data` is the named Docker volume holding the SQLite database. It persists across `docker compose down` (use `docker compose down -v` to remove it).
- `${DATA_DIR:-./data}` is a host directory where downloaded ZIPs and `manifest.json` are cached. It defaults to `./data` and is bind-mounted read-write into `db-builder` so downloads survive container restarts.
- The `api` service mounts `grants_data` read-only (`:ro`) — it cannot modify the database.

---

## 6. `.env.example`

```bash
# Copy to .env and edit before running docker compose.

# Directory on the HOST where downloaded ZIPs and manifest.json are cached.
# Created automatically on first db-builder run if it doesn't exist.
DATA_DIR=./data

# First fiscal year to include in the database build (NIH ExPORTER goes back to 2000).
START_YEAR=2015
```

The actual `.env` file must be listed in `.gitignore`. `.env.example` is committed.

---

## 7. `.dockerignore`

```
.git
.env
data/
frontend/node_modules/
frontend/dist/
__pycache__/
*.pyc
*.pyo
.pytest_cache/
tests/
docs/
```

---

## 8. `pyproject.toml` — runtime dependencies

Ensure `pyproject.toml` lists all runtime dependencies (not just test deps). The `Dockerfile.api` runs `pip install .` to install them. At minimum:

```toml
[project]
name = "communication-grants"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "strawberry-graphql[fastapi]>=0.341",
    "uvicorn[standard]>=0.30",
]

[project.optional-dependencies]
dev = ["pytest"]
```

Read the existing `pyproject.toml` first and update it; do not overwrite fields that are already correct.

---

## 9. `README.md`

Write a clear, practical README for a research audience (not a software engineering audience). Sections:

### 9.1 Title and description

```markdown
# Communication Grants Database

A local search tool for NIH and EU CORDIS grant data, built for research on
communication and science policy funding patterns.

Covers NIH ExPORTER (from a configurable start year) and CORDIS FP7, Horizon 2020,
and Horizon Europe programmes. Full-text search with BM25 relevance ranking.
Results can be saved into named collections and exported/imported as JSON files
for sharing with collaborators.
```

### 9.2 Prerequisites

- Docker and Docker Compose (v2)
- Python 3.11+ (for the database build step, run outside Docker)

### 9.3 Quick start

Three steps:

**Step 1 — Install Python dependencies (for the build pipeline):**
```bash
python3 -m pip install -e .
```

**Step 2 — Build the database:**
```bash
mkdir -p data
python3 db/build_db.py \
    --start-year 2015 \
    --data-dir ./data \
    --db-path ./data/grants.db
```

Note: This step downloads several hundred MB of data from NIH and CORDIS. It takes 10–30 minutes depending on network speed. The `--start-year` flag controls how far back NIH data goes (CORDIS data is always all three programmes).

**Step 3 — Start the app:**
```bash
# Copy .env.example to .env (defaults are fine for most setups)
cp .env.example .env

# Load the named volume and start services
docker compose --profile build run db-builder   # copies grants.db into the Docker volume
docker compose up --build
```

The app is available at **http://localhost:3000**. GraphiQL (the interactive API explorer) is at **http://localhost:8000/graphql**.

### 9.4 Rebuilding the database

To refresh the data (e.g. after a new CORDIS release):

```bash
# Re-run the build pipeline on the host
python3 db/build_db.py --start-year 2015 --data-dir ./data --db-path ./data/grants.db

# Reload the Docker volume
docker compose --profile build run db-builder
docker compose restart api
```

Use `--force-redownload` to re-download all source files, or `--backup-db` to preserve the previous database before overwriting.

### 9.5 Sharing collections

The search interface allows saving grants into named collections. Each collection can be exported as a `.json` file and shared with collaborators running their own instance. Collections are identified by stable source IDs (NIH APPLICATION_ID / CORDIS project ID) and resolve correctly across deployments built from the same source data.

### 9.6 Development

```bash
# Run backend tests
python3 -m pytest

# Run frontend tests
cd frontend && npm test

# Run the backend locally (without Docker)
GRANTS_DB_PATH=./data/grants.db python3 -m uvicorn api.app:app --reload

# Run the frontend dev server (proxies /graphql to localhost:8000)
cd frontend && npm run dev
```

### 9.7 Project structure (brief)

```
db/             — data acquisition, normalization, build pipeline, SQLite query layer
api/            — FastAPI + Strawberry GraphQL schema
frontend/       — React + Relay SPA
docs/           — roadmap and implementation contracts
data/           — downloaded source files and built database (gitignored)
```

---

## 10. Git commit

After all files are created and tests pass, commit everything:

**Files to stage:**
- All files under `db/`, `api/`, `frontend/`, `docs/`, `tests/`
- `pyproject.toml`
- `docker-compose.yml`, `Dockerfile.api`, `Dockerfile.frontend`, `nginx.conf`
- `.env.example`, `.dockerignore`
- `README.md`

**Do NOT stage:**
- `.env` (if it exists)
- `data/` directory
- `frontend/node_modules/`
- `frontend/dist/`
- Any `__pycache__/` directories

Commit message:

```
Implement communication grants search tool (contracts 00–07)

Data pipeline: NIH ExPORTER bulk download + gap fill via RePORTER API v2;
CORDIS FP7, Horizon 2020, and Horizon Europe bulk ZIPs. SQLite FTS5 for
full-text search with BM25 ranking.

Stack: FastAPI + Strawberry GraphQL (Relay-compatible) → SQLiteGrantRepository
→ React 18 + Relay SPA with named collections, export/import, and faceted
search. Docker Compose for local deployment.

256 Python tests, 50 frontend (Vitest) tests.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

Verify with `git status` after staging to confirm no secrets or large binaries are included before committing.

---

## 11. Verification checklist

Before reporting back, confirm:
- [ ] `docker compose config` runs without errors (validates the compose file)
- [ ] `python3 -m pytest -q` — 256 passing
- [ ] `cd frontend && npm test` — 50 passing
- [ ] `git log --oneline -1` shows the commit
- [ ] `git status` is clean (no untracked or modified files except `data/` and `frontend/node_modules/`)
