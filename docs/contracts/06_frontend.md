# Contract 06 — Frontend

**Status:** Ready for implementation  
**Depends on:** Contract 05 (`api/schema.py` — GraphQL schema including `grantsBySource`)  
**Prerequisite for:** Contract 07 (Docker Compose wires the frontend build into the deployment)

---

## 1. Purpose and Scope

A React + Relay single-page application for searching and exploring the grant database. The primary interaction is FTS text search; facets narrow the results client-side. Users can collect grants into named collections, export collections to JSON files, and import collections shared by collaborators.

**In scope:**
- Vite + React 18 + Relay + Tailwind CSS build setup
- Search bar + facet sidebar + results list + detail slide-in panel
- Named collection tabs with save, close, export, and import
- Relay schema generation and compiler configuration
- Vitest + React Testing Library unit tests

**Out of scope:**
- Authentication
- Server-side facet filtering beyond `source` (all facets except source are client-side in v1)
- Backend changes (use the GraphQL API exactly as defined in Contract 05)

---

## 2. Visual Design

Carry over the design conventions from the existing project at `~/research/repos/invenio_testing/dantec-optimade-federation/frontend/`:

- **Color palette:** Tailwind defaults — `blue-600` primary action, `gray-50` page background, `gray-200` borders, `blue-100`/`blue-700` badges, `green-100`/`green-700` saved/positive actions
- **Typography:** Tailwind defaults; `text-sm` body, `text-xs` labels, `text-xl font-semibold` headings
- **Card style:** `bg-white rounded-lg border border-gray-200 p-4 hover:border-blue-300 hover:shadow-sm` (same as OPTIMADE StructureCard)
- **Filter section pattern:** reuse `FilterSection` component pattern (uppercase label + `tracking-wide` + children)
- **Input style:** `border border-gray-200 rounded px-2 py-1.5 text-sm focus:ring-1 focus:ring-blue-400`
- **Primary button:** `bg-blue-600 text-white rounded-md hover:bg-blue-700`
- **Secondary button:** `border border-gray-200 text-gray-600 rounded-md hover:bg-gray-50`

---

## 3. File Layout

```
frontend/
  index.html
  package.json
  vite.config.js
  tailwind.config.js
  postcss.config.js
  relay.config.js
  src/
    main.jsx
    index.css
    App.jsx
    relay/
      environment.js
    pages/
      GrantsPage.jsx
    components/
      SearchBar.jsx
      FilterPanel.jsx
      GrantCard.jsx
      GrantList.jsx
      GrantDetailPanel.jsx
      CollectionsPanel.jsx
    lib/
      collections.js       # localStorage helpers
      export.js            # file export/import helpers
      facets.js            # client-side filter functions
      utils.js             # cn() and formatting helpers
    __generated__/         # relay-compiler output (committed)
    __tests__/
      GrantCard.test.jsx
      FilterPanel.test.jsx
      GrantsPage.test.jsx
      collections.test.js
      facets.test.js
      relayTestUtils.jsx
      setup.js
```

---

## 4. Package Dependencies

```json
{
  "dependencies": {
    "react": "^18.3",
    "react-dom": "^18.3",
    "react-relay": "^18.0",
    "relay-runtime": "^18.0",
    "@radix-ui/react-toggle-group": "^1.1",
    "@radix-ui/react-dialog": "^1.1"
  },
  "devDependencies": {
    "vite": "^5.4",
    "@vitejs/plugin-react": "^4.3",
    "vite-plugin-relay": "^2.1",
    "relay-compiler": "^18.0",
    "tailwindcss": "^3.4",
    "postcss": "^8.4",
    "autoprefixer": "^10.4",
    "vitest": "^2.1",
    "@testing-library/react": "^16.0",
    "@testing-library/user-event": "^14.5",
    "jsdom": "^25.0"
  },
  "scripts": {
    "dev": "vite",
    "build": "relay-compiler && vite build",
    "relay": "relay-compiler",
    "test": "vitest run"
  }
}
```

---

## 5. Relay Configuration

### 5.1 Schema generation

Before running the Relay compiler, generate the schema file:

```bash
cd /home/zerbe/research/repos/communication_grants
python3 -c "from api.schema import schema; print(schema.as_str())" > frontend/schema.graphql
```

Commit `frontend/schema.graphql`. Regenerate whenever the Python schema changes.

### 5.2 `relay.config.js`

