import React from 'react';
import { usePaginationFragment, graphql } from 'react-relay';
import GrantCard from './GrantCard.jsx';

export const GrantList_query = graphql`
  fragment GrantList_query on Query
  @argumentDefinitions(
    query: { type: "String!" }
    source: { type: "Source" }
    yearMin: { type: "Int" }
    yearMax: { type: "Int" }
    country: { type: "String" }
    programmes: { type: "[String!]" }
    fundingMin: { type: "Float" }
    fundingMax: { type: "Float" }
    first: { type: "Int", defaultValue: 100 }
    after: { type: "String" }
  )
  @refetchable(queryName: "GrantListPaginationQuery") {
    search(
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
    ) @connection(key: "GrantList_search") {
      totalCount
      edges {
        node {
          id
          ...GrantCard_grant
        }
      }
    }
  }
`;

export default function GrantList({
  query: queryRef,
  onSelectGrant,
  onSave,
  savedIds,
  saveDisabled,
}) {
  const { data, loadNext, isLoadingNext, hasNext } = usePaginationFragment(
    GrantList_query,
    queryRef
  );

  const totalCount = data.search?.totalCount ?? 0;
  const edges = data.search?.edges ?? [];

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
        <span className="font-medium text-gray-700">{edges.length}</span>
        {' '}of{' '}
        <span className="font-medium text-gray-700">{totalCount}</span>{' '}
        match{totalCount !== 1 ? 'es' : ''}
      </p>

      {/* Grant cards */}
      <div className="space-y-3">
        {edges.map(edge => (
          <GrantCard
            key={edge.node.id}
            grant={edge.node}
            onSelect={onSelectGrant}
            onSave={onSave}
            isSaved={savedIds?.has(edge.node.id) ?? false}
            saveDisabled={saveDisabled}
            saveTooltip={saveDisabled ? 'Make a collection active first' : undefined}
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
