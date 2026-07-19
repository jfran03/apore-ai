import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ChapterArtifactStatus, WikiPageView, WikiPreview } from '../../api/types';

const getWikiPreview = vi.fn();
const setConceptOrder = vi.fn();

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client');
  return {
    ...actual,
    getWikiPreview: (...args: unknown[]) => getWikiPreview(...args),
    setConceptOrder: (...args: unknown[]) => setConceptOrder(...args),
  };
});

import { CompiledWikiPanel, computeReorder } from './CompiledWikiPanel';

function page(id: string, label: string, depth: number, order: number, body: string): WikiPageView {
  return { concept_id: id, label, depth, order, body };
}

function preview(pages: WikiPageView[]): WikiPreview {
  return { source: 'published', version: 1, pages, edges: [] };
}

function artifact(overrides: Partial<ChapterArtifactStatus> = {}): ChapterArtifactStatus {
  return {
    source_hash: 'h',
    compile: {
      stage: 'ready',
      version: 1,
      source_hash: 'h',
      progress: { done: 0, total: 0 },
      error_code: null,
      error_message: null,
      started_at: null,
      updated_at: null,
    },
    approved: { version: 1, source_hash: 'h', approved_at: null, legacy: false },
    is_approved: true,
    is_stale: false,
    has_unapproved_compile: false,
    wiki_count: 2,
    concept_count: 2,
    ...overrides,
  };
}

const noop = async () => {};

beforeEach(() => {
  getWikiPreview.mockReset();
  setConceptOrder.mockReset();
});

describe('computeReorder', () => {
  const pages = [page('a', 'A', 0, 0, 'a'), page('b', 'B', 1, 1, 'b'), page('c', 'C', 2, 2, 'c')];

  it('moves the active page to the target position', () => {
    const result = computeReorder(pages, 'c', 'a');
    expect(result.map((p) => p.concept_id)).toEqual(['c', 'a', 'b']);
  });

  it('returns the same reference for a no-op move', () => {
    expect(computeReorder(pages, 'a', 'a')).toBe(pages);
  });
});

describe('CompiledWikiPanel', () => {
  it('renders the concept body as formatted Markdown, not raw text', async () => {
    getWikiPreview.mockResolvedValue(
      preview([page('alpha', 'Alpha', 0, 0, '# Overview\n\nThis is **bold** copy.')]),
    );
    render(<CompiledWikiPanel knowledgeSource="domain:x/y" artifact={artifact()} onApprove={noop} onRetryCompile={noop} />);

    const toggle = await screen.findByRole('button', { name: /Alpha/ });
    await userEvent.click(toggle);

    expect(screen.getByRole('heading', { name: 'Overview' })).toBeInTheDocument();
    const strong = screen.getByText('bold');
    expect(strong.tagName).toBe('STRONG');
    expect(screen.queryByText('# Overview')).not.toBeInTheDocument();
  });

  it('does not show the passive Approved banner once approved', async () => {
    getWikiPreview.mockResolvedValue(preview([page('alpha', 'Alpha', 0, 0, 'Body.')]));
    render(<CompiledWikiPanel knowledgeSource="domain:x/y" artifact={artifact()} onApprove={noop} onRetryCompile={noop} />);

    await screen.findByRole('button', { name: /Alpha/ });
    expect(screen.queryByText(/Approved/)).not.toBeInTheDocument();
  });

  it('still warns when sources changed after approval', async () => {
    getWikiPreview.mockResolvedValue(preview([page('alpha', 'Alpha', 0, 0, 'Body.')]));
    render(
      <CompiledWikiPanel
        knowledgeSource="domain:x/y"
        artifact={artifact({ is_stale: true })}
        onApprove={noop}
        onRetryCompile={noop}
      />,
    );

    expect(await screen.findByText(/Sources changed since the approved version/)).toBeInTheDocument();
  });

  it('exposes an accessible reorder handle per concept', async () => {
    getWikiPreview.mockResolvedValue(
      preview([page('alpha', 'Alpha', 0, 0, 'A.'), page('beta', 'Beta', 1, 1, 'B.')]),
    );
    render(<CompiledWikiPanel knowledgeSource="domain:x/y" artifact={artifact()} onApprove={noop} onRetryCompile={noop} />);

    expect(await screen.findByRole('button', { name: 'Reorder Alpha' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reorder Beta' })).toBeInTheDocument();
    expect(screen.getByText(/drag to set teaching order/)).toBeInTheDocument();
  });

  it('keeps a concept collapsed until its toggle is clicked', async () => {
    getWikiPreview.mockResolvedValue(preview([page('alpha', 'Alpha', 0, 0, 'Hidden body copy.')]));
    render(<CompiledWikiPanel knowledgeSource="domain:x/y" artifact={artifact()} onApprove={noop} onRetryCompile={noop} />);

    const toggle = await screen.findByRole('button', { name: /Alpha/ });
    expect(screen.queryByText('Hidden body copy.')).not.toBeInTheDocument();
    await userEvent.click(toggle);
    expect(screen.getByText('Hidden body copy.')).toBeInTheDocument();
  });
});
