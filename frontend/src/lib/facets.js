/**
 * facets.js — client-side filter functions for grant data.
 *
 * All functions are pure: they take (grants, facets) and return a filtered array.
 * No React dependency.
 */

/**
 * Extract the year from an ISO date string.
 * Returns null if isoDate is null/undefined/empty.
 *
 * @param {string|null} isoDate
 * @returns {number|null}
 */
function year(isoDate) {
  if (!isoDate) return null;
  return parseInt(isoDate.slice(0, 4), 10);
}

/**
 * Test whether a single grant matches the facet state.
 *
 * @param {Object} g  — grant snapshot
 * @param {Object} facets  — FacetsState
 * @returns {boolean}
 */
function matchesFacets(g, {
  startYearMin,
  startYearMax,
  country,
  programmes,
  fundingMin,
  fundingMax,
}) {
  if (startYearMin != null) {
    const y = year(g.startDate);
    if (y == null || y < startYearMin) return false;
  }
  if (startYearMax != null) {
    const y = year(g.startDate);
    if (y == null || y > startYearMax) return false;
  }
  if (country && country.trim() !== '') {
    if (g.country !== country) return false;
  }
  if (programmes && programmes.size > 0) {
    if (!programmes.has(g.sourceProgramme)) return false;
  }
  if (fundingMin != null) {
    if (g.fundingAmount == null || g.fundingAmount < fundingMin) return false;
  }
  if (fundingMax != null) {
    if (g.fundingAmount == null || g.fundingAmount > fundingMax) return false;
  }
  return true;
}

/**
 * Filter an array of grant snapshots by the given facet state.
 *
 * @param {Array<Object>} grants  — grant snapshots
 * @param {Object} facets  — FacetsState
 * @returns {Array<Object>} filtered grants
 */
export function applyFacets(grants, facets) {
  return grants.filter(g => matchesFacets(g, facets));
}

/**
 * Returns an empty facets object (no filters active).
 *
 * @returns {Object}
 */
export function emptyFacets() {
  return {
    startYearMin: null,
    startYearMax: null,
    country: '',
    programmes: new Set(),
    fundingMin: null,
    fundingMax: null,
  };
}
