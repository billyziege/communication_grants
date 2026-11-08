import { describe, it, expect } from 'vitest';
import { applyFacets, emptyFacets } from '../lib/facets.js';

const grants = [
  {
    id: '1',
    title: 'Grant A',
    source: 'nih',
    sourceId: 'A1',
    startDate: '2020-01-01',
    endDate: '2024-12-31',
    country: 'US',
    sourceProgramme: null,
    fundingAmount: 500000,
    fundingCurrency: 'USD',
  },
  {
    id: '2',
    title: 'Grant B',
    source: 'cordis',
    sourceId: 'B1',
    startDate: '2015-06-01',
    endDate: '2019-05-31',
    country: 'CZ',
    sourceProgramme: 'fp7',
    fundingAmount: 1200000,
    fundingCurrency: 'EUR',
  },
  {
    id: '3',
    title: 'Grant C',
    source: 'cordis',
    sourceId: 'C1',
    startDate: '2021-03-01',
    endDate: '2026-02-28',
    country: 'DE',
    sourceProgramme: 'horizon_europe',
    fundingAmount: null,
    fundingCurrency: null,
  },
  {
    id: '4',
    title: 'Grant D',
    source: 'nih',
    sourceId: 'D1',
    startDate: null,
    endDate: null,
    country: null,
    sourceProgramme: null,
    fundingAmount: 200000,
    fundingCurrency: 'USD',
  },
];

describe('applyFacets', () => {
  it('returns all items when no facets are active', () => {
    const result = applyFacets(grants, emptyFacets());
    expect(result).toHaveLength(4);
  });

  it('filters by startYearMin', () => {
    const result = applyFacets(grants, { ...emptyFacets(), startYearMin: 2020 });
    // Grant A (2020), Grant C (2021) pass; Grant B (2015) and Grant D (null startDate) fail
    expect(result.map(g => g.id)).toEqual(expect.arrayContaining(['1', '3']));
    expect(result.map(g => g.id)).not.toContain('2');
    expect(result.map(g => g.id)).not.toContain('4');
  });

  it('filters by startYearMax', () => {
    const result = applyFacets(grants, { ...emptyFacets(), startYearMax: 2019 });
    // Only Grant B (2015) passes; D (null) fails too
    expect(result.map(g => g.id)).toEqual(['2']);
  });

  it('filters by country (case-insensitive substring)', () => {
    const result = applyFacets(grants, { ...emptyFacets(), country: 'CZ' });
    expect(result.map(g => g.id)).toEqual(['2']);
  });

  it('filters by country returns empty when no match', () => {
    const result = applyFacets(grants, { ...emptyFacets(), country: 'JP' });
    expect(result).toHaveLength(0);
  });

  it('filters by programmes set', () => {
    const programmes = new Set(['fp7']);
    const result = applyFacets(grants, { ...emptyFacets(), programmes });
    expect(result.map(g => g.id)).toEqual(['2']);
  });

  it('filters by multiple programmes', () => {
    const programmes = new Set(['fp7', 'horizon_europe']);
    const result = applyFacets(grants, { ...emptyFacets(), programmes });
    expect(result.map(g => g.id)).toEqual(expect.arrayContaining(['2', '3']));
  });

  it('filters by fundingMin', () => {
    const result = applyFacets(grants, { ...emptyFacets(), fundingMin: 600000 });
    // Only B (1,200,000) passes; A (500k), C (null), D (200k) fail
    expect(result.map(g => g.id)).toEqual(['2']);
  });

  it('filters by fundingMax', () => {
    const result = applyFacets(grants, { ...emptyFacets(), fundingMax: 300000 });
    // A (500k) fails, B (1.2M) fails, C (null) fails, D (200k) passes
    expect(result.map(g => g.id)).toEqual(['4']);
  });

  it('handles null startDate without crashing', () => {
    const result = applyFacets(grants, { ...emptyFacets(), startYearMin: 2020 });
    // Grant D has null startDate — should not crash, just be excluded
    expect(result.map(g => g.id)).not.toContain('4');
  });

  it('handles null fundingAmount without crashing', () => {
    const result = applyFacets(grants, { ...emptyFacets(), fundingMin: 1 });
    // Grant C has null fundingAmount — should not crash, just be excluded
    expect(result.map(g => g.id)).not.toContain('3');
  });
});
