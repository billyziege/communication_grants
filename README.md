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
- ~25 GB free disk space (source file cache and SQLite database)

---

## Quick Start

**Step 1 — Configure:**

```bash
cp .env.example .env
```

Open `.env` and set `START_YEAR` (default: 2015) if you want a different range. `DATA_DIR` controls where downloaded files and the database are stored (default: `./data`).

**Step 2 — Build the database** (run once; downloads ~700 MB, takes 10–30 min):

```bash
docker compose --profile build run --rm build-db
```

**Step 3 — Start the app:**

```bash
docker compose up --build
```

The app is available at **http://localhost:3000**. GraphiQL (the interactive API explorer) is at **http://localhost:8000/graphql**.

---

## Rebuilding the Database

To refresh the data (e.g. after a new CORDIS release):

```bash
docker compose --profile build run --rm build-db
docker compose restart api
```

To force re-download of all source files or back up the previous database before overwriting, pass the extra flags explicitly:

```bash
docker compose --profile build run --rm build-db \
    python3 -m db.build_db \
    --start-year 2015 \
    --data-dir /data \
    --db-path /data/grants.db \
    --force-redownload \
    --backup-db
```

---

## Sharing Collections

The search interface allows saving grants into named collections. Each collection can be exported as a `.json` file and shared with collaborators running their own instance. Collections are identified by stable source IDs (NIH APPLICATION_ID / CORDIS project ID) and resolve correctly across deployments built from the same source data.

---

## Development

Requires Python 3.11+ with [uv](https://docs.astral.sh/uv/): `curl -LsSf https://astral.sh/uv/install.sh | sh`

```bash
# Install dependencies (including dev extras)
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
