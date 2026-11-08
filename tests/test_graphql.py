"""tests/test_graphql.py — GraphQL schema tests for Contract 05.

Uses schema.execute_sync() with an in-memory SQLite database — no HTTP
layer, no env-var dependency.
"""
from __future__ import annotations

import json
import sqlite3

import pytest

from db.models import create_schema
from db.sqlite_repository import SQLiteGrantRepository
from api.schema import schema
from api.app import CustomContext
from strawberry import relay


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ctx():
    """In-memory SQLite context with two basic grants."""
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    conn.execute("""
        INSERT INTO grants
          (title, abstract, source, source_id, source_url, metadata)
        VALUES
          ('NIH Grant', 'An NIH abstract', 'nih', 'APP001',
           'https://reporter.nih.gov/project-details/APP001', '{}'),
          ('CORDIS Grant', 'A CORDIS abstract', 'cordis', 'C001',
           'https://cordis.europa.eu/project/id/C001', '{}')
    """)
    conn.execute("INSERT INTO grants_fts(grants_fts) VALUES('rebuild')")
    conn.commit()
    repo = SQLiteGrantRepository(conn)
    return CustomContext(repo=repo)


@pytest.fixture
def ctx_five():
    """In-memory SQLite context with five NIH grants for pagination tests."""
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    for i in range(1, 6):
        conn.execute(
            """
            INSERT INTO grants (title, abstract, source, source_id, source_url, metadata)
            VALUES (?, ?, 'nih', ?, ?, '{}')
            """,
            (f"NIH Grant {i}", f"Abstract {i}", f"APP{i:03d}",
             f"https://reporter.nih.gov/project-details/APP{i:03d}"),
        )
    conn.execute("INSERT INTO grants_fts(grants_fts) VALUES('rebuild')")
    conn.commit()
    repo = SQLiteGrantRepository(conn)
    return CustomContext(repo=repo)


@pytest.fixture
def ctx_full():
    """Context with one fully-populated grant row."""
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    conn.execute("""
        INSERT INTO grants (
            title, abstract, start_date, end_date, funding_amount,
            funding_currency, organization, country,
            source, source_id, source_programme, source_url, metadata
        ) VALUES (
            'Full Grant', 'Full abstract', '2020-01-01', '2022-12-31',
            100000.0, 'USD', 'Test University', 'US',
            'nih', 'FULL001',
            NULL,
            'https://reporter.nih.gov/project-details/FULL001',
            '{"pi_names": "Dr. Test"}'
        )
    """)
    conn.execute("INSERT INTO grants_fts(grants_fts) VALUES('rebuild')")
    conn.commit()
    repo = SQLiteGrantRepository(conn)
    return CustomContext(repo=repo)


def gql(query, ctx, variables=None):
    return schema.execute_sync(query, context_value=ctx, variable_values=variables or {})


# ---------------------------------------------------------------------------
# grants query
# ---------------------------------------------------------------------------


def test_grants_returns_all_rows(ctx):
    result = gql(
        "{ grants { edges { node { title } } totalCount } }",
        ctx,
    )
    assert result.errors is None
    data = result.data["grants"]
    assert data["totalCount"] == 2
    assert len(data["edges"]) == 2
    titles = {e["node"]["title"] for e in data["edges"]}
    assert titles == {"NIH Grant", "CORDIS Grant"}


def test_grants_source_filter_nih(ctx):
    result = gql(
        "{ grants(source: NIH) { edges { node { title } } totalCount } }",
        ctx,
    )
    assert result.errors is None
    data = result.data["grants"]
    assert data["totalCount"] == 1
    assert data["edges"][0]["node"]["title"] == "NIH Grant"


def test_grants_source_filter_cordis(ctx):
    result = gql(
        "{ grants(source: CORDIS) { edges { node { title } } totalCount } }",
        ctx,
    )
    assert result.errors is None
    data = result.data["grants"]
    assert data["totalCount"] == 1
    assert data["edges"][0]["node"]["title"] == "CORDIS Grant"


def test_grants_pagination_first_page(ctx_five):
    result = gql(
        "{ grants(first: 2) { edges { node { title } } pageInfo { hasNextPage endCursor } totalCount } }",
        ctx_five,
    )
    assert result.errors is None
    data = result.data["grants"]
    assert len(data["edges"]) == 2
    assert data["pageInfo"]["hasNextPage"] is True
    assert data["pageInfo"]["endCursor"] is not None


def test_grants_pagination_second_page(ctx_five):
    # Get the first page to get the cursor
    first = gql(
        "{ grants(first: 2) { pageInfo { endCursor } } }",
        ctx_five,
    )
    end_cursor = first.data["grants"]["pageInfo"]["endCursor"]

    # Fetch next page
    second = gql(
        "query($after: String) { grants(first: 2, after: $after) { edges { node { title } } pageInfo { hasNextPage hasPreviousPage } } }",
        ctx_five,
        variables={"after": end_cursor},
    )
    assert second.errors is None
    data = second.data["grants"]
    assert len(data["edges"]) == 2
    assert data["pageInfo"]["hasPreviousPage"] is True


