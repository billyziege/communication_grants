import React from 'react';
import { usePreloadedQuery, graphql } from 'react-relay';
import { formatFunding, snakeToTitle } from '../lib/utils.js';

export const GrantDetailPanelQuery = graphql`
  query GrantDetailPanelQuery($id: ID!) {
    node(id: $id) {
      ... on GrantNode {
        ...GrantDetailPanel_grant
      }
    }
  }
`;

const GrantDetailPanel_grant = graphql`
  fragment GrantDetailPanel_grant on GrantNode {
    id
    title
    abstract
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
    metadata
  }
`;

function DetailRow({ label, value }) {
  if (value == null || value === '') return null;
  return (
    <div className="flex gap-2 text-sm py-0.5">
      <span className="text-gray-500 flex-shrink-0 w-32">{label}:</span>
      <span className="text-gray-900 break-words">{String(value)}</span>
    </div>
  );
}

function GrantDetailContent({ grant, onClose, onSave, isSaved, saveDisabled }) {
  if (!grant) return null;

  const sourceIsNih = grant.source === 'NIH' || grant.source === 'nih';
  const sourceLabel = sourceIsNih ? 'NIH' : 'CORDIS';
  const funding = formatFunding(grant.fundingAmount, grant.fundingCurrency);
  const dateLine = [grant.startDate, grant.endDate].filter(Boolean).join(' – ');

  const metadata = grant.metadata && typeof grant.metadata === 'object'
    ? Object.entries(grant.metadata).filter(([, v]) => v != null && v !== '')
    : [];

  return (
    <div
      className="fixed right-0 top-[57px] h-[calc(100vh-57px)] w-[480px] bg-white border-l border-gray-200 shadow-xl overflow-y-auto z-50 flex flex-col"
      data-testid="detail-panel"
    >
      {/* Header */}
      <div className="flex-shrink-0 p-4 border-b border-gray-200 flex items-start gap-3">
        <button
          type="button"
          onClick={onClose}
          aria-label="Close detail panel"
          className="flex-shrink-0 text-gray-400 hover:text-gray-700 text-xl leading-none mt-0.5"
        >
          ×
        </button>
        <h2 className="text-base font-semibold text-gray-900 flex-1 leading-snug">
          {grant.title}
        </h2>
      </div>

      {/* Meta row */}
      <div className="flex-shrink-0 p-4 border-b border-gray-100 flex flex-wrap items-center gap-2">
        <span
          className={`inline-block px-2 py-0.5 text-xs font-medium rounded ${
            sourceIsNih
              ? 'bg-blue-100 text-blue-700'
              : 'bg-green-100 text-green-700'
          }`}
        >
          {sourceLabel}
        </span>
        {!sourceIsNih && grant.sourceProgramme && (
          <span className="inline-block px-1.5 py-0.5 text-xs bg-gray-100 text-gray-600 rounded">
            {grant.sourceProgramme}
          </span>
        )}
        {(grant.organization || grant.country) && (
          <span className="text-sm text-gray-600">
            {[grant.organization, grant.country].filter(Boolean).join(' · ')}
          </span>
        )}
        {(dateLine || funding) && (
          <span className="text-sm text-gray-500">
            {[dateLine, funding].filter(Boolean).join(' · ')}
          </span>
        )}
      </div>

      {/* Scrollable body */}
      <div className="flex-1 p-4 space-y-5 overflow-y-auto">
        {/* Abstract */}
        {grant.abstract && (
          <div>
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
              Abstract
            </h3>
            <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
              {grant.abstract}
            </p>
          </div>
        )}

        {/* Metadata */}
        {metadata.length > 0 && (
          <div>
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
              Details
            </h3>
            <div className="border-t border-gray-100 pt-2">
              {metadata.map(([k, v]) => (
                <DetailRow key={k} label={snakeToTitle(k)} value={v} />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Footer actions */}
      <div className="flex-shrink-0 p-4 border-t border-gray-200 flex gap-2">
        {grant.sourceUrl && (
          <a
            href={grant.sourceUrl}
            target="_blank"
            rel="noreferrer"
            className="flex-1 text-center py-1.5 text-sm font-medium border border-gray-200 text-gray-600 rounded-md hover:bg-gray-50"
          >
            View source ↗
          </a>
        )}
        <button
          type="button"
          disabled={saveDisabled}
          onClick={() => !saveDisabled && onSave && onSave(grant)}
          className={`flex-1 py-1.5 text-sm font-medium rounded-md transition-colors ${
            saveDisabled
              ? 'opacity-40 cursor-not-allowed border border-gray-200 text-gray-400'
              : isSaved
              ? 'bg-green-200 text-green-800 hover:bg-green-300'
              : 'bg-blue-600 text-white hover:bg-blue-700'
          }`}
        >
          {isSaved ? '✓ Saved' : '+ Save to collection'}
        </button>
      </div>
    </div>
  );
}

function GrantDetailLoader({ queryRef, onClose, onSave, isSaved, saveDisabled }) {
  const data = usePreloadedQuery(GrantDetailPanelQuery, queryRef);
  const grant = data.node;
  return (
    <GrantDetailContent
      grant={grant}
      onClose={onClose}
      onSave={onSave}
      isSaved={isSaved}
      saveDisabled={saveDisabled}
    />
  );
}

export default function GrantDetailPanel({
  queryRef,
  onClose,
  onSave,
  isSaved,
  saveDisabled,
}) {
  if (!queryRef) return null;
  return (
    <GrantDetailLoader
      queryRef={queryRef}
      onClose={onClose}
      onSave={onSave}
      isSaved={isSaved}
      saveDisabled={saveDisabled}
    />
  );
}
