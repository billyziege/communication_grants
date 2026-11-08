import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, act, waitFor } from '@testing-library/react';
import { MockPayloadGenerator } from 'relay-test-utils';
import { createEnv, renderWithRelay, queueResolver, resolveOperation } from './relayTestUtils.jsx';
import GrantsPage from '../pages/GrantsPage.jsx';

// Mock parseImportFile for import tests
vi.mock('../lib/export.js', async importOriginal => {
  const actual = await importOriginal();
  return {
    ...actual,
    parseImportFile: vi.fn(),
  };
});

beforeEach(() => {
  localStorage.clear();
});

describe('GrantsPage', () => {
  it('shows empty search state on initial render', () => {
    const env = createEnv();
    renderWithRelay(<GrantsPage />, env);
    expect(screen.getByTestId('empty-search-state')).toBeInTheDocument();
  });

  it('submitting a search loads the Relay query', async () => {
    const env = createEnv();
    queueResolver(env, {
      SearchGrantConnection: () => ({
        totalCount: 2,
        edges: [
          {
            node: {
              id: 'grant:1',
              title: 'Test Grant Alpha',
              organization: 'Test Org',
              country: 'US',
              source: 'NIH',
              sourceId: 'T001',
              sourceProgramme: null,
              sourceUrl: 'https://example.com/1',
              startDate: '2020-01-01',
              endDate: '2024-12-31',
              fundingAmount: 500000,
              fundingCurrency: 'USD',
            },
          },
        ],
      }),
    });

    renderWithRelay(<GrantsPage pendingSearch={{ query: 'cancer', timestamp: 1 }} />, env);

    await act(async () => {});

    // Should have left empty state and show results
    expect(screen.queryByTestId('empty-search-state')).not.toBeInTheDocument();
  });

  it('switching to a collection tab shows collection content instead of search results', async () => {
    // Pre-populate localStorage with a collection
    const col = {
      name: 'My Test Collection',
      createdAt: '2026-01-01T00:00:00.000Z',
      items: [
        {
          source: 'NIH',
          sourceId: 'TEST001',
          title: 'Saved Grant Title',
          organization: 'Test Org',
          country: 'US',
          startDate: '2021-01-01',
          endDate: '2025-12-31',
          fundingAmount: null,
          fundingCurrency: null,
          sourceProgramme: null,
          sourceUrl: 'https://example.com',
        },
      ],
    };
    localStorage.setItem('grant_collections', JSON.stringify({ collections: [col] }));

    const env = createEnv();
    renderWithRelay(<GrantsPage />, env);

    // Click on the collection tab
    const collectionTab = screen.getByText('My Test Collection');
    act(() => { collectionTab.click(); });

    // Should show the saved grant
    await waitFor(() => {
      expect(screen.getByText('Saved Grant Title')).toBeInTheDocument();
    });
  });

  it('shows import error when duplicate collection name', async () => {
    const { parseImportFile } = await import('../lib/export.js');
    parseImportFile.mockResolvedValueOnce({
      collectionName: 'Existing Collection',
      items: [{ source: 'nih', sourceId: 'X1' }],
    });

    // Pre-populate with existing collection
    const col = {
      name: 'Existing Collection',
      createdAt: '2026-01-01T00:00:00.000Z',
      items: [],
    };
    localStorage.setItem('grant_collections', JSON.stringify({ collections: [col] }));

    const env = createEnv();
    renderWithRelay(<GrantsPage />, env);

    // Trigger an import by calling handleImportCollection indirectly
    // We simulate by finding the import input
    const importLabel = screen.getByText('Import');
    const fileInput = importLabel.closest('label').querySelector('input[type="file"]');

    const file = new File(['{}'], 'Existing Collection.json', { type: 'application/json' });
    Object.defineProperty(fileInput, 'files', {
      value: [file],
      writable: false,
    });

    await act(async () => {
      fileInput.dispatchEvent(new Event('change', { bubbles: true }));
    });

    await waitFor(() => {
      expect(screen.getByText(/already exists/i)).toBeInTheDocument();
    });
  });
});
