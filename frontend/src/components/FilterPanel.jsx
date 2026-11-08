import React, { useState, useEffect } from 'react';
import * as ToggleGroup from '@radix-ui/react-toggle-group';
import { emptyFilters } from '../lib/facets.js';

const PROGRAMME_LABELS = {
  fp7: 'FP7',
  h2020: 'H2020',
  horizon_europe: 'Horizon Europe',
};

function FilterSection({ label, children }) {
  return (
    <div>
      <div className="mb-1.5">
        <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
          {label}
        </span>
      </div>
      {children}
    </div>
  );
}

function IntInput({ value, onChange, placeholder }) {
  return (
    <input
      type="number"
      value={value === null ? '' : value}
      onChange={e => {
        const v = e.target.value;
        onChange(v === '' ? null : parseInt(v, 10));
      }}
      placeholder={placeholder}
      className="w-full text-sm border border-gray-200 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400 placeholder:text-gray-300"
    />
  );
}

function FloatInput({ value, onChange, placeholder }) {
  return (
    <input
      type="number"
      value={value === null ? '' : value}
      onChange={e => {
        const v = e.target.value;
        onChange(v === '' ? null : parseFloat(v));
      }}
      placeholder={placeholder}
      className="w-full text-sm border border-gray-200 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400 placeholder:text-gray-300"
    />
  );
}

export default function FilterPanel({
  filters,
  availableSources = [],
  availableProgrammes = [],
  availableCountries = [],
  onApply,
  onReset,
}) {
  const [local, setLocal] = useState(() => ({
    ...filters,
    programmes: new Set(filters.programmes),
  }));

  // Sync when parent resets filters from outside
  useEffect(() => {
    setLocal({ ...filters, programmes: new Set(filters.programmes) });
  }, [filters]);

  function update(key, value) {
    setLocal(prev => ({ ...prev, [key]: value }));
  }

  function handleProgrammeChange(vals) {
    setLocal(prev => ({ ...prev, programmes: new Set(vals) }));
  }

  return (
    <div className="flex flex-col h-full">
      {/* Scrollable filter body */}
      <div className="flex-1 overflow-y-auto p-3 space-y-5">

        {/* Source — data-driven, appears after search */}
        {availableSources.length > 0 && (
          <FilterSection label="Source">
            <ToggleGroup.Root
              type="single"
              value={local.source ?? ''}
              onValueChange={val => update('source', val || null)}
              className="flex gap-1"
              aria-label="Source filter"
            >
              {availableSources.map(s => (
                <ToggleGroup.Item
                  key={s}
                  value={s}
                  aria-label={s}
                  className="px-3 py-1 text-xs rounded border transition-colors select-none cursor-pointer
                    data-[state=on]:bg-blue-100 data-[state=on]:border-blue-400 data-[state=on]:text-blue-700 data-[state=on]:font-medium
                    data-[state=off]:bg-white data-[state=off]:border-gray-200 data-[state=off]:text-gray-500
                    hover:data-[state=off]:border-gray-400 focus:outline-none"
                >
                  {s}
                </ToggleGroup.Item>
              ))}
            </ToggleGroup.Root>
          </FilterSection>
        )}

        {/* Year range — always visible */}
        <FilterSection label="Year range">
          <div className="flex gap-2">
            <div className="flex-1">
              <div className="text-[10px] text-gray-400 mb-0.5">From</div>
              <IntInput
                value={local.yearMin}
                onChange={v => update('yearMin', v)}
                placeholder="2007"
              />
            </div>
            <div className="flex-1">
              <div className="text-[10px] text-gray-400 mb-0.5">To</div>
              <IntInput
                value={local.yearMax}
                onChange={v => update('yearMax', v)}
                placeholder="2026"
              />
            </div>
          </div>
        </FilterSection>

        {/* Country — data-driven dropdown, appears after search */}
        {availableCountries.length > 0 && (
          <FilterSection label="Country">
            <select
              value={local.country}
              onChange={e => update('country', e.target.value)}
              className="w-full text-sm border border-gray-200 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400 bg-white"
              aria-label="Country filter"
            >
              <option value="">All countries</option>
              {availableCountries.map(c => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </FilterSection>
        )}

        {/* Programme — data-driven, appears after search */}
        {availableProgrammes.length > 0 && (
          <FilterSection label="Programme">
            <ToggleGroup.Root
              type="multiple"
              value={[...local.programmes]}
              onValueChange={handleProgrammeChange}
              className="flex flex-wrap gap-1"
              aria-label="Programme filter"
            >
              {availableProgrammes.map(p => (
                <ToggleGroup.Item
                  key={p}
                  value={p}
                  aria-label={PROGRAMME_LABELS[p] ?? p}
                  className="px-2 py-1 text-xs rounded border transition-colors select-none cursor-pointer
                    data-[state=on]:bg-blue-100 data-[state=on]:border-blue-400 data-[state=on]:text-blue-700 data-[state=on]:font-medium
                    data-[state=off]:bg-white data-[state=off]:border-gray-200 data-[state=off]:text-gray-500
                    hover:data-[state=off]:border-gray-400 focus:outline-none"
                >
                  {PROGRAMME_LABELS[p] ?? p}
                </ToggleGroup.Item>
              ))}
            </ToggleGroup.Root>
          </FilterSection>
        )}

        {/* Funding — always visible */}
        <FilterSection label="Funding (EUR/USD)">
          <div className="flex gap-2">
            <div className="flex-1">
              <div className="text-[10px] text-gray-400 mb-0.5">Min</div>
              <FloatInput
                value={local.fundingMin}
                onChange={v => update('fundingMin', v)}
                placeholder="0"
              />
            </div>
            <div className="flex-1">
              <div className="text-[10px] text-gray-400 mb-0.5">Max</div>
              <FloatInput
                value={local.fundingMax}
                onChange={v => update('fundingMax', v)}
                placeholder="—"
              />
            </div>
          </div>
        </FilterSection>

        {/* Hint before first search */}
        {availableSources.length === 0 && availableCountries.length === 0 && (
          <p className="text-xs text-gray-400 italic pt-1">
            Source, country, and programme filters appear after a search.
          </p>
        )}

      </div>

      {/* Sticky bottom bar: Apply + Reset */}
      <div className="flex-shrink-0 border-t border-gray-200 bg-white p-3 flex gap-2">
        <button
          type="button"
          onClick={() => onApply(local)}
          className="flex-1 py-1.5 text-sm font-medium bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors"
        >
          Apply
        </button>
        <button
          type="button"
          onClick={onReset}
          className="px-3 py-1.5 text-sm font-medium text-gray-600 border border-gray-200 rounded-md hover:bg-gray-50 hover:text-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-300 transition-colors"
        >
          Reset
        </button>
      </div>
    </div>
  );
}