def test_grants_has_next_page_false_on_last_page(ctx_five):
    # Get all 5 at once
    result = gql(
        "{ grants(first: 5) { pageInfo { hasNextPage hasPreviousPage } } }",
        ctx_five,
    )
    assert result.errors is None
    page_info = result.data["grants"]["pageInfo"]
    assert page_info["hasNextPage"] is False
    assert page_info["hasPreviousPage"] is False


def test_grants_has_previous_page_false_on_first_page(ctx_five):
    result = gql(
        "{ grants(first: 2) { pageInfo { hasPreviousPage } } }",
        ctx_five,
    )
    assert result.errors is None
    assert result.data["grants"]["pageInfo"]["hasPreviousPage"] is False


def test_grants_total_count_stable_across_pages(ctx_five):
    first = gql(
        "{ grants(first: 2) { totalCount pageInfo { endCursor } } }",
        ctx_five,
    )
    end_cursor = first.data["grants"]["pageInfo"]["endCursor"]
    total_first = first.data["grants"]["totalCount"]

    second = gql(
        "query($after: String) { grants(first: 2, after: $after) { totalCount } }",
        ctx_five,
        variables={"after": end_cursor},
    )
    total_second = second.data["grants"]["totalCount"]

    assert total_first == 5
    assert total_second == 5


# ---------------------------------------------------------------------------
# search query
# ---------------------------------------------------------------------------


def test_search_returns_relevant_result(ctx):
    result = gql(
        '{ search(query: "NIH") { edges { node { title } } totalCount } }',
        ctx,
    )
    assert result.errors is None
    data = result.data["search"]
    assert data["totalCount"] >= 1
    titles = [e["node"]["title"] for e in data["edges"]]
    assert "NIH Grant" in titles


def test_search_bm25_ordering(ctx):
    """Better FTS match should appear first."""
    # Both rows contain 'abstract' but only NIH Grant title has 'NIH'
    # We test that searching for 'NIH' returns NIH Grant first
    result = gql(
        '{ search(query: "NIH") { edges { node { title } } } }',
        ctx,
    )
    assert result.errors is None
    edges = result.data["search"]["edges"]
    assert len(edges) >= 1
    assert edges[0]["node"]["title"] == "NIH Grant"


def test_search_source_filter(ctx):
    result = gql(
        '{ search(query: "grant", source: CORDIS) { edges { node { title } } totalCount } }',
        ctx,
    )
    assert result.errors is None
    data = result.data["search"]
    assert data["totalCount"] == 1
    assert data["edges"][0]["node"]["title"] == "CORDIS Grant"


def test_search_fts_syntax_error(ctx):
    """Malformed FTS query should return a GraphQL error entry, not raise."""
    result = gql(
        '{ search(query: "AND AND") { edges { node { title } } } }',
        ctx,
    )
    # Should have errors, not crash
    assert result.errors is not None
    assert len(result.errors) >= 1


# ---------------------------------------------------------------------------
# node query
# ---------------------------------------------------------------------------


def test_node_lookup_valid_id(ctx):
    # First get a grant ID via grants query
    grants_result = gql(
        "{ grants { edges { node { id title } } } }",
        ctx,
    )
    assert grants_result.errors is None
    edge = grants_result.data["grants"]["edges"][0]
    node_id = edge["node"]["id"]
    title = edge["node"]["title"]

    # Now look it up via node query
    result = gql(
        "query($id: ID!) { node(id: $id) { id ... on GrantNode { title } } }",
        ctx,
        variables={"id": node_id},
    )
    assert result.errors is None
    assert result.data["node"]["title"] == title


def test_node_missing_id(ctx):
    """node(id: "invalid") should return a GraphQL error, not crash."""
    result = gql(
        '{ node(id: "invalid") { id } }',
        ctx,
    )
    # Should return errors (bad base64 or bad type dispatch), not crash
    assert result.errors is not None


# ---------------------------------------------------------------------------
# grantBySource query
# ---------------------------------------------------------------------------


def test_grant_by_source_found(ctx):
    result = gql(
        '{ grantBySource(source: NIH, sourceId: "APP001") { title } }',
        ctx,
    )
    assert result.errors is None
    assert result.data["grantBySource"]["title"] == "NIH Grant"


def test_grant_by_source_not_found(ctx):
    result = gql(
        '{ grantBySource(source: NIH, sourceId: "MISSING") { title } }',
        ctx,
    )
    assert result.errors is None
    assert result.data["grantBySource"] is None


# ---------------------------------------------------------------------------
# grantsBySource batch lookup query
# ---------------------------------------------------------------------------


