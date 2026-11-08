import React, { Suspense, useState, useEffect, useCallback } from 'react';
import { graphql, useQueryLoader, usePreloadedQuery, fetchQuery } from 'react-relay';
import FilterPanel from '../components/FilterPanel.jsx';
import GrantList, { GrantList_query } from '../components/GrantList.jsx';
import GrantDetailPanel, { GrantDetailPanelQuery } from '../components/GrantDetailPanel.jsx';
import CollectionsPanel from '../components/CollectionsPanel.jsx';
import { GrantCardContent } from '../components/GrantCard.jsx';
import { emptyFilters } from '../lib/facets.js';
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
    $yearMin: Int
    $yearMax: Int
    $country: String
    $programmes: [String!]
    $fundingMin: Float
    $fundingMax: Float
    $first: Int
    $after: String
  ) {
    searchFacets(query: $query) {
      sources
      programmes
      countries
    }
    ...GrantList_query @arguments(
      query: $query
      source: $source
      yearMin: $yearMin
      yearMax: $yearMax
      country: $country
      programmes: $programmes
      fundingMin: $fundingMin
      fundingMax: $fundingMax
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

// ── Filter toggle button ───────────────────────────────────────────────────────

function FunnelIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 14 14"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M1 2h12l-4.5 5.5V12L5.5 10.5V7.5L1 2z" fillRule="evenodd" />
    </svg>
  );
}

// ── Search results container ───────────────────────────────────────────────────

