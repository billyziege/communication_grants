import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  loadCollections,
  saveCollections,
  createCollection,
  deleteCollection,
  addItemToCollection,
  removeItemFromCollection,
} from '../lib/collections.js';
import { parseImportFile } from '../lib/export.js';

const makeItem = (source, sourceId) => ({
  source,
  sourceId,
  title: `Grant ${sourceId}`,
  organization: 'Test Org',
  country: 'US',
  startDate: '2020-01-01',
  endDate: '2024-12-31',
  fundingAmount: 100000,
  fundingCurrency: 'USD',
  sourceProgramme: null,
  sourceUrl: 'https://example.com',
});

// --- loadCollections / saveCollections ---

describe('loadCollections', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('returns [] when localStorage key is absent', () => {
    expect(loadCollections()).toEqual([]);
  });

  it('returns [] for corrupted JSON (does not throw)', () => {
    localStorage.setItem('grant_collections', '{broken json');
    expect(loadCollections()).toEqual([]);
  });

  it('returns [] when stored object has no collections array', () => {
    localStorage.setItem('grant_collections', JSON.stringify({ foo: 'bar' }));
    expect(loadCollections()).toEqual([]);
  });

  it('returns collections array when valid', () => {
    const col = { name: 'Test', createdAt: '2026-01-01T00:00:00.000Z', items: [] };
    localStorage.setItem('grant_collections', JSON.stringify({ collections: [col] }));
    expect(loadCollections()).toEqual([col]);
  });
});

// --- createCollection ---

describe('createCollection', () => {
  it('adds a new collection', () => {
    const result = createCollection([], 'My Collection');
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe('My Collection');
    expect(result[0].items).toEqual([]);
    expect(result[0].createdAt).toBeTruthy();
  });

  it('throws if name already exists', () => {
    const existing = createCollection([], 'Existing');
    expect(() => createCollection(existing, 'Existing')).toThrow();
  });
});

// --- deleteCollection ---

describe('deleteCollection', () => {
  it('removes collection by name', () => {
    const cols = createCollection([], 'ToDelete');
    const result = deleteCollection(cols, 'ToDelete');
    expect(result).toHaveLength(0);
  });

  it('leaves other collections intact', () => {
    let cols = createCollection([], 'Keep');
    cols = createCollection(cols, 'Remove');
    const result = deleteCollection(cols, 'Remove');
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe('Keep');
  });
});

// --- addItemToCollection ---

describe('addItemToCollection', () => {
  it('adds an item to the named collection', () => {
    const cols = createCollection([], 'MyCol');
    const item = makeItem('nih', 'ABC123');
    const result = addItemToCollection(cols, 'MyCol', item);
    expect(result[0].items).toHaveLength(1);
    expect(result[0].items[0].sourceId).toBe('ABC123');
  });

  it('throws if source+sourceId already in collection', () => {
    let cols = createCollection([], 'MyCol');
    const item = makeItem('nih', 'DUP001');
    cols = addItemToCollection(cols, 'MyCol', item);
    expect(() => addItemToCollection(cols, 'MyCol', item)).toThrow();
  });

  it('allows same sourceId from different source', () => {
    let cols = createCollection([], 'MyCol');
    cols = addItemToCollection(cols, 'MyCol', makeItem('nih', 'SHARED'));
    const result = addItemToCollection(cols, 'MyCol', makeItem('cordis', 'SHARED'));
    expect(result[0].items).toHaveLength(2);
  });
});

// --- removeItemFromCollection ---

describe('removeItemFromCollection', () => {
  it('removes item from collection', () => {
    let cols = createCollection([], 'MyCol');
    cols = addItemToCollection(cols, 'MyCol', makeItem('nih', 'REM001'));
    cols = addItemToCollection(cols, 'MyCol', makeItem('nih', 'KEEP001'));
    const result = removeItemFromCollection(cols, 'MyCol', 'nih', 'REM001');
    expect(result[0].items).toHaveLength(1);
    expect(result[0].items[0].sourceId).toBe('KEEP001');
  });
});

// --- parseImportFile ---

describe('parseImportFile', () => {
  function makeFile(content, name) {
    return new File([content], name, { type: 'application/json' });
  }

  it('parses a valid JSON file', async () => {
    const payload = JSON.stringify({
      version: 1,
      tool: 'communication-grants',
      collectionName: 'From JSON',
      exportedAt: '2026-01-01T00:00:00.000Z',
      items: [
        { source: 'nih', sourceId: 'A1' },
        { source: 'cordis', sourceId: 'B1' },
      ],
    });
    const result = await parseImportFile(makeFile(payload, 'CZ_Grants.json'));
    expect(result.collectionName).toBe('CZ_Grants');
    expect(result.items).toHaveLength(2);
    expect(result.items[0]).toEqual({ source: 'nih', sourceId: 'A1' });
  });

  it('derives collection name from filename, not collectionName field', async () => {
    const payload = JSON.stringify({
      version: 1,
      items: [{ source: 'nih', sourceId: 'X1' }],
      collectionName: 'Should Be Ignored',
    });
    const result = await parseImportFile(makeFile(payload, 'my_file.json'));
    expect(result.collectionName).toBe('my_file');
  });

  it('rejects invalid JSON', async () => {
    await expect(parseImportFile(makeFile('{broken', 'bad.json'))).rejects.toThrow();
  });

  it('rejects missing items field', async () => {
    const payload = JSON.stringify({ version: 1 });
    await expect(parseImportFile(makeFile(payload, 'no-items.json'))).rejects.toThrow(
      /items/
    );
  });

  it('rejects version !== 1', async () => {
    const payload = JSON.stringify({ version: 2, items: [] });
    await expect(parseImportFile(makeFile(payload, 'v2.json'))).rejects.toThrow(
      /version/i
    );
  });

  it('rejects items missing source field', async () => {
    const payload = JSON.stringify({
      version: 1,
      items: [{ sourceId: 'X1' }],
    });
    await expect(parseImportFile(makeFile(payload, 'bad-item.json'))).rejects.toThrow(
      /source/
    );
  });
});
