import React, { Suspense, useState, useEffect } from 'react';
import { graphql, useQueryLoader, usePreloadedQuery, fetchQuery } from 'react-relay';
import FilterPanel from '../components/FilterPanel.jsx';
import GrantList, { GrantList_query } from '../components/GrantList.jsx';
import GrantDetailPanel, { GrantDetailPanelQuery } from '../components/GrantDetailPanel.jsx';
import CollectionsPanel from '../components/CollectionsPanel.jsx';
import { GrantCardContent } from '../components/GrantCard.jsx';
import { applyFacets, emptyFacets } from '../lib/facets.js';
import {
  loadCollections,
  saveCollections,
  createCollection,
  deleteCollection,
  addItemToCollection,
} from '../lib/collections.js';
import { parseImportFile } from '../lib/export.js';
import { RelayEnvironment } from '../relay/environment.js';

// ── Relay queries ─────────────────────────────────────────────────────────────

export const GrantsPageSearchQuery = graphql`
  query GrantsPageSearchQuery(
    $query: String!
    $source: Source
    $first: Int
    $after: String
  ) {
    ...GrantList_query @arguments(
      query: $query
      source: $source
      first: $first
      after: $after
    )
  }
`;

const GrantsPageReloadCollectionQuery = graphql`
  query GrantsPageReloadCollectionQuery($items: [GrantLookupInput!]!) {
    grantsBySource(items: $items) {
      id
      title
      organization
      country
      source
      sourceId
      sourceProgramme
      sourceUrl
      startDate
      endDate
      fundingAmount
      fundingCurrency
    }
  }
`;

// ── Error boundary ─────────────────────────────────────────────────────────────

class ErrorBoundary extends React.Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-red-800">
          <p className="font-semibold mb-1">Failed to load grants</p>
          <p className="text-sm">{this.state.error.message}</p>
          <button
            onClick={() => this.setState({ error: null })}
            className="mt-3 text-sm underline hover:no-underline"
          >
            Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

// ── Search results container ───────────────────────────────────────────────────

