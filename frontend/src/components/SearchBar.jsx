import React from 'react';

export default function SearchBar({ value, onChange, onSearch }) {
  return (
    <div className="flex flex-1 gap-2 max-w-2xl">
      <input
        type="search"
        placeholder="Search grants by keyword…"
        className="flex-1 text-sm border border-gray-200 rounded-md px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
        value={value}
        onChange={e => onChange(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && onSearch(value)}
        aria-label="Search query"
      />
      <button
        type="button"
        onClick={() => onSearch(value)}
        className="px-4 py-1.5 text-sm font-medium bg-blue-600 text-white rounded-md hover:bg-blue-700"
      >
        Search
      </button>
    </div>
  );
}
