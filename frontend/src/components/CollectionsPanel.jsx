import React, { useState, useRef } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { parseImportFile } from '../lib/export.js';
import { exportCollection } from '../lib/export.js';

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
        <span
          className="w-1.5 h-1.5 rounded-full bg-blue-500 flex-shrink-0"
          title="Active collection — saves go here"
        />
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
  const fileInputRef = useRef(null);

  const activeCollection = collections.find(c => c.name === activeCollectionName) ?? null;

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

  async function handleImportFile(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = '';
    await onImportCollection(file);
  }

  function handleExport() {
    if (activeCollection) exportCollection(activeCollection);
  }

  return (
    <div className="flex border-b border-gray-200 bg-white flex-shrink-0 px-2 items-center gap-1">
      <div role="tablist" className="flex flex-1 overflow-x-auto items-center">
        {/* Search / Results tab */}
        <TabButton
          label="Results"
          active={activeTab === 'search'}
          onClick={() => onTabChange('search')}
        />

        {/* Separator + Collections label */}
        {collections.length > 0 && (
          <>
            <div className="w-px h-5 bg-gray-300 mx-1 flex-shrink-0" />
            <span className="text-xs font-bold text-gray-500 uppercase tracking-wide whitespace-nowrap px-1 flex-shrink-0">
              Collections
            </span>
          </>
        )}

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
        <span className="text-xs text-red-600 px-2 flex-shrink-0 max-w-xs truncate" title={importError}>
          {importError}
        </span>
      )}

      {/* Hidden file input for import */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".json"
        className="hidden"
        data-testid="import-file-input"
        onChange={handleImportFile}
      />

      {/* Collections menu */}
      <Dialog.Root open={dialogOpen} onOpenChange={setDialogOpen}>
        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <button
              type="button"
              className="flex-shrink-0 px-2 py-1.5 text-gray-500 hover:text-gray-800 hover:bg-gray-100 rounded focus:outline-none"
              aria-label="Collections menu"
              title="Collections menu"
            >
              {/* Three-line (hamburger) icon */}
              <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                <rect x="2" y="3.5" width="12" height="1.5" rx="0.75" />
                <rect x="2" y="7.25" width="12" height="1.5" rx="0.75" />
                <rect x="2" y="11" width="12" height="1.5" rx="0.75" />
              </svg>
            </button>
          </DropdownMenu.Trigger>

          <DropdownMenu.Portal>
            <DropdownMenu.Content
              align="end"
              sideOffset={4}
              className="min-w-[200px] bg-white rounded-md border border-gray-200 shadow-lg py-1 z-50"
            >
              <Dialog.Trigger asChild>
                <DropdownMenu.Item className="px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 cursor-pointer focus:outline-none focus:bg-gray-50 select-none">
                  Create collection tab
                </DropdownMenu.Item>
              </Dialog.Trigger>

              <DropdownMenu.Item
                className="px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 cursor-pointer focus:outline-none focus:bg-gray-50 select-none"
                onSelect={() => fileInputRef.current?.click()}
              >
                Import collection
              </DropdownMenu.Item>

              <DropdownMenu.Separator className="my-1 h-px bg-gray-100" />

              <DropdownMenu.Item
                className={`px-3 py-2 text-sm focus:outline-none select-none ${
                  activeCollection
                    ? 'text-gray-700 hover:bg-gray-50 cursor-pointer focus:bg-gray-50'
                    : 'text-gray-300 cursor-not-allowed'
                }`}
                disabled={!activeCollection}
                onSelect={handleExport}
              >
                Save active collection
                {activeCollectionName && (
                  <span className="ml-1 text-gray-400 text-xs">({activeCollectionName})</span>
                )}
              </DropdownMenu.Item>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>

        {/* Create collection dialog */}
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
