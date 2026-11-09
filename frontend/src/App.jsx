import React, { useState } from 'react';
import { RelayEnvironmentProvider } from 'react-relay';
import { RelayEnvironment } from './relay/environment.js';
import SearchBar from './components/SearchBar.jsx';
import GrantsPage from './pages/GrantsPage.jsx';

export default function App() {
  const [searchValue, setSearchValue] = useState('');
  const [pendingSearch, setPendingSearch] = useState(null);

  function handleSearch(query) {
    setPendingSearch({ query, timestamp: Date.now() });
  }

  return (
    <RelayEnvironmentProvider environment={RelayEnvironment}>
      <div className="h-screen flex flex-col bg-gray-50">
        <header className="flex-shrink-0 bg-white border-b border-gray-200 px-6 py-3 flex items-start gap-4">
          <h1 className="text-xl font-semibold text-gray-900 flex-shrink-0 mt-1">
            Communication Grants
          </h1>
          <SearchBar
            value={searchValue}
            onChange={setSearchValue}
            onSearch={handleSearch}
          />
        </header>
        <main className="flex-1 overflow-hidden">
          <GrantsPage
            pendingSearch={pendingSearch}
            searchValue={searchValue}
          />
        </main>
      </div>
    </RelayEnvironmentProvider>
  );
}
