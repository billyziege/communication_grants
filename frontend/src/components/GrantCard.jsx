import React from 'react';
import { useFragment, graphql } from 'react-relay';
import { formatFunding, formatYear } from '../lib/utils.js';

export const GrantCard_grant = graphql`
  fragment GrantCard_grant on GrantNode {
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
`;

function BookmarkIcon({ filled }) {
  return (
    <svg viewBox="0 0 20 20" className="w-4 h-4 shrink-0" aria-hidden="true">
      {filled ? (
        <path
          fill="currentColor"
          d="M5 4a2 2 0 012-2h6a2 2 0 012 2v14l-5-2.5L5 18V4z"
        />
      ) : (
        <path
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          d="M5 4a2 2 0 012-2h6a2 2 0 012 2v14l-5-2.5L5 18V4z"
        />
      )}
    </svg>
  );
}

/**
 * GrantCardContent — pure presentational component, no Relay dependency.
 * Used both by GrantCard (Relay fragment) and by collection display (plain data).
 */
export function GrantCardContent({
  grant,
  onSelect,
  onSave,
  isSaved,
  saveDisabled,
  saveTooltip,
}) {
  const startYear = formatYear(grant.startDate);
  const endYear = formatYear(grant.endDate);
  const yearRange = startYear || endYear
    ? [startYear, endYear].filter(Boolean).join(' – ')
    : null;
  const funding = formatFunding(grant.fundingAmount, grant.fundingCurrency);

  const sourceIsNih = grant.source === 'NIH' || grant.source === 'nih';
  const sourceLabel = sourceIsNih ? 'NIH' : 'CORDIS';

  return (
    <div
      className="bg-white rounded-lg border border-gray-200 p-4 hover:border-blue-300 hover:shadow-sm cursor-pointer transition-all"
      onClick={() => onSelect && onSelect(grant.id)}
      data-testid="grant-card"
    >
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 flex-wrap">
          {/* Source badge */}
          <span
            className={`inline-block px-2 py-0.5 text-xs font-medium rounded ${
              sourceIsNih
                ? 'bg-blue-100 text-blue-700'
                : 'bg-green-100 text-green-700'
            }`}
            data-testid="source-badge"
          >
            {sourceLabel}
          </span>
          {/* Programme badge — CORDIS only */}
          {!sourceIsNih && grant.sourceProgramme && (
            <span className="inline-block px-1.5 py-0.5 text-xs bg-gray-100 text-gray-600 rounded">
              {grant.sourceProgramme}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3 flex-shrink-0">
          {yearRange && (
            <span className="text-xs text-gray-400">{yearRange}</span>
          )}
          {funding && (
            <span className="text-xs text-gray-600 font-medium">{funding}</span>
          )}
          {/* Save button */}
          <button
            type="button"
            aria-label={isSaved ? 'Saved to collection' : 'Save to collection'}
            title={saveDisabled ? (saveTooltip ?? 'Create a collection tab first') : undefined}
            disabled={saveDisabled}
            onClick={e => {
              e.stopPropagation();
              if (onSave && !saveDisabled) onSave(grant);
            }}
            className={`flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium transition-colors ${
              saveDisabled
                ? 'opacity-40 cursor-not-allowed bg-gray-100 text-gray-400'
                : isSaved
                ? 'bg-green-200 text-green-800 hover:bg-green-300'
                : 'bg-green-100 text-green-700 hover:bg-green-200'
            }`}
            data-testid="save-button"
          >
            <BookmarkIcon filled={isSaved} />
          </button>
        </div>
      </div>

      {/* Title */}
      <p
        className="text-sm font-semibold text-gray-900 line-clamp-2"
        data-testid="grant-title"
      >
        {grant.title}
      </p>

      {/* Organization · Country */}
      {(grant.organization || grant.country) && (
        <p className="text-xs text-gray-500 mt-1" data-testid="grant-org">
          {[grant.organization, grant.country].filter(Boolean).join(' · ')}
        </p>
      )}
    </div>
  );
}

/**
 * GrantCard — Relay fragment component for the search results list.
 */
export default function GrantCard({
  grant: grantRef,
  onSelect,
  onSave,
  isSaved,
  saveDisabled,
  saveTooltip,
}) {
  const grant = useFragment(GrantCard_grant, grantRef);
  return (
    <GrantCardContent
      grant={grant}
      onSelect={onSelect}
      onSave={onSave}
      isSaved={isSaved}
      saveDisabled={saveDisabled}
      saveTooltip={saveTooltip}
    />
  );
}
