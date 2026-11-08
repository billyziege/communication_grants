import React from 'react';
import { usePaginationFragment, graphql } from 'react-relay';
import GrantCard from './GrantCard.jsx';
import { applyFacets } from '../lib/facets.js';

export const GrantList_query = graphql`
  fragment GrantList_query on Query
  @argumentDefinitions(
    query: { type: "String!" }
    source: { type: "Source" }
    first: { type: "Int", defaultValue: 100 }
    after: { type: "String" }
  )
  @refetchable(queryName: "GrantListPaginationQuery") {
    search(query: $query, source: $source, first: $first, after: $after)
      @connection(key: "GrantList_search") {
      totalCount
      edges {
        node {
          id
          startDate
          country
          sourceProgramme
          fundingAmount
          fundingCurrency
          ...GrantCard_grant
        }
      }
    }
  }
`;

export default function GrantList({
  query: queryRef,
  facets,
  onSelectGrant,
  onSave,
  savedIds,
  activeTab,
}) {
  const { data, loadNext, isLoadingNext, hasNext } = usePaginationFragment(
    GrantList_query,
    queryRef
  );

  const totalCount = data.search?.totalCount ?? 0;
  const edges = data.search?.edges ?? [];

  // Apply client-side facets if any are active
  const displayedEdges = facets != null
    ? edges.filter(e => {
        const { startDate, country, sourceProgramme, fundingAmount, fundingCurrency } = e.node;
        const snapshot = { startDate, country, sourceProgramme, fundingAmount, fundingCurrency };
        return applyFacets([snapshot], facets).length > 0;
      })
    : edges;

  const displayedCount = displayedEdges.length;
  const isFiltered = facets != null && displayedCount !== edges.length;

  if (edges.length === 0) {
    return (
      <p className="text-gray-400 italic text-sm text-center py-16">
        No grants found. Try different keywords or filters.
      </p>
    );
  }

  return (
    <div>
      {/* Count summary */}
      <p className="text-xs text-gray-500 mb-3">
        Showing{' '}
        <span className="font-medium text-gray-700">{displayedCount}</span>
        {isFiltered && (
          <span> (filtered from {edges.length})</span>
        )}{' '}
        of{' '}
        <span className="font-medium text-gray-700">{totalCount}</span>{' '}
        database match{totalCount !== 1 ? 'es' : ''}
      </p>

      {/* Grant cards */}
      <div className="space-y-3">
        {displayedEdges.map(edge => (
          <GrantCard
            key={edge.node.id}
            grant={edge.node}
            onSelect={onSelectGrant}
            onSave={onSave}
            isSaved={savedIds?.has(edge.node.id) ?? false}
            saveDisabled={activeTab === 'search'}
            saveTooltip="Create a collection tab first"
          />
        ))}
      </div>

      {/* Load more */}
      {hasNext && (
        <div className="mt-4 text-center">
          <button
            type="button"
            disabled={isLoadingNext}
            onClick={() => loadNext(100)}
            className="px-4 py-2 text-sm font-medium border border-gray-200 text-gray-600 rounded-md hover:bg-gray-50 disabled:opacity-50"
          >
            {isLoadingNext ? 'Loading…' : 'Load more'}
          </button>
        </div>
      )}
    </div>
  );
}