```js
module.exports = {
  src: './src',
  schema: './schema.graphql',
  exclude: ['**/__generated__/**', '**/__tests__/**'],
  language: 'javascript',
  eagerEsModules: true,
};
```

### 5.3 `vite.config.js`

```js
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import relay from 'vite-plugin-relay';

export default defineConfig({
  plugins: [react(), relay],
  server: { proxy: { '/graphql': 'http://localhost:8000' } },
});
```

The dev-server proxy routes `/graphql` to the FastAPI backend on port 8000.

---

## 6. Layout

```
┌──────────────────────────────────────────────────────────────────┐
│ Header: "Communication Grants"   [search input ............] [Go] │
├────────────────┬─────────────────────────────────────────────────┤
│ Left sidebar   │ Tab bar: [Search] [CollName ×] [CollName2 ×] [+]│
│ (280px fixed)  ├─────────────────────────────────────────────────┤
│                │ Results / Collection content (scrollable)        │
│ Source         │                                                  │
│ Year range     │   GrantCard                                      │
│ Country        │   GrantCard                                      │
│ Programme      │   ...                                            │
│ Funding        │   Load more                                      │
│                │                                                  │
└────────────────┴─────────────────────────────────────────────────┘
                   GrantDetailPanel (right slide-in, overlapping)
```

The detail panel overlaps the results area from the right; it does not push the layout.

---

## 7. App Shell — `App.jsx`

```jsx
export default function App() {
  return (
    <div className="h-screen flex flex-col bg-gray-50">
      <header className="flex-shrink-0 bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-4">
        <h1 className="text-xl font-semibold text-gray-900 flex-shrink-0">
          Communication Grants
        </h1>
        <SearchBar />  {/* takes up remaining header space */}
      </header>
      <main className="flex-1 overflow-hidden">
        <GrantsPage />
      </main>
    </div>
  );
}
```

---

## 8. `SearchBar.jsx`

Controlled input that calls `onSearch(query)` on Enter or button click. Lives in the header.

Props passed down via context (or lifted to `GrantsPage` via a shared state callback):
- `onSearch(query: string)` — fires the Relay query
- `value: string` — current query text
- `onChange(value: string)` — updates the text

```jsx
// renders:
<div className="flex flex-1 gap-2 max-w-2xl">
  <input
    type="search"
    placeholder="Search grants by keyword…"
    className="flex-1 text-sm border border-gray-200 rounded-md px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
    value={value}
    onChange={e => onChange(e.target.value)}
    onKeyDown={e => e.key === 'Enter' && onSearch(value)}
  />
  <button
    type="button"
    onClick={() => onSearch(value)}
    className="px-4 py-1.5 text-sm font-medium bg-blue-600 text-white rounded-md hover:bg-blue-700"
  >
    Search
  </button>
</div>
```

---

## 9. `FilterPanel.jsx`

Left sidebar. Facets other than `source` are client-side: they emit filter state via `onFacetsChange(facets)` and the parent passes filtered results back for display.

```jsx
// Props
{
  source: 'nih' | 'cordis' | null,       // server-side: passed to GraphQL
  onSourceChange(source),
  onFacetsChange(facets),                // client-side facets
}

// Facets object shape:
{
  startYearMin: number | null,   // filter: startDate year >= startYearMin
  startYearMax: number | null,   // filter: startDate year <= startYearMax
  country: string,               // filter: country contains this string (case-insensitive)
  programmes: Set<string>,       // filter: sourceProgramme in set ('fp7','h2020','horizon_europe')
  fundingMin: number | null,
  fundingMax: number | null,
}
```

Sections in order:
1. **Source** — toggle chips `[NIH] [CORDIS]` using Radix `ToggleGroup.Root type="single"` (null = both). This is the only server-side facet.
2. **Year range** — two number inputs (min/max). Placeholder: `2007` / `2026`.
3. **Country** — text input. Placeholder: `CZ, US…`. Matches ISO alpha-2 or partial org name.
4. **Programme** — toggle chips `[FP7] [H2020] [Horizon Europe]`; only relevant when CORDIS is active, but always visible (simplicity).
5. **Funding** — two number inputs for min/max EUR/USD amount.

Sticky top bar with Search and Reset buttons (same pattern as OPTIMADE `FilterPanel`). "Search" re-runs the Relay query with current source; Reset clears all state.

---

## 10. Relay Queries

### 10.1 Search query