def test_grants_by_source_returns_matching_nodes(ctx):
    result = gql(
        """
        {
            grantsBySource(items: [{source: NIH, sourceId: "APP001"}, {source: CORDIS, sourceId: "C001"}]) {
                title
                sourceId
            }
        }
        """,
        ctx,
    )
    assert result.errors is None
    nodes = result.data["grantsBySource"]
    assert len(nodes) == 2
    assert nodes[0]["title"] == "NIH Grant"
    assert nodes[0]["sourceId"] == "APP001"
    assert nodes[1]["title"] == "CORDIS Grant"
    assert nodes[1]["sourceId"] == "C001"


def test_grants_by_source_returns_none_for_missing(ctx):
    result = gql(
        """
        {
            grantsBySource(items: [{source: NIH, sourceId: "APP001"}, {source: NIH, sourceId: "MISSING"}]) {
                title
                sourceId
            }
        }
        """,
        ctx,
    )
    assert result.errors is None
    nodes = result.data["grantsBySource"]
    assert len(nodes) == 2
    assert nodes[0]["title"] == "NIH Grant"
    assert nodes[1] is None


def test_grants_by_source_empty_list(ctx):
    result = gql(
        """
        {
            grantsBySource(items: []) {
                title
            }
        }
        """,
        ctx,
    )
    assert result.errors is None
    assert result.data["grantsBySource"] == []


def test_grants_by_source_mixed_sources(ctx):
    result = gql(
        """
        {
            grantsBySource(items: [{source: NIH, sourceId: "APP001"}, {source: CORDIS, sourceId: "C001"}]) {
                title
                sourceId
            }
        }
        """,
        ctx,
    )
    assert result.errors is None
    nodes = result.data["grantsBySource"]
    assert len(nodes) == 2
    titles = {n["title"] for n in nodes}
    assert titles == {"NIH Grant", "CORDIS Grant"}


# ---------------------------------------------------------------------------
# GrantNode.id GlobalID
# ---------------------------------------------------------------------------


def test_grant_node_id_is_valid_global_id(ctx):
    result = gql(
        "{ grants { edges { node { id } } } }",
        ctx,
    )
    assert result.errors is None
    for edge in result.data["grants"]["edges"]:
        node_id = edge["node"]["id"]
        type_name, id_val = relay.from_base64(node_id)
        assert type_name == "GrantNode"
        assert id_val.isdigit()


# ---------------------------------------------------------------------------
# metadata returned as JSON object
# ---------------------------------------------------------------------------


def test_metadata_returned_as_object(ctx_full):
    result = gql(
        "{ grants { edges { node { metadata } } } }",
        ctx_full,
    )
    assert result.errors is None
    metadata = result.data["grants"]["edges"][0]["node"]["metadata"]
    # metadata should be a dict (deserialized JSON), not a string
    assert isinstance(metadata, dict)
    assert metadata.get("pi_names") == "Dr. Test"


# ---------------------------------------------------------------------------
# Source enum serialization
# ---------------------------------------------------------------------------


def test_source_enum_serializes_as_name(ctx):
    result = gql(
        "{ grants(source: NIH) { edges { node { source } } } }",
        ctx,
    )
    assert result.errors is None
    source_val = result.data["grants"]["edges"][0]["node"]["source"]
    # Must serialize as the enum name ("NIH"), not the value ("nih")
    assert source_val == "NIH"


# ---------------------------------------------------------------------------
# All GrantNode fields round-trip
# ---------------------------------------------------------------------------


def test_grant_node_all_fields_round_trip(ctx_full):
    result = gql(
        """
        {
            grants {
                edges {
                    node {
                        id
                        title
                        abstract
                        startDate
                        endDate
                        fundingAmount
                        fundingCurrency
                        organization
                        country
                        source
                        sourceId
                        sourceProgramme
                        sourceUrl
                        metadata
                    }
                }
            }
        }
        """,
        ctx_full,
    )
    assert result.errors is None
    node = result.data["grants"]["edges"][0]["node"]
    assert node["title"] == "Full Grant"
    assert node["abstract"] == "Full abstract"
    assert node["startDate"] == "2020-01-01"
    assert node["endDate"] == "2022-12-31"
    assert node["fundingAmount"] == 100000.0
    assert node["fundingCurrency"] == "USD"
    assert node["organization"] == "Test University"
    assert node["country"] == "US"
    assert node["source"] == "NIH"
    assert node["sourceId"] == "FULL001"
    assert node["sourceProgramme"] is None
    assert node["sourceUrl"] == "https://reporter.nih.gov/project-details/FULL001"
    assert node["metadata"]["pi_names"] == "Dr. Test"


# ---------------------------------------------------------------------------
# last/before ignored gracefully
# ---------------------------------------------------------------------------


def test_last_before_ignored_gracefully(ctx):
    """grants(last: 2) should not crash; returns a result (empty or first page)."""
    result = gql(
        "{ grants(last: 2) { edges { node { title } } totalCount } }",
        ctx,
    )
    # Must not crash — errors is None or result.data is not None
    assert result.data is not None or result.errors is not None
    # Specifically, should not raise an exception during execution
    # We just verify the call completes without Python exception
