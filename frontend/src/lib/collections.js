/**
 * collections.js — localStorage helpers for named grant collections.
 *
 * Collections are stored under the key "grant_collections" in localStorage.
 * All functions are pure with the exception of loadCollections/saveCollections
 * which interact with localStorage.
 *
 * localStorage access is wrapped in try/catch so the app degrades gracefully
 * in private browsing or when storage is blocked.
 */

const STORAGE_KEY = 'grant_collections';

/**
 * Load collections from localStorage.
 * Returns [] if the key is absent, storage is blocked, or JSON is corrupted.
 *
 * @returns {Array<Collection>}
 */
export function loadCollections() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!parsed || !Array.isArray(parsed.collections)) return [];
    return parsed.collections;
  } catch {
    return [];
  }
}

/**
 * Persist collections to localStorage.
 * Silently ignores errors (blocked storage, quota exceeded, etc.).
 *
 * @param {Array<Collection>} collections
 */
export function saveCollections(collections) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ collections }));
  } catch {
    // ignore — app still works in-memory
  }
}

/**
 * Create a new, empty collection.
 * Throws if a collection with that name already exists.
 *
 * @param {Array<Collection>} collections
 * @param {string} name
 * @returns {Array<Collection>} new array
 */
export function createCollection(collections, name) {
  if (collections.some(c => c.name === name)) {
    throw new Error(`A collection named '${name}' already exists.`);
  }
  return [
    ...collections,
    {
      name,
      createdAt: new Date().toISOString(),
      items: [],
    },
  ];
}

/**
 * Delete a collection by name.
 *
 * @param {Array<Collection>} collections
 * @param {string} name
 * @returns {Array<Collection>} new array
 */
export function deleteCollection(collections, name) {
  return collections.filter(c => c.name !== name);
}

/**
 * Add a grant snapshot to a named collection.
 * Throws if source+sourceId already exists in that collection.
 *
 * @param {Array<Collection>} collections
 * @param {string} name  — collection name
 * @param {Object} item  — grant snapshot
 * @returns {Array<Collection>} new array
 */
export function addItemToCollection(collections, name, item) {
  return collections.map(c => {
    if (c.name !== name) return c;
    const duplicate = c.items.some(
      i => i.source === item.source && i.sourceId === item.sourceId
    );
    if (duplicate) {
      throw new Error(
        `Grant ${item.sourceId} (${item.source}) is already in collection '${name}'.`
      );
    }
    return { ...c, items: [...c.items, item] };
  });
}

/**
 * Remove a grant from a named collection.
 *
 * @param {Array<Collection>} collections
 * @param {string} name  — collection name
 * @param {string} source
 * @param {string} sourceId
 * @returns {Array<Collection>} new array
 */
export function removeItemFromCollection(collections, name, source, sourceId) {
  return collections.map(c => {
    if (c.name !== name) return c;
    return {
      ...c,
      items: c.items.filter(
        i => !(i.source === source && i.sourceId === sourceId)
      ),
    };
  });
}