function SearchResultsContainer({
  queryRef,
  facets,
  onSelectGrant,
  onSave,
  savedIds,
  activeTab,
}) {
  const data = usePreloadedQuery(GrantsPageSearchQuery, queryRef);

  // Build a Set of IDs that pass client-side facets, if any are active
  const hasActiveFacets =
    facets.startYearMin != null ||
    facets.startYearMax != null ||
    (facets.country && facets.country.trim() !== '') ||
    facets.programmes.size > 0 ||
    facets.fundingMin != null ||
    facets.fundingMax != null;

  // We need snapshot data for facet filtering; extract from search edges
  // The GrantList component reads through the fragment so we pass the query root
  // and let GrantList do the pagination. For facet filtering we pass filteredIds.
  // We get edges via the fragment data inside GrantList — but here we need a snapshot.
  // For simplicity, we pass facets to GrantList and it computes the filtered IDs.

  return (
    <GrantList
      query={data}
      facets={hasActiveFacets ? facets : null}
      onSelectGrant={onSelectGrant}
      onSave={onSave}
      savedIds={savedIds}
      activeTab={activeTab}
    />
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function GrantsPage({ pendingSearch, searchValue: externalSearchValue }) {
  const [queryRef, loadQuery] = useQueryLoader(GrantsPageSearchQuery);
  const [detailQueryRef, loadDetailQuery] = useQueryLoader(GrantDetailPanelQuery);

  const [source, setSource] = useState(null);
  const [facets, setFacets] = useState(emptyFacets());
  const [internalSearchValue, setInternalSearchValue] = useState('');
  const [activeTab, setActiveTab] = useState('search');
  const [collections, setCollections] = useState(() => loadCollections());
  const [importError, setImportError] = useState('');

  // When App fires a search from the header, respond to it
  useEffect(() => {
    if (pendingSearch != null) {
      runSearch(pendingSearch.query);
    }
  }, [pendingSearch]);

  function persistCollections(cols) {
    setCollections(cols);
    saveCollections(cols);
  }

  function runSearch(query) {
    loadQuery(
      { query: query || ' ', source: source || undefined, first: 100 },
      { fetchPolicy: 'network-only' }
    );
    setActiveTab('search');
  }

  function handleSearch(query) {
    runSearch(query);
  }

  function handleSelectGrant(id) {
    loadDetailQuery({ id });
  }

  function handleSave(grant) {
    if (activeTab === 'search') return;
    const snapshot = {
      source: grant.source,
      sourceId: grant.sourceId,
      title: grant.title,
      organization: grant.organization ?? null,
      country: grant.country ?? null,
      startDate: grant.startDate ?? null,
      endDate: grant.endDate ?? null,
      fundingAmount: grant.fundingAmount ?? null,
      fundingCurrency: grant.fundingCurrency ?? null,
      sourceProgramme: grant.sourceProgramme ?? null,
      sourceUrl: grant.sourceUrl ?? '',
    };
    try {
      const next = addItemToCollection(collections, activeTab, snapshot);
      persistCollections(next);
    } catch {
      // duplicate — silently ignore
    }
  }

  function handleCreateCollection(name) {
    const next = createCollection(collections, name);
    persistCollections(next);
    setActiveTab(name);
  }

  function handleDeleteCollection(name) {
    const next = deleteCollection(collections, name);
    persistCollections(next);
    if (activeTab === name) setActiveTab('search');
  }

  async function handleImportCollection(file) {
    setImportError('');
    let parsed;
    try {
      parsed = await parseImportFile(file);
    } catch (err) {
      setImportError(err.message);
      return;
    }

    const { collectionName, items } = parsed;

    if (collections.some(c => c.name === collectionName)) {
      setImportError(
        `A collection named '${collectionName}' already exists. Close it first, then re-import.`
      );
      return;
    }

    // Re-fetch grants via grantsBySource (outside component render cycle)
    let result;
    try {
      result = await fetchQuery(RelayEnvironment, GrantsPageReloadCollectionQuery, {
        items: items.map(({ source, sourceId }) => ({
          source: source.toUpperCase(),
          sourceId,
        })),
      }).toPromise();
    } catch (err) {
      setImportError(`Failed to fetch grants: ${err.message}`);
      return;
    }

    const resolved = (result?.grantsBySource ?? []).filter(Boolean);
    if (resolved.length === 0) {
      setImportError('No grants from this file were found in the current database.');
      return;
    }

    let cols = createCollection(collections, collectionName);
    for (const grant of resolved) {
      const snapshot = {
        source: grant.source,
        sourceId: grant.sourceId,
        title: grant.title,
        organization: grant.organization ?? null,
        country: grant.country ?? null,
        startDate: grant.startDate ?? null,
        endDate: grant.endDate ?? null,
        fundingAmount: grant.fundingAmount ?? null,
        fundingCurrency: grant.fundingCurrency ?? null,
        sourceProgramme: grant.sourceProgramme ?? null,
        sourceUrl: grant.sourceUrl ?? '',
      };
      try {
        cols = addItemToCollection(cols, collectionName, snapshot);
      } catch {
        // duplicate — skip
      }
    }

    persistCollections(cols);
    setActiveTab(collectionName);
  }

  const activeCollection = collections.find(c => c.name === activeTab);

  return (
    <div className="flex h-full">
      {/* Filter sidebar */}
      <div className="flex-shrink-0 w-[280px] border-r border-gray-200 bg-white overflow-y-auto">
        <FilterPanel
          source={source}
          onSourceChange={setSource}
          onFacetsChange={setFacets}
          onSearch={() => handleSearch(externalSearchValue ?? internalSearchValue)}
        />
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Tab bar + collections panel */}
        <CollectionsPanel
          collections={collections}
          activeTab={activeTab}
          onTabChange={setActiveTab}
          onCreateCollection={handleCreateCollection}
          onDeleteCollection={handleDeleteCollection}
          onImportCollection={handleImportCollection}
          importError={importError}
        />

        {/* Content area */}
        <div className="flex-1 overflow-y-auto p-6">

          {/* Search tab */}
          {activeTab === 'search' && (
            queryRef == null ? (
              <div className="flex items-center justify-center h-full min-h-48">
                <p className="text-gray-400 italic text-sm" data-testid="empty-search-state">
                  Enter keywords in the search bar and click Search to find grants.
                </p>
              </div>
            ) : (
              <ErrorBoundary>
                <Suspense
                  fallback={
                    <div
                      className="text-center text-gray-400 py-16 text-sm"
                      data-testid="loading-state"
                    >
                      Loading grants…
                    </div>
                  }
                >
                  <SearchResultsContainer
                    queryRef={queryRef}
                    facets={facets}
                    onSelectGrant={handleSelectGrant}
                    onSave={handleSave}
                    savedIds={new Set()}
                    activeTab={activeTab}
                  />
                </Suspense>
              </ErrorBoundary>
            )
          )}

          {/* Collection tab */}
          {activeTab !== 'search' && activeCollection && (
            activeCollection.items.length === 0 ? (
              <div className="flex items-center justify-center h-full min-h-48">
                <p className="text-gray-400 italic text-sm">
                  This collection is empty. Save grants from search results to add them here.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {activeCollection.items.map(item => (
                  <GrantCardContent
                    key={`${item.source}:${item.sourceId}`}
                    grant={{
                      ...item,
                      id: `${item.source}:${item.sourceId}`,
                    }}
                    onSelect={() => {}}
                    onSave={null}
                    isSaved={false}
                    saveDisabled={false}
                  />
                ))}
              </div>
            )
          )}
        </div>
      </div>

      {/* Detail panel */}
      <Suspense fallback={null}>
        <GrantDetailPanel
          queryRef={detailQueryRef}
          onClose={() => loadDetailQuery(null)}
          onSave={handleSave}
          saveDisabled={activeTab === 'search'}
        />
      </Suspense>
    </div>
  );
}
