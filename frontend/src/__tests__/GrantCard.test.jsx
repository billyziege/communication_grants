import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { GrantCardContent } from '../components/GrantCard.jsx';

// GrantCardContent is the pure presentational component — no Relay dependency.
// We test it directly with plain data objects.

const mockGrant = {
  id: 'grant:1',
  title: 'Neural Network Research for Brain Disorders',
  organization: 'University of Prague',
  country: 'CZ',
  source: 'NIH',
  sourceId: 'APP123456',
  sourceProgramme: null,
  sourceUrl: 'https://example.com/grant/1',
  startDate: '2020-01-01',
  endDate: '2024-12-31',
  fundingAmount: 1200000,
  fundingCurrency: 'USD',
};

const mockCordisGrant = {
  id: 'grant:2',
  title: 'European Climate Research Initiative',
  organization: 'TU Berlin',
  country: 'DE',
  source: 'CORDIS',
  sourceId: 'PROJ789',
  sourceProgramme: 'horizon_europe',
  sourceUrl: 'https://cordis.europa.eu/project/id/789',
  startDate: '2021-06-01',
  endDate: '2026-05-31',
  fundingAmount: 2500000,
  fundingCurrency: 'EUR',
};

describe('GrantCardContent', () => {
  it('renders title', () => {
    render(<GrantCardContent grant={mockGrant} />);
    expect(screen.getByTestId('grant-title')).toHaveTextContent(
      'Neural Network Research for Brain Disorders'
    );
  });

  it('renders organization and country', () => {
    render(<GrantCardContent grant={mockGrant} />);
    expect(screen.getByTestId('grant-org')).toHaveTextContent('University of Prague · CZ');
  });

  it('renders NIH source badge with correct class', () => {
    render(<GrantCardContent grant={mockGrant} />);
    const badge = screen.getByTestId('source-badge');
    expect(badge).toHaveTextContent('NIH');
    expect(badge.className).toContain('blue');
  });

  it('renders CORDIS source badge with correct class', () => {
    render(<GrantCardContent grant={mockCordisGrant} />);
    const badge = screen.getByTestId('source-badge');
    expect(badge).toHaveTextContent('CORDIS');
    expect(badge.className).toContain('green');
  });

  it('calls onSave with correct snapshot data when save button clicked', () => {
    const onSave = vi.fn();
    render(
      <GrantCardContent
        grant={mockGrant}
        onSave={onSave}
        isSaved={false}
        saveDisabled={false}
      />
    );
    fireEvent.click(screen.getByTestId('save-button'));
    expect(onSave).toHaveBeenCalledOnce();
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
      id: 'grant:1',
      sourceId: 'APP123456',
    }));
  });

  it('calls onSelect when card body is clicked', () => {
    const onSelect = vi.fn();
    render(
      <GrantCardContent
        grant={mockGrant}
        onSelect={onSelect}
        saveDisabled={true}
      />
    );
    fireEvent.click(screen.getByTestId('grant-card'));
    expect(onSelect).toHaveBeenCalledWith('grant:1');
  });

  it('save button does not call onSave when saveDisabled', () => {
    const onSave = vi.fn();
    render(
      <GrantCardContent
        grant={mockGrant}
        onSave={onSave}
        isSaved={false}
        saveDisabled={true}
      />
    );
    fireEvent.click(screen.getByTestId('save-button'));
    expect(onSave).not.toHaveBeenCalled();
  });

  it('shows programme badge for CORDIS grants with sourceProgramme', () => {
    render(<GrantCardContent grant={mockCordisGrant} />);
    expect(screen.getByText('horizon_europe')).toBeInTheDocument();
  });

  it('does not show programme badge for NIH grants', () => {
    render(<GrantCardContent grant={mockGrant} />);
    expect(screen.queryByText('horizon_europe')).not.toBeInTheDocument();
  });

  it('renders with null organization gracefully', () => {
    const grant = { ...mockGrant, organization: null };
    render(<GrantCardContent grant={grant} />);
    expect(screen.getByTestId('grant-title')).toBeInTheDocument();
  });
});
