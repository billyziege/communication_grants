import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import FilterPanel from '../components/FilterPanel.jsx';

function renderFilterPanel(overrides = {}) {
  const defaults = {
    source: null,
    onSourceChange: vi.fn(),
    onFacetsChange: vi.fn(),
    onSearch: vi.fn(),
  };
  return render(<FilterPanel {...defaults} {...overrides} />);
}

describe('FilterPanel', () => {
  it('renders without crashing', () => {
    renderFilterPanel();
    expect(screen.getByRole('button', { name: /search/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /reset/i })).toBeInTheDocument();
  });

  it('calls onSearch when Search button is clicked', () => {
    const onSearch = vi.fn();
    renderFilterPanel({ onSearch });
    fireEvent.click(screen.getByRole('button', { name: /search/i }));
    expect(onSearch).toHaveBeenCalledOnce();
  });

  it('calls onSourceChange with NIH when NIH toggle is clicked', () => {
    const onSourceChange = vi.fn();
    renderFilterPanel({ onSourceChange });
    const nihButton = screen.getByRole('radio', { name: /nih/i }) ||
      screen.getByLabelText('NIH');
    fireEvent.click(nihButton);
    expect(onSourceChange).toHaveBeenCalledWith('NIH');
  });

  it('calls onFacetsChange when year range min input changes', () => {
    const onFacetsChange = vi.fn();
    renderFilterPanel({ onFacetsChange });
    const inputs = screen.getAllByPlaceholderText(/2007/);
    fireEvent.change(inputs[0], { target: { value: '2015' } });
    expect(onFacetsChange).toHaveBeenCalledWith(
      expect.objectContaining({ startYearMin: 2015 })
    );
  });

  it('calls onFacetsChange with null when year field is cleared after being set', () => {
    const onFacetsChange = vi.fn();
    renderFilterPanel({ onFacetsChange });
    const inputs = screen.getAllByPlaceholderText(/2007/);
    // First set a value
    fireEvent.change(inputs[0], { target: { value: '2015' } });
    expect(onFacetsChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ startYearMin: 2015 })
    );
    // Then clear it
    fireEvent.change(inputs[0], { target: { value: '' } });
    expect(onFacetsChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ startYearMin: null })
    );
  });

  it('Reset button calls onSourceChange(null) and onFacetsChange with empty facets', () => {
    const onSourceChange = vi.fn();
    const onFacetsChange = vi.fn();
    renderFilterPanel({ onSourceChange, onFacetsChange });
    fireEvent.click(screen.getByRole('button', { name: /reset/i }));
    expect(onSourceChange).toHaveBeenCalledWith(null);
    expect(onFacetsChange).toHaveBeenCalledWith(
      expect.objectContaining({
        startYearMin: null,
        startYearMax: null,
        country: '',
        fundingMin: null,
        fundingMax: null,
      })
    );
  });

  it('calls onFacetsChange with country value when country input changes', () => {
    const onFacetsChange = vi.fn();
    renderFilterPanel({ onFacetsChange });
    const countryInput = screen.getByLabelText(/country/i);
    fireEvent.change(countryInput, { target: { value: 'CZ' } });
    expect(onFacetsChange).toHaveBeenCalledWith(
      expect.objectContaining({ country: 'CZ' })
    );
  });
});