```graphql
query GrantsSearchQuery(
  $query: String!
  $source: Source
  $first: Int
  $after: String
) {
  search(query: $query, source: $source, first: $first, after: $after) {
    ...GrantList_connection
  }
}
```

### 10.2 Reload collection query

```graphql
query GrantsReloadCollectionQuery($items: [GrantLookupInput!]!) {
  grantsBySource(items: $items) {
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
}
```

Used when importing a collection from file: re-fetches each `{source, sourceId}` pair to populate the in-memory snapshot.

### 10.3 Detail query

```graphql
query GrantDetailQuery($id: ID!) {
  node(id: $id) {
    ... on GrantNode {
      ...GrantDetail_grant
    }
  }
}
```

### 10.4 `GrantList_connection` fragment

```graphql
fragment GrantList_connection on GrantConnection {
  totalCount
  pageInfo { hasNextPage endCursor }
  edges {
    node { ...GrantCard_grant }
  }
}
```

### 10.5 `GrantCard_grant` fragment

```graphql
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
```

### 10.6 `GrantDetail_grant` fragment

```graphql
fragment GrantDetail_grant on GrantNode {
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
```

---

## 11. `GrantCard.jsx`

Relay fragment component. Renders a clickable card in the results list.

```
┌─────────────────────────────────────────────────────────┐
│ [NIH badge]  [+ Save]          2020 – 2024   $1,200,000 │
│ Title of the Grant (truncated to 2 lines)               │
│ University of Prague · CZ                               │
└─────────────────────────────────────────────────────────┘
```

- **Source badge**: `bg-blue-100 text-blue-700` for NIH; `bg-green-100 text-green-700` for CORDIS
- **Programme badge** (CORDIS only): `bg-gray-100 text-gray-600 text-xs` showing `fp7` / `h2020` / `horizon_europe`
- **Save button**: bookmark icon; calls `onSave(snapshot)` where snapshot is the plain data object extracted from the fragment. Active state: `bg-green-200 text-green-800`.
- **Funding**: formatted with `Intl.NumberFormat` using the `fundingCurrency` field; omitted if null.
- Click on card body (not the save button) calls `onSelect(id)` to open the detail panel.

The "Save" button adds to the **active collection tab** (the currently selected collection tab, not the Search tab). If no collection tab exists, the button is disabled with tooltip "Create a collection tab first".

---

## 12. `GrantList.jsx`

Renders a list of `GrantCard` components from the Relay connection fragment, plus a "Load more" button when `hasNextPage` is true.

- Uses `usePaginationFragment` with `@refetchable` and `@connection` directives for cursor pagination
- Passes each card's fragment ref to `GrantCard`
- Shows total count: `"Showing {displayedCount} of {totalCount} results"`
- When client-side facets are active, displayed count reflects filtered count with a note: `"(filtered from {totalCount})"`
- Empty state: `"No grants found. Try different keywords or filters."`
- Loading state via `Suspense` fallback

---

## 13. `GrantDetailPanel.jsx`

Right-side slide-in panel. Triggered by clicking a `GrantCard`.

```
┌──────────────────────────────────────────────────────┐
│ [×]                                                   │
│ Title (full, wrapping)                                │
│                                                       │
│ [NIH] [horizon_europe]   University of Prague · CZ    │
│ 2020-01-01 – 2024-12-31 · €1,200,000                 │
│                                                       │
│ Abstract                                              │
│ ─────────────────────────────────────────────────────│
│ Lorem ipsum abstract text…                            │
│                                                       │
│ Details                                               │
│ ─────────────────────────────────────────────────────│
│ Source ID:   APP123456                                │
│ Activity:    R01                                      │
│ IC Name:     National Cancer Institute                │
│ PI:          SMITH, JOHN                              │
│ …                                                     │
│                                                       │
│ [View source ↗]   [+ Save to collection]              │
└──────────────────────────────────────────────────────┘
```

- Uses `usePreloadedQuery` with the detail query; preloaded when the card is clicked
- `metadata` JSON is rendered as a key/value list; keys are formatted from snake_case to `Title Case`
- `[View source ↗]` opens `sourceUrl` in a new tab
- `[+ Save to collection]` same behavior as the card's save button
- Close button (`×`) calls `onClose()`
- Rendered at `position: fixed; right: 0; top: header height; height: calc(100vh - header height); width: 480px`; overlaps the results panel

---

## 14. `CollectionsPanel.jsx`

Manages the tab bar for the Search tab and collection tabs.

### 14.1 Tab bar

