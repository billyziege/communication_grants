import React, { useState } from 'react';
import * as ToggleGroup from '@radix-ui/react-toggle-group';
import { emptyFacets } from '../lib/facets.js';

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

function NumberInput({ value, onChange, placeholder }) {
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

const PROGRAMME_OPTIONS = [
  { value: 'fp7', label: 'FP7' },
  { value: 'h2020', label: 'H2020' },
  { value: 'horizon_europe', label: 'Horizon Europe' },
];

export default function FilterPanel({
  source,
  onSourceChange,
  onFacetsChange,
  onSearch,
}) {
  const [facets, setFacets] = useState(emptyFacets());

  function updateFacet(key, value) {
    const next = { ...facets, [key]: value };
    setFacets(next);
    onFacetsChange(next);
  }

  function handleProgrammeChange(vals) {
    const next = { ...facets, programmes: new Set(vals) };
    setFacets(next);
    onFacetsChange(next);
  }

  function handleReset() {
    const reset = emptyFacets();
    setFacets(reset);
    onFacetsChange(reset);
    onSourceChange(null);
  }

  return (
    <div>
      {/* Sticky top bar */}
      <div className="sticky top-0 z-10 bg-white border-b border-gray-200 p-3 flex gap-2">
        <button
          type="button"
          onClick={onSearch}
          className="flex-1 py-1.5 text-sm font-medium bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors"
        >
          Search
        </button>
        <button
          type="button"
          onClick={handleReset}
          className="px-3 py-1.5 text-sm font-medium text-gray-600 border border-gray-200 rounded-md hover:bg-gray-50 hover:text-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-300 transition-colors"
        >
          Reset
        </button>
      </div>

      {/* Scrollable filter body */}
      <div className="p-3 space-y-5">

        {/* 1. Source — server-side */}
        <FilterSection label="Source">
          <ToggleGroup.Root
            type="single"
            value={source ?? ''}
            onValueChange={val => onSourceChange(val || null)}
            className="flex gap-1"
            aria-label="Source filter"
          >
            {[
              { value: 'NIH', label: 'NIH' },
              { value: 'CORDIS', label: 'CORDIS' },
            ].map(({ value, label }) => (
              <ToggleGroup.Item
                key={value}
                value={value}
                aria-label={label}
                className="px-3 py-1 text-xs rounded border transition-colors select-none cursor-pointer
                  data-[state=on]:bg-blue-100 data-[state=on]:border-blue-400 data-[state=on]:text-blue-700 data-[state=on]:font-medium
                  data-[state=off]:bg-white data-[state=off]:border-gray-200 data-[state=off]:text-gray-500
                  hover:data-[state=off]:border-gray-400 focus:outline-none"
              >
                {label}
              </ToggleGroup.Item>
            ))}
          </ToggleGroup.Root>
        </FilterSection>

        {/* 2. Year range — client-side */}
        <FilterSection label="Year range">
          <div className="flex gap-2">
            <div className="flex-1">
              <div className="text-[10px] text-gray-400 mb-0.5">From</div>
              <NumberInput
                value={facets.startYearMin}
                onChange={v => updateFacet('startYearMin', v)}
                placeholder="2007"
              />
            </div>
            <div className="flex-1">
              <div className="text-[10px] text-gray-400 mb-0.5">To</div>
              <NumberInput
                value={facets.startYearMax}
                onChange={v => updateFacet('startYearMax', v)}
                placeholder="2026"
              />
            </div>
          </div>
        </FilterSection>

        {/* 3. Country — client-side */}
        <FilterSection label="Country">
          <input
            type="text"
            value={facets.country}
            onChange={e => updateFacet('country', e.target.value)}
            placeholder="CZ, US…"
            className="w-full text-sm border border-gray-200 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400 placeholder:text-gray-300"
            aria-label="Country filter"
          />
        </FilterSection>

        {/* 4. Programme — client-side */}
        <FilterSection label="Programme">
          <ToggleGroup.Root
            type="multiple"
            value={[...facets.programmes]}
            onValueChange={handleProgrammeChange}
            className="flex flex-wrap gap-1"
            aria-label="Programme filter"
          >
            {PROGRAMME_OPTIONS.map(({ value, label }) => (
              <ToggleGroup.Item
                key={value}
                value={value}
                aria-label={label}
                className="px-2 py-1 text-xs rounded border transition-colors select-none cursor-pointer
                  data-[state=on]:bg-blue-100 data-[state=on]:border-blue-400 data-[state=on]:text-blue-700 data-[state=on]:font-medium
                  data-[state=off]:bg-white data-[state=off]:border-gray-200 data-[state=off]:text-gray-500
                  hover:data-[state=off]:border-gray-400 focus:outline-none"
              >
                {label}
              </ToggleGroup.Item>
            ))}
          </ToggleGroup.Root>
        </FilterSection>

        {/* 5. Funding — client-side */}
        <FilterSection label="Funding (EUR/USD)">
          <div className="flex gap-2">
            <div className="flex-1">
              <div className="text-[10px] text-gray-400 mb-0.5">Min</div>
              <NumberInput
                value={facets.fundingMin}
                onChange={v => updateFacet('fundingMin', v)}
                placeholder="0"
              />
            </div>
            <div className="flex-1">
              <div className="text-[10px] text-gray-400 mb-0.5">Max</div>
              <NumberInput
                value={facets.fundingMax}
                onChange={v => updateFacet('fundingMax', v)}
                placeholder="—"
              />
            </div>
          </div>
        </FilterSection>

      </div>
    </div>
  );
}