function SearchResultsContainer({
  queryRef,
  onSelectGrant,
  onSave,
  savedIds,
  saveDisabled,
  onFacetsLoaded,
}) {
  const data = usePreloadedQuery(GrantsPageSearchQuery, queryRef);

  useEffect(() => {
    if (data.searchFacets) onFacetsLoaded?.(data.searchFacets);
  }, [data.searchFacets, onFacetsLoaded]);

  return (
    <GrantList
      query={data}
      onSelectGrant={onSelectGrant}
      onSave={onSave}
      savedIds={savedIds}
      saveDisabled={saveDisabled}
    />
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function GrantsPage({ pendingSearch }) {
  const [queryRef, loadQuery] = useQueryLoader(GrantsPageSearchQuery);
  const [detailQueryRef, loadDetailQuery, disposeDetailQuery] = useQueryLoader(GrantDetailPanelQuery);

  const [filters, setFilters] = useState(emptyFilters);
  const [lastQuery, setLastQuery] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('search');
  const [activeCollectionName, setActiveCollectionName] = useState(null);
  const [availableFacets, setAvailableFacets] = useState({ sources: [], programmes: [], countries: [] });

  const handleFacetsLoaded = useCallback(f => setAvailableFacets(f), []);
  const [collections, setCollections] = useState(() => loadCollections());
  const [importError, setImportError] = useState('');

  // Count how many filter dimensions are active
  const activeFilterCount = [
    filters.source != null,
    filters.yearMin != null || filters.yearMax != null,
    filters.country !== '',
    filters.programmes.size > 0,
    filters.fundingMin != null || filters.fundingMax != null,
  ].filter(Boolean).length;

  // When App fires a search from the header, respond to it
  useEffect(() => {
    if (pendingSearch != null) {
      runSearch(pendingSearch.query, emptyFilters());
    }
  }, [pendingSearch]);

  function persistCollections(cols) {
    setCollections(cols);
    saveCollections(cols);
  }

  function filtersToQueryVars(f) {
    return {
      source: f.source || undefined,
      yearMin: f.yearMin ?? undefined,
      yearMax: f.yearMax ?? undefined,
      country: f.country || undefined,
      programmes: f.programmes.size > 0 ? [...f.programmes] : undefined,
      fundingMin: f.fundingMin ?? undefined,
      fundingMax: f.fundingMax ?? undefined,
    };
  }

  function runSearch(query, currentFilters) {
    const f = currentFilters ?? filters;
    setLastQuery(query);
    setAvailableFacets({ sources: [], programmes: [], countries: [] });
    loadQuery(
      { query: query || ' ', ...filtersToQueryVars(f), first: 100 },
      { fetchPolicy: 'network-only' }
    );
    setActiveTab('search');
  }

  function handleApplyFilters(newFilters) {
    setFilters(newFilters);
    setSidebarOpen(false);
    if (lastQuery !== null) {
      runSearch(lastQuery, newFilters);
    }
  }

  function handleResetFilters() {
    const empty = emptyFilters();
    setFilters(empty);
    setSidebarOpen(false);
    if (lastQuery !== null) {
      runSearch(lastQuery, empty);
    }
  }

  function handleSelectGrant(id) {
    loadDetailQuery({ id });
  }

  function handleSave(grant) {
    if (!activeCollectionName) return;
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
      const next = addItemToCollection(collections, activeCollectionName, snapshot);
      persistCollections(next);
    } catch {
      // duplicate — silently ignore
    }
  }

  function handleTabChange(name) {
    setActiveTab(name);
    if (name !== 'search') setActiveCollectionName(name);
  }

  function handleCreateCollection(name) {
    const next = createCollection(collections, name);
    persistCollections(next);
    setActiveTab(name);
    setActiveCollectionName(name);
  }

  function handleDeleteCollection(name) {
    const next = deleteCollection(collections, name);
    persistCollections(next);
    if (activeTab === name) setActiveTab('search');
    if (activeCollectionName === name) setActiveCollectionName(null);
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
    setActiveCollectionName(collectionName);
  }

  const activeCollection = collections.find(c => c.name === activeTab);

  return (
    <div className="flex h-full">
      {/* Collapsible filter sidebar — only shown after a search */}
      {sidebarOpen && queryRef !== null && (
        <div className="flex-shrink-0 w-[280px] border-r border-gray-200 bg-white flex flex-col">
          <FilterPanel
            filters={filters}
            availableSources={availableFacets.sources}
            availableProgrammes={availableFacets.programmes}
            availableCountries={availableFacets.countries}
            onApply={handleApplyFilters}
            onReset={handleResetFilters}
          />
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        {/* Tab bar + collections panel */}
        <CollectionsPanel
          collections={collections}
          activeTab={activeTab}
          activeCollectionName={activeCollectionName}
          onTabChange={handleTabChange}
          onCreateCollection={handleCreateCollection}
          onDeleteCollection={handleDeleteCollection}
          onImportCollection={handleImportCollection}
          importError={importError}
        />

        {/* Filter toggle bar — only visible after first search */}
        {queryRef !== null && activeTab === 'search' && (
          <div className="flex-shrink-0 border-b border-gray-100 px-4 py-2 flex items-center gap-2 bg-white">
            <button
              type="button"
              onClick={() => setSidebarOpen(o => !o)}
              className={`flex items-center gap-1.5 px-2.5 py-1 text-sm rounded-md border transition-colors ${
                sidebarOpen || activeFilterCount > 0
                  ? 'border-blue-400 text-blue-700 bg-blue-50 hover:bg-blue-100'
                  : 'border-gray-200 text-gray-600 bg-white hover:bg-gray-50'
              }`}
              aria-label="Toggle filters"
            >
              <FunnelIcon />
              <span>Filters</span>
              {activeFilterCount > 0 && (
                <span className="ml-0.5 px-1.5 py-0.5 text-xs font-semibold bg-blue-600 text-white rounded-full leading-none">
                  {activeFilterCount}
                </span>
              )}
            </button>
          </div>
        )}

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
                    onSelectGrant={handleSelectGrant}
                    onSave={handleSave}
                    savedIds={new Set()}
                    saveDisabled={activeCollectionName === null}
                    onFacetsLoaded={handleFacetsLoaded}
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
          onClose={disposeDetailQuery}
          onSave={handleSave}
          saveDisabled={activeCollectionName === null}
          activeCollectionName={activeCollectionName}
        />
      </Suspense>
    </div>
  );
}