```
[Search] [My Collection ×] [CZ Grants ×] [+]
```

- **Search tab** is always first and cannot be closed
- Each collection tab shows its name and an `×` button
- `×` removes the tab: deletes from localStorage and updates state; no confirmation dialog (the user can re-import the file)
- `[+]` opens a dialog (`@radix-ui/react-dialog`) with a text input for the new collection name. On confirm: creates an empty collection in localStorage with that name, switches to the new tab.

### 14.2 Active collection context

The active collection tab determines where `GrantCard`'s save button puts items. When the Search tab is active, the save button is disabled. When a collection tab is active, clicking save adds the grant to that collection.

---

## 15. `lib/collections.js` — localStorage helpers

Collections are stored under the key `"grant_collections"` in `localStorage`.

```js
// Schema
{
  collections: [
    {
      name: string,                     // user-visible name
      createdAt: string,                // ISO 8601
      items: [
        {
          source: string,               // 'nih' | 'cordis'
          sourceId: string,             // stable external ID
          // snapshot fields (for rendering without re-fetch):
          title: string,
          organization: string | null,
          country: string | null,
          startDate: string | null,
          endDate: string | null,
          fundingAmount: number | null,
          fundingCurrency: string | null,
          sourceProgramme: string | null,
          sourceUrl: string,
        }
      ]
    }
  ]
}
```

Exported functions:
- `loadCollections() → Collection[]` — reads and parses from localStorage; returns `[]` if absent or corrupted
- `saveCollections(collections) → void` — JSON.stringifies and writes to localStorage
- `addItemToCollection(collections, name, item) → Collection[]` — returns new array; throws if `source+sourceId` already in that collection
- `removeItemFromCollection(collections, name, source, sourceId) → Collection[]`
- `createCollection(collections, name) → Collection[]` — throws if name already exists
- `deleteCollection(collections, name) → Collection[]`

---

## 16. `lib/export.js` — file export/import

### 16.1 Export format

```json
{
  "version": 1,
  "tool": "communication-grants",
  "collectionName": "CZ Grants",
  "exportedAt": "2026-11-08T12:34:56.000Z",
  "items": [
    {"source": "nih", "sourceId": "12345"},
    {"source": "cordis", "sourceId": "67890"}
  ]
}
```

Only `source` + `sourceId` are exported — no snapshots (they may be stale). On import the app re-fetches via `grantsBySource`.

### 16.2 `exportCollection(collection) → void`

Creates a JSON blob and triggers a browser download. The filename defaults to `{collection.name}.json` (spaces replaced with underscores).

```js
function exportCollection(collection) {
  const payload = {
    version: 1,
    tool: 'communication-grants',
    collectionName: collection.name,
    exportedAt: new Date().toISOString(),
    items: collection.items.map(({ source, sourceId }) => ({ source, sourceId })),
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = collection.name.replace(/\s+/g, '_') + '.json';
  a.click();
  URL.revokeObjectURL(url);
}
```

### 16.3 `parseImportFile(file) → Promise<{collectionName, items}>`

Reads a `File` object, parses the JSON, validates structure. Throws descriptive errors for:
- Not valid JSON
- Missing `version` or `items` fields
- `version` is not `1`
- Any item missing `source` or `sourceId`

The `collectionName` returned is derived from the **filename without extension** (e.g. `"CZ_Grants.json"` → `"CZ_Grants"`), not from the JSON `collectionName` field. This ensures the tab name reflects what the user named the file on disk.

### 16.4 Import flow in `CollectionsPanel`

1. User clicks an "Import" button (file picker input, `accept=".json"`)
2. `parseImportFile(file)` runs
3. Check if a collection named `collectionName` already exists:
   - **If yes**: show inline error `"A collection named '{name}' already exists. Close it first, then re-import."` — abort, do not create the tab
   - **If no**: continue
4. Call Relay `grantsBySource` with all `{source, sourceId}` pairs
5. Items not found in the database (returned as `null`) are silently skipped — they may be from a different year range
6. Items found are added to a new collection tab named after the file
7. If zero items resolved, show inline error: `"No grants from this file were found in the current database."` — do not create an empty tab
8. Switch to the new collection tab

---

## 17. `lib/facets.js` — client-side filter functions

