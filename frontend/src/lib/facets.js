export function emptyFilters() {
  return {
    source: null,
    yearMin: null,
    yearMax: null,
    country: '',
    programmes: new Set(),
    fundingMin: null,
    fundingMax: null,
  };
}
