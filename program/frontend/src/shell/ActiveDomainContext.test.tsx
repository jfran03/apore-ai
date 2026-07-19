import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { KnowledgeCatalog, KnowledgeChapter } from '../api/types';

const getKnowledgeCatalog = vi.fn();

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client');
  return { ...actual, getKnowledgeCatalog: () => getKnowledgeCatalog() };
});

import { ActiveDomainProvider, useActiveDomain } from './ActiveDomainContext';
import { getStoredKnowledgeSource } from '../api/client';

function chapter(id: string, domainId: string): KnowledgeChapter {
  return {
    id,
    knowledge_source: `domain:${domainId}/${id}`,
    sources_present: false,
    source_count: 0,
    source_files: [],
    has_concept_graph: false,
    wiki_count: 0,
    has_question_bank: false,
    question_bank_count: 0,
    compile_stage: 'idle',
    is_approved: false,
    is_stale: false,
    has_unapproved_compile: false,
  };
}

function catalogFixture(): KnowledgeCatalog {
  return {
    fixtures: [],
    domains: [
      { id: 'alpha', chapters: [chapter('ch1', 'alpha'), chapter('ch2', 'alpha')] },
      { id: 'beta', chapters: [chapter('b1', 'beta')] },
    ],
  };
}

function Probe() {
  const { activeDomainId, activeChapterId, setActiveDomainId, setActiveChapterId } =
    useActiveDomain();
  return (
    <div>
      <span data-testid="domain">{activeDomainId ?? 'none'}</span>
      <span data-testid="chapter">{activeChapterId ?? 'none'}</span>
      <button onClick={() => setActiveDomainId('beta')}>switch-domain</button>
      <button onClick={() => setActiveChapterId('ch2')}>switch-chapter</button>
    </div>
  );
}

function renderProbe() {
  return render(
    <ActiveDomainProvider>
      <Probe />
    </ActiveDomainProvider>,
  );
}

beforeEach(() => {
  getKnowledgeCatalog.mockReset();
  localStorage.clear();
});

describe('ActiveDomainContext', () => {
  it('defaults to the first domain and chapter when nothing is stored', async () => {
    getKnowledgeCatalog.mockResolvedValue(catalogFixture());
    renderProbe();
    await waitFor(() => expect(screen.getByTestId('domain')).toHaveTextContent('alpha'));
    expect(screen.getByTestId('chapter')).toHaveTextContent('ch1');
  });

  it('falls back to the first domain when the stored domain is missing', async () => {
    localStorage.setItem('apore.knowledge_source', 'domain:ghost/x');
    getKnowledgeCatalog.mockResolvedValue(catalogFixture());
    renderProbe();
    await waitFor(() => expect(screen.getByTestId('domain')).toHaveTextContent('alpha'));
    expect(screen.getByTestId('chapter')).toHaveTextContent('ch1');
  });

  it('restores a valid stored chapter selection', async () => {
    localStorage.setItem('apore.knowledge_source', 'domain:alpha/ch2');
    getKnowledgeCatalog.mockResolvedValue(catalogFixture());
    renderProbe();
    await waitFor(() => expect(screen.getByTestId('chapter')).toHaveTextContent('ch2'));
  });

  it('switching domain snaps to the first chapter of that domain and persists', async () => {
    getKnowledgeCatalog.mockResolvedValue(catalogFixture());
    renderProbe();
    await waitFor(() => expect(screen.getByTestId('domain')).toHaveTextContent('alpha'));

    await userEvent.click(screen.getByText('switch-domain'));
    expect(screen.getByTestId('domain')).toHaveTextContent('beta');
    expect(screen.getByTestId('chapter')).toHaveTextContent('b1');
    expect(getStoredKnowledgeSource()).toBe('domain:beta/b1');
  });

  it('switching chapter persists the knowledge source', async () => {
    getKnowledgeCatalog.mockResolvedValue(catalogFixture());
    renderProbe();
    await waitFor(() => expect(screen.getByTestId('chapter')).toHaveTextContent('ch1'));

    await userEvent.click(screen.getByText('switch-chapter'));
    expect(screen.getByTestId('chapter')).toHaveTextContent('ch2');
    expect(getStoredKnowledgeSource()).toBe('domain:alpha/ch2');
  });

  it('handles an empty catalog without crashing and retains the stored selection', async () => {
    localStorage.setItem('apore.knowledge_source', 'domain:kept/x');
    getKnowledgeCatalog.mockResolvedValue({ fixtures: [], domains: [] });
    renderProbe();
    await waitFor(() => expect(screen.getByTestId('domain')).toHaveTextContent('kept'));
    expect(screen.getByTestId('chapter')).toHaveTextContent('x');
  });
});
