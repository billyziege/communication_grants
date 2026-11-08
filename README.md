# Communication Grants Database

A local search tool for NIH and EU CORDIS grant data, built for research on
communication and science policy funding patterns.

Covers NIH ExPORTER (from a configurable start year) and CORDIS FP7, Horizon 2020,
and Horizon Europe programmes. Full-text search with BM25 relevance ranking.
Results can be saved into named collections and exported/imported as JSON files
for sharing with collaborators.

---

## Prerequisites

- Docker and Docker Compose (v2)
- Python 3.11+ with [uv](https://docs.astral.sh/uv/) (for the database build step, run outside Docker)

Install uv if you don't have it: `curl -LsSf https://astral.sh/uv/install.sh | sh`

---

## Quick Start

**Step 1 — Install Python dependencies (for the build pipeline):**

```bash
uv sync
```

**Step 2 — Build the database:**

```bash
mkdir -p data
uv run python3 -m db.build_db \
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

---

## Rebuilding the Database

To refresh the data (e.g. after a new CORDIS release):

```bash
# Re-run the build pipeline on the host
uv run python3 -m db.build_db --start-year 2015 --data-dir ./data --db-path ./data/grants.db

# Reload the Docker volume
docker compose --profile build run db-builder
docker compose restart api
```

Use `--force-redownload` to re-download all source files, or `--backup-db` to preserve the previous database before overwriting.

---

## Sharing Collections

The search interface allows saving grants into named collections. Each collection can be exported as a `.json` file and shared with collaborators running their own instance. Collections are identified by stable source IDs (NIH APPLICATION_ID / CORDIS project ID) and resolve correctly across deployments built from the same source data.

---

## Development

```bash
# Install dependencies
uv sync

# Run backend tests
uv run pytest

# Run frontend tests
cd frontend && npm test

# Run the backend locally (without Docker)
GRANTS_DB_PATH=./data/grants.db uv run uvicorn api.app:app --reload

# Run the frontend dev server (proxies /graphql to localhost:8000)
cd frontend && npm run dev
```

---

## Project Structure

```
db/             — data acquisition, normalization, build pipeline, SQLite query layer
api/            — FastAPI + Strawberry GraphQL schema
frontend/       — React + Relay SPA
docs/           — roadmap and implementation contracts
data/           — downloaded source files and built database (gitignored)
```
