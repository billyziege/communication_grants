import React, { useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { parseImportFile } from '../lib/export.js';
import { createCollection } from '../lib/collections.js';

function TabButton({ label, active, isActiveSaveTarget, onClose, onClick }) {
  return (
    <div
      role="tab"
      aria-selected={active}
      className={`flex items-center gap-1 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap cursor-pointer ${
        active
          ? 'border-blue-600 text-blue-700'
          : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
      }`}
      onClick={onClick}
    >
      {isActiveSaveTarget && (
        <span className="w-1.5 h-1.5 rounded-full bg-blue-500 flex-shrink-0" title="Active collection — saves go here" />
      )}
      <span>{label}</span>
      {onClose && (
        <button
          type="button"
          aria-label={`Close ${label}`}
          onClick={e => {
            e.stopPropagation();
            onClose();
          }}
          className="ml-1 text-gray-400 hover:text-gray-700 leading-none text-xs"
        >
          ×
        </button>
      )}
    </div>
  );
}

export default function CollectionsPanel({
  collections,
  activeTab,
  activeCollectionName,
  onTabChange,
  onCreateCollection,
  onDeleteCollection,
  onImportCollection,
  importError,
}) {
  const [newName, setNewName] = useState('');
  const [createError, setCreateError] = useState('');
  const [dialogOpen, setDialogOpen] = useState(false);

  function handleCreate() {
    if (!newName.trim()) return;
    try {
      onCreateCollection(newName.trim());
      setNewName('');
      setCreateError('');
      setDialogOpen(false);
    } catch (err) {
      setCreateError(err.message);
    }
  }

  async function handleImport(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    // Reset so the same file can be re-selected after an error
    e.target.value = '';
    await onImportCollection(file);
  }

  return (
    <div className="flex border-b border-gray-200 bg-white flex-shrink-0 px-2 items-center gap-1">
      <div role="tablist" className="flex flex-1 overflow-x-auto">
        {/* Search tab — always first, cannot be closed */}
        <TabButton
          label="Search"
          active={activeTab === 'search'}
          onClick={() => onTabChange('search')}
        />

        {/* Collection tabs */}
        {collections.map(col => (
          <TabButton
            key={col.name}
            label={col.name}
            active={activeTab === col.name}
            isActiveSaveTarget={activeCollectionName === col.name}
            onClick={() => onTabChange(col.name)}
            onClose={() => onDeleteCollection(col.name)}
          />
        ))}
      </div>

      {/* Import error */}
      {importError && (
        <span className="text-xs text-red-600 px-2 flex-shrink-0 max-w-xs">
          {importError}
        </span>
      )}

      {/* Import button */}
      <label
        className="flex-shrink-0 px-2 py-1 text-xs text-gray-600 border border-gray-200 rounded cursor-pointer hover:bg-gray-50"
        title="Import collection from JSON"
      >
        Import
        <input
          type="file"
          accept=".json"
          className="hidden"
          onChange={handleImport}
        />
      </label>

      {/* New collection dialog */}
      <Dialog.Root open={dialogOpen} onOpenChange={setDialogOpen}>
        <Dialog.Trigger asChild>
          <button
            type="button"
            className="flex-shrink-0 px-2 py-1 text-xs font-semibold text-gray-600 border border-gray-200 rounded hover:bg-gray-50"
            aria-label="Create new collection"
          >
            +
          </button>
        </Dialog.Trigger>

        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/30 z-50" />
          <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 bg-white rounded-lg border border-gray-200 shadow-xl p-6 z-50 w-80">
            <Dialog.Title className="text-base font-semibold text-gray-900 mb-4">
              New collection
            </Dialog.Title>
            <input
              type="text"
              value={newName}
              onChange={e => {
                setNewName(e.target.value);
                setCreateError('');
              }}
              onKeyDown={e => e.key === 'Enter' && handleCreate()}
              placeholder="Collection name"
              autoFocus
              className="w-full text-sm border border-gray-200 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400 mb-2"
              aria-label="New collection name"
            />
            {createError && (
              <p className="text-xs text-red-600 mb-2">{createError}</p>
            )}
            <div className="flex gap-2 justify-end">
              <Dialog.Close asChild>
                <button
                  type="button"
                  className="px-3 py-1.5 text-sm border border-gray-200 text-gray-600 rounded-md hover:bg-gray-50"
                >
                  Cancel
                </button>
              </Dialog.Close>
              <button
                type="button"
                onClick={handleCreate}
                disabled={!newName.trim()}
                className="px-3 py-1.5 text-sm font-medium bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
              >
                Create
              </button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
