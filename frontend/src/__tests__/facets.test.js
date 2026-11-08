import { describe, it, expect } from 'vitest';
import { emptyFilters } from '../lib/facets.js';

describe('emptyFilters', () => {
  it('returns an object with all filter fields at their empty state', () => {
    const f = emptyFilters();
    expect(f.source).toBeNull();
    expect(f.yearMin).toBeNull();
    expect(f.yearMax).toBeNull();
    expect(f.country).toBe('');
    expect(f.programmes).toBeInstanceOf(Set);
    expect(f.programmes.size).toBe(0);
    expect(f.fundingMin).toBeNull();
    expect(f.fundingMax).toBeNull();
  });

  it('returns a fresh object on each call', () => {
    const a = emptyFilters();
    const b = emptyFilters();
    expect(a).not.toBe(b);
    expect(a.programmes).not.toBe(b.programmes);
  });
});
