/**
 * export.js — file export/import helpers for grant collections.
 */

/**
 * Export a collection to a JSON file and trigger a browser download.
 * Only source + sourceId are exported — no snapshots.
 *
 * @param {Object} collection
 */
export function exportCollection(collection) {
  const payload = {
    version: 1,
    tool: 'communication-grants',
    collectionName: collection.name,
    exportedAt: new Date().toISOString(),
    items: collection.items.map(({ source, sourceId }) => ({ source, sourceId })),
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: 'application/json',
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = collection.name.replace(/\s+/g, '_') + '.json';
  a.click();
  URL.revokeObjectURL(url);
}

/**
 * Parse an imported collection file.
 *
 * The collection name is derived from the filename without extension
 * (not from the JSON collectionName field) so the tab name reflects
 * what the user named the file on disk.
 *
 * @param {File} file
 * @returns {Promise<{collectionName: string, items: Array<{source: string, sourceId: string}>}>}
 * @throws {Error} with a descriptive message on validation failure
 */
export async function parseImportFile(file) {
  const text = await file.text();

  let parsed;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new Error('Not valid JSON.');
  }

  if (parsed.version == null) {
    throw new Error('Missing required field: version.');
  }
  if (parsed.version !== 1) {
    throw new Error(`Unsupported version: ${parsed.version}. Expected 1.`);
  }
  if (!Array.isArray(parsed.items)) {
    throw new Error('Missing required field: items.');
  }

  for (let i = 0; i < parsed.items.length; i++) {
    const item = parsed.items[i];
    if (!item.source) {
      throw new Error(`Item at index ${i} is missing required field: source.`);
    }
    if (!item.sourceId) {
      throw new Error(`Item at index ${i} is missing required field: sourceId.`);
    }
  }

  // Derive collection name from filename without extension
  const collectionName = file.name.replace(/\.[^.]+$/, '');

  return {
    collectionName,
    items: parsed.items.map(({ source, sourceId }) => ({ source, sourceId })),
  };
}
