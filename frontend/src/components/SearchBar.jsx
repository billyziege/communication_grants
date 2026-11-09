import React, { useState } from 'react';

function ChevronIcon({ className }) {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 12 12"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <path d="M2 4l4 4 4-4" />
    </svg>
  );
}

const SYNTAX_EXAMPLES = [
  ['climate change', 'both terms required (AND)'],
  ['"climate change"', 'exact phrase'],
  ['climate OR warming', 'either term'],
  ['climate NOT funding', 'exclude term'],
  ['communic*', 'prefix wildcard'],
];

export default function SearchBar({ value, onChange, onSearch }) {
  const [guideOpen, setGuideOpen] = useState(false);

  return (
    <div className="flex-1 flex flex-col max-w-2xl">
      {/* Search input row */}
      <div className="flex gap-2">
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
      </div>

      {/* Syntax guide toggle */}
      <div className="mt-1">
        <button
          type="button"
          onClick={() => setGuideOpen(o => !o)}
          className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 select-none"
          aria-expanded={guideOpen}
          aria-controls="search-syntax-guide"
        >
          <span className="font-semibold">Syntax guide</span>
          <ChevronIcon
            className={`transition-transform duration-200 ${guideOpen ? 'rotate-180' : ''}`}
          />
        </button>

        {guideOpen && (
          <div
            id="search-syntax-guide"
            className="mt-1.5 text-xs text-gray-700"
          >
            <table className="border-collapse">
              <tbody>
                {SYNTAX_EXAMPLES.map(([ex, desc]) => (
                  <tr key={ex}>
                    <td className="pr-4 pb-1 align-top">
                      <code className="bg-gray-100 px-1.5 py-0.5 rounded text-gray-800 font-mono whitespace-nowrap">
                        {ex}
                      </code>
                    </td>
                    <td className="pb-1 align-top text-gray-500">{desc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
