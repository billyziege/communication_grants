"""api/app.py — FastAPI application wiring for the communication grants API.

Requires the GRANTS_DB_PATH environment variable to be set to the path of
the SQLite database file.
"""
from __future__ import annotations

import os
import sqlite3

import strawberry
from fastapi import FastAPI
from strawberry.fastapi import BaseContext, GraphQLRouter

from api.schema import schema
from db.sqlite_repository import SQLiteGrantRepository


class CustomContext(BaseContext):
    def __init__(self, repo: SQLiteGrantRepository) -> None:
        super().__init__()
        self.repo = repo


def get_context() -> CustomContext:
    db_path = os.environ["GRANTS_DB_PATH"]
    conn = sqlite3.connect(db_path, check_same_thread=False)
    repo = SQLiteGrantRepository(conn)
    return CustomContext(repo=repo)


graphql_router = GraphQLRouter(
    schema,
    context_getter=get_context,
    graphql_ide="graphiql",
)

app = FastAPI(title="Communication Grants API")
app.include_router(graphql_router, prefix="/graphql")
