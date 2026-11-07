# Communication Grant Data Access

A local search tool for NIH and EU grant funding data, built to support research on communication and policy funding patterns.

Queries NIH RePORTER live via its public API and searches a local SQLite database loaded from CORDIS bulk downloads (Horizon Europe, Horizon 2020, FP7). Both sources are exposed through a unified GraphQL interface.

> See `docs/communication_grant_data_access.md` for full architecture rationale and implementation roadmap.

---

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/) (v2+)

---

## Quick Start

```bash
docker compose up
```

- GraphQL API: `http://localhost:8000/graphql`
- Frontend: `http://localhost:3000`

---

## Loading EU/CORDIS Data

CORDIS data requires a one-time bulk download and load. After the containers are running:

```bash
docker compose run api python load_cordis.py
```

This downloads the Horizon Europe, Horizon 2020, and FP7 bulk datasets and loads them into the local SQLite database. The database persists in a named Docker volume and survives container rebuilds.

---

## Querying

Both NIH and CORDIS data are queryable through the GraphQL endpoint at `http://localhost:8000/graphql`. The schema is self-documenting — use the GraphQL explorer in the browser to introspect available queries and fields.

---

## Project Structure

```
.
├── docs/
│   ├── communication_grant_data_access.md   # Architecture and roadmap
│   └── contracts/                           # Implementation contracts (one per component)
├── api/                                     # FastAPI + Strawberry GraphQL server
├── web/                                     # React + Relay frontend
├── docker-compose.yml
└── README.md
```

---

## Development Status

Pre-implementation. Contracts are being written; see `docs/contracts/`.
