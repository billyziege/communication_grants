# Communication Grants Database

A local search tool for NIH and EU CORDIS grant data, built for research on
communication and science policy funding patterns.

Covers NIH ExPORTER (from a configurable start year) and CORDIS FP7, Horizon 2020,
and Horizon Europe programmes. Full-text search with BM25 relevance ranking.
Results can be saved into named collections and exported/imported as JSON files
for sharing with collaborators.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
   - [Getting the code](#getting-the-code)
   - [Docker](#docker)
2. [Quick Start](#quick-start)
3. [Rebuilding the Database](#rebuilding-the-database)
4. [Sharing Collections](#sharing-collections)
5. [Development](#development)
6. [Project Structure](#project-structure)

---

## Prerequisites

### Getting the code

**Option A — Git** (recommended if you are comfortable with the command line):

```bash
git clone <repository URL>
cd communication-grants
```

This keeps a full version history and lets you pull future updates with `git pull`.

**Option B — Download ZIP** (no tools required):

Open the repository in a browser, click the **`<> Code`** button near the top of the
page, and choose **Download ZIP**. Extract the archive to a folder of your choice.

> **Note:** with the ZIP approach there is no version tracking. To get a newer
> version of the tool you will need to download and extract the ZIP again.

---

### Docker

Docker is required to build the database and run the app. It includes Docker Compose —
no separate install is needed.

**Linux:**
Install Docker Engine and the Compose plugin for your distribution:
https://docs.docker.com/engine/install/

**Windows:**
Install Docker Desktop for Windows:
https://docs.docker.com/desktop/install/windows-install/

After installing, open **PowerShell** or **Windows Terminal**, navigate to the project
folder, and run the commands in the next section from there.

> **Tip (Windows 11):** in File Explorer, right-click the project folder and choose
> **Open in Terminal** to open a terminal already pointed at that folder.

---

## Quick Start

**Step 1 — Configure:**

Linux:
```bash
cp .env.example .env
```

Windows:
```cmd
copy .env.example .env
```

Open `.env` and set `START_YEAR` (default: 2015) if you want a different range.
`DATA_DIR` controls where downloaded files and the database are stored (default: `./data`).

**Step 2 — Build the database** (run once; downloads ~700 MB, takes 10–30 min):

```bash
docker compose --profile build run --rm build-db
```

**Step 3 — Start the app:**

```bash
docker compose up --build
```

The app is available at **http://localhost:3000**. GraphiQL (the interactive API
explorer) is at **http://localhost:8000/graphql**.

---

## Rebuilding the Database

To refresh the data (e.g. after a new CORDIS release):

```bash
docker compose --profile build run --rm build-db
docker compose restart api
```

To force re-download of all source files or back up the previous database before
overwriting, pass the extra flags explicitly:

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

The search interface allows saving grants into named collections. Each collection can
be exported as a `.json` file and shared with collaborators running their own instance.
Collections are identified by stable source IDs (NIH APPLICATION_ID / CORDIS project
ID) and resolve correctly across deployments built from the same source data.

---

## Development

Requires Python 3.11+ with [uv](https://docs.astral.sh/uv/):
`curl -LsSf https://astral.sh/uv/install.sh | sh`

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
