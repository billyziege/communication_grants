import React from 'react';

function InfoIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <circle cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="1.5" />
      <path d="M7 6.5v4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="7" cy="4" r="0.8" fill="currentColor" />
    </svg>
  );
}

export default function SearchBar({ value, onChange, onSearch }) {
  return (
    <div className="flex flex-1 gap-2 max-w-2xl items-center">
      <input
        type="search"
        placeholder="Search grant abstracts…"
        className="flex-1 text-sm border border-gray-200 rounded-md px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
        value={value}
        onChange={e => onChange(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && onSearch(value)}
        aria-label="Search query"
      />
      <button
        type="button"
        onClick={() => onSearch(value)}
        className="flex-shrink-0 px-4 py-1.5 text-sm font-medium bg-blue-600 text-white rounded-md hover:bg-blue-700"
      >
        Search
      </button>

      {/* Syntax help */}
      <div className="relative group flex-shrink-0">
        <button
          type="button"
          className="flex items-center justify-center w-6 h-6 text-gray-400 hover:text-gray-600 rounded-full focus:outline-none focus:ring-1 focus:ring-blue-400"
          aria-label="Search syntax help"
        >
          <InfoIcon />
        </button>

        <div className="hidden group-hover:block absolute right-0 top-full mt-1.5 w-72 bg-white border border-gray-200 rounded-lg shadow-lg p-3 z-50 text-xs text-gray-700">
          <p className="font-semibold text-gray-800 mb-2">Search syntax</p>
          <table className="w-full border-collapse">
            <tbody className="space-y-1">
              {[
                ['climate change', 'both terms (AND)'],
                ['"climate change"', 'exact phrase'],
                ['climate OR warming', 'either term'],
                ['climate NOT funding', 'exclude term'],
                ['communic*', 'prefix wildcard'],
              ].map(([ex, desc]) => (
                <tr key={ex}>
                  <td className="pr-3 pb-1 align-top">
                    <code className="bg-gray-100 px-1 py-0.5 rounded text-gray-800 font-mono whitespace-nowrap">
                      {ex}
                    </code>
                  </td>
                  <td className="pb-1 align-top text-gray-500">{desc}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
