import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MasteryDeltaList, type MasteryDeltaItem } from './MasteryDeltaList';
import type { ConceptMasteryDelta } from '../api/types';

function delta(
  partial: Partial<ConceptMasteryDelta> = {},
): ConceptMasteryDelta {
  return {
    band_before: 'struggling',
    band_after: 'learning',
    pct_before: 34,
    pct_after: 61,
    n_observed_session: 2,
    ...partial,
  };
}

function items(n = 1): MasteryDeltaItem[] {
  return Array.from({ length: n }, (_, i) => ({
    concept_id: `c${i}`,
    label: i === 0 ? 'Set Operations' : `Concept ${i}`,
    delta: delta(
      i === 0
        ? {}
        : {
            band_before: 'learning',
            band_after: 'proficient',
            pct_before: 55,
            pct_after: 78,
          },
    ),
  }));
}

describe('MasteryDeltaList', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders band-led transition with trailing percentages', () => {
    render(<MasteryDeltaList items={items(1)} variant="live" />);
    expect(screen.getByText('Set Operations')).toBeInTheDocument();
    expect(screen.getByText('struggling')).toBeInTheDocument();
    expect(screen.getByText('learning')).toBeInTheDocument();
    expect(screen.getByText('34%')).toBeInTheDocument();
    expect(screen.getByText('61%')).toBeInTheDocument();
  });

  it('shows empty state for recap with no items', () => {
    render(<MasteryDeltaList items={[]} variant="recap" />);
    expect(screen.getByText('Concepts practiced')).toBeInTheDocument();
    expect(screen.getByText('No concepts practiced this session.')).toBeInTheDocument();
  });

  it('collapses to a compact line on Close summary', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<MasteryDeltaList items={items(2)} variant="recap" collapseAfterMs={5000} />);
    expect(screen.getByText('Concepts practiced')).toBeInTheDocument();
    expect(screen.getByText('Set Operations')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Close summary' }));

    expect(screen.getByText('2 concepts moved · 1 now proficient')).toBeInTheDocument();
    expect(
      screen.queryByRole('list'),
    ).not.toBeInTheDocument();
  });

  it('auto-collapses after the countdown', async () => {
    render(<MasteryDeltaList items={items(1)} variant="recap" collapseAfterMs={5000} />);
    expect(screen.getByText('Set Operations')).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5100);
    });

    expect(screen.getByText('1 concept moved')).toBeInTheDocument();
    expect(screen.queryByRole('list')).not.toBeInTheDocument();
  });

  it('pauses the countdown while hovered', async () => {
    render(<MasteryDeltaList items={items(1)} variant="recap" collapseAfterMs={5000} />);
    const section = screen.getByRole('region', { name: 'Concepts practiced' });

    fireEvent.pointerEnter(section);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(6000);
    });
    expect(screen.getByText('Set Operations')).toBeInTheDocument();

    fireEvent.pointerLeave(section);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5100);
    });
    expect(screen.getByText('1 concept moved')).toBeInTheDocument();
  });
});
