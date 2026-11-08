import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import FilterPanel from '../components/FilterPanel.jsx';
import { emptyFilters } from '../lib/facets.js';

function renderFilterPanel(overrides = {}) {
  const defaults = {
    filters: emptyFilters(),
    onApply: vi.fn(),
    onReset: vi.fn(),
  };
  return render(<FilterPanel {...defaults} {...overrides} />);
}

describe('FilterPanel', () => {
  it('renders without crashing with Apply and Reset buttons', () => {
    renderFilterPanel();
    expect(screen.getByRole('button', { name: /apply/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /reset/i })).toBeInTheDocument();
  });

  it('calls onApply when Apply button is clicked', () => {
    const onApply = vi.fn();
    renderFilterPanel({ onApply });
    fireEvent.click(screen.getByRole('button', { name: /apply/i }));
    expect(onApply).toHaveBeenCalledOnce();
    expect(onApply).toHaveBeenCalledWith(expect.objectContaining({ source: null }));
  });

  it('calls onReset when Reset button is clicked', () => {
    const onReset = vi.fn();
    renderFilterPanel({ onReset });
    fireEvent.click(screen.getByRole('button', { name: /reset/i }));
    expect(onReset).toHaveBeenCalledOnce();
  });

  it('Apply passes updated yearMin when year range min input changes', () => {
    const onApply = vi.fn();
    renderFilterPanel({ onApply });
    const [fromInput] = screen.getAllByPlaceholderText(/2007/);
    fireEvent.change(fromInput, { target: { value: '2015' } });
    fireEvent.click(screen.getByRole('button', { name: /apply/i }));
    expect(onApply).toHaveBeenCalledWith(expect.objectContaining({ yearMin: 2015 }));
  });

  it('Apply passes null yearMin when year field is cleared', () => {
    const onApply = vi.fn();
    renderFilterPanel({ onApply });
    const [fromInput] = screen.getAllByPlaceholderText(/2007/);
    fireEvent.change(fromInput, { target: { value: '2015' } });
    fireEvent.change(fromInput, { target: { value: '' } });
    fireEvent.click(screen.getByRole('button', { name: /apply/i }));
    expect(onApply).toHaveBeenCalledWith(expect.objectContaining({ yearMin: null }));
  });

  it('source toggles appear when availableSources are provided', () => {
    renderFilterPanel({ availableSources: ['NIH', 'CORDIS'] });
    expect(screen.getByLabelText('NIH')).toBeInTheDocument();
    expect(screen.getByLabelText('CORDIS')).toBeInTheDocument();
  });

  it('Apply passes selected source when NIH toggle is clicked', () => {
    const onApply = vi.fn();
    renderFilterPanel({ onApply, availableSources: ['NIH', 'CORDIS'] });
    fireEvent.click(screen.getByLabelText('NIH'));
    fireEvent.click(screen.getByRole('button', { name: /apply/i }));
    expect(onApply).toHaveBeenCalledWith(expect.objectContaining({ source: 'NIH' }));
  });

  it('country dropdown appears when availableCountries are provided', () => {
    renderFilterPanel({ availableCountries: ['CZ', 'DE', 'US'] });
    expect(screen.getByLabelText(/country filter/i)).toBeInTheDocument();
  });

  it('Apply passes country value when country dropdown changes', () => {
    const onApply = vi.fn();
    renderFilterPanel({ onApply, availableCountries: ['CZ', 'DE', 'US'] });
    const select = screen.getByLabelText(/country filter/i);
    fireEvent.change(select, { target: { value: 'CZ' } });
    fireEvent.click(screen.getByRole('button', { name: /apply/i }));
    expect(onApply).toHaveBeenCalledWith(expect.objectContaining({ country: 'CZ' }));
  });
});