```js
// All functions are pure and take (grants: GrantSnapshot[], facets: FacetsState) → GrantSnapshot[]

export function applyFacets(grants, facets) {
  return grants.filter(g => matchesFacets(g, facets));
}

function matchesFacets(g, { startYearMin, startYearMax, country, programmes, fundingMin, fundingMax }) {
  if (startYearMin != null && year(g.startDate) < startYearMin) return false;
  if (startYearMax != null && year(g.startDate) > startYearMax) return false;
  if (country && !g.country?.toLowerCase().includes(country.toLowerCase())) return false;
  if (programmes.size > 0 && !programmes.has(g.sourceProgramme)) return false;
  if (fundingMin != null && (g.fundingAmount == null || g.fundingAmount < fundingMin)) return false;
  if (fundingMax != null && (g.fundingAmount == null || g.fundingAmount > fundingMax)) return false;
  return true;
}

function year(isoDate) {
  if (!isoDate) return null;
  return parseInt(isoDate.slice(0, 4), 10);
}
```

---

## 18. `GrantsPage.jsx` — state and data flow

Top-level state lives here. Children receive callbacks.

```
searchQuery: string              — current text in the search bar
source: 'nih' | 'cordis' | null — server-side filter
facets: FacetsState              — client-side filter state
selectedGrantId: string | null   — Relay global ID for detail panel
activeTab: 'search' | string     — collection name or 'search'
queryRef: PreloadedQuery | null  — Relay preloaded query ref
```

On search submit: `loadQuery({ query: searchQuery, source, first: 100 })`. Initial page size is 100 — large enough that most targeted research searches fit in one shot.

Client-side facets are applied in `GrantsPage` after the Relay connection data is read; the filtered list is passed to the display component. `totalCount` from GraphQL is shown as "of {totalCount} database matches", with the filtered count shown as "showing {N}".

---

## 19. Test Surface

Use Vitest + React Testing Library. Mock the Relay environment using the same `relayTestUtils.jsx` pattern from the OPTIMADE browser project.

**`facets.test.js`:**
- `applyFacets` with no facets returns all items
- `applyFacets` with `startYearMin` filters correctly
- `applyFacets` with `country: "CZ"` returns only CZ items
- `applyFacets` with `programmes` set filters correctly
- Null `startDate` or `fundingAmount` handled without crash

**`collections.test.js`:**
- `createCollection` adds a new collection
- `createCollection` throws if name already exists
- `addItemToCollection` adds an item
- `addItemToCollection` throws if `source+sourceId` already in collection
- `removeItemFromCollection` removes item
- `deleteCollection` removes collection
- `loadCollections` returns `[]` for missing localStorage key
- `loadCollections` returns `[]` for corrupted JSON (does not throw)

**`export.test.js` (in `collections.test.js` or separate):**
- `parseImportFile` parses valid JSON
- `parseImportFile` rejects invalid JSON
- `parseImportFile` rejects missing `items` field
- `parseImportFile` rejects `version !== 1`
- `parseImportFile` derives collection name from filename, not `collectionName` JSON field
- `parseImportFile` rejects items missing `source`

**`GrantCard.test.jsx`:**
- Renders title, organization, country, source badge
- Save button calls `onSave` with correct snapshot data
- Click on card body (not save button) calls `onSelect`

**`FilterPanel.test.jsx`:**
- Source toggle fires `onSourceChange` with correct value
- Year range inputs fire `onFacetsChange` with parsed integers
- Reset button clears all state

**`GrantsPage.test.jsx`:**
- Initial render shows empty search state (no results until search submitted)
- Submitting a search loads the Relay query
- Switching to a collection tab shows collection content (not search results)
- Import error shown when duplicate collection name

---

## 20. Known Implementation Notes

- **Relay compiler must run before `vite build`** — the `"build"` npm script runs `relay-compiler` first
- **`schema.graphql` must be regenerated** after any change to `api/schema.py` by running `python3 -c "from api.schema import schema; print(schema.as_str())" > frontend/schema.graphql`
- **`vite-plugin-relay`** handles the Babel transform for `graphql\`...\`` tagged template literals; no separate Babel config is needed
- **`grantsBySource` on import** — the Relay query runs outside of a component (triggered by user file interaction). Use `fetchQuery` from `relay-runtime` rather than a hook.
- **`localStorage` availability** — wrap every read/write in try/catch; fall back to in-memory state if localStorage is blocked (private browsing). Do not show an error to the user; the app still works, collections just won't persist across page loads.
- **Search tab Relay GC** — when the user navigates away from the Search tab and back, the Relay store retains the query unless explicitly evicted. This is the desired behavior — results persist while the user browses collections.
