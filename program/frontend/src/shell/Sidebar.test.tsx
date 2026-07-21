import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { KnowledgeCatalog, KnowledgeChapter, KnowledgeDomain, SessionSummary } from '../api/types';

const renameDomain = vi.fn();
const deleteDomain = vi.fn();
const refreshCatalog = vi.fn();
const refreshSessions = vi.fn();
const setActiveDomainId = vi.fn();

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client');
  return {
    ...actual,
    renameDomain: (...args: unknown[]) => renameDomain(...args),
    deleteDomain: (...args: unknown[]) => deleteDomain(...args),
    createDomain: vi.fn(),
  };
});

vi.mock('./ActiveDomainContext', async () => {
  const actual = await vi.importActual<typeof import('./ActiveDomainContext')>(
    './ActiveDomainContext',
  );
  return {
    ...actual,
    useActiveDomain: () => mockActiveDomain,
  };
});

import { Sidebar } from './Sidebar';

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

function domain(id: string, chapters: KnowledgeChapter[]): KnowledgeDomain {
  return { id, chapters };
}

function session(domainId: string, chapterId: string, title: string): SessionSummary {
  return {
    session_id: `${domainId}-${chapterId}-session`,
    title,
    created_at: '2026-07-01T00:00:00+00:00',
    knowledge_source: `domain:${domainId}/${chapterId}`,
  };
}

const sampleSessions = [
  session('alpha', 'ch1', 'Alpha practice'),
  session('beta', 'b1', 'Beta practice'),
];

let mockActiveDomain: {
  catalog: KnowledgeCatalog | null;
  sessions: SessionSummary[];
  sessionsLoaded: boolean;
  activeDomainId: string | null;
  setActiveDomainId: typeof setActiveDomainId;
  refreshCatalog: typeof refreshCatalog;
  refreshSessions: typeof refreshSessions;
};

function renderSidebar() {
  return render(
    <MemoryRouter>
      <Sidebar />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  renameDomain.mockReset();
  deleteDomain.mockReset();
  refreshCatalog.mockReset().mockResolvedValue(undefined);
  refreshSessions.mockReset().mockResolvedValue(undefined);
  setActiveDomainId.mockReset();
  mockActiveDomain = {
    catalog: {
      fixtures: [],
      domains: [
        domain('alpha', [chapter('ch1', 'alpha')]),
        domain('beta', [chapter('b1', 'beta')]),
      ],
    },
    sessions: sampleSessions,
    sessionsLoaded: true,
    activeDomainId: 'alpha',
    setActiveDomainId,
    refreshCatalog,
    refreshSessions,
  };
});

describe('Sidebar domain menu', () => {
  it('shows a skeleton until catalog and sessions are ready', () => {
    mockActiveDomain.sessionsLoaded = false;
    const { container } = renderSidebar();
    expect(container.querySelector('.sidebar__skeleton')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'alpha' })).not.toBeInTheDocument();
  });

  it('renders cached domains and sessions without refetching on mount', async () => {
    renderSidebar();

    expect(await screen.findByRole('button', { name: 'alpha' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Alpha practice/ })).toBeInTheDocument();
    expect(refreshSessions).not.toHaveBeenCalled();
  });

  it('keeps cached content when remounted', async () => {
    const { unmount } = renderSidebar();
    expect(await screen.findByRole('button', { name: 'alpha' })).toBeInTheDocument();
    unmount();

    renderSidebar();
    expect(screen.getByRole('button', { name: 'alpha' })).toBeInTheDocument();
    expect(document.querySelector('.sidebar__skeleton')).not.toBeInTheDocument();
    expect(refreshSessions).not.toHaveBeenCalled();
  });

  it('exposes rename and delete actions from the domain kebab menu', async () => {
    renderSidebar();

    await screen.findByRole('button', { name: 'alpha' });
    await userEvent.click(screen.getByRole('button', { name: 'Domain actions for alpha' }));

    expect(screen.getByRole('menuitem', { name: 'Rename domain' })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'Delete domain' })).toBeInTheDocument();
  });

  it('renames a domain and selects the new id after refresh', async () => {
    renameDomain.mockResolvedValue({
      domain_id: 'alpha-renamed',
      path: '/tmp/alpha-renamed',
      sessions_updated: 1,
    });
    renderSidebar();

    await screen.findByRole('button', { name: 'alpha' });
    await userEvent.click(screen.getByRole('button', { name: 'Domain actions for alpha' }));
    await userEvent.click(screen.getByRole('menuitem', { name: 'Rename domain' }));

    const input = screen.getByRole('textbox', { name: 'Rename domain alpha' });
    await userEvent.clear(input);
    await userEvent.type(input, 'alpha-renamed');
    await userEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(renameDomain).toHaveBeenCalledWith('alpha', 'alpha-renamed');
    });
    expect(refreshCatalog).toHaveBeenCalled();
    expect(setActiveDomainId).toHaveBeenCalledWith('alpha-renamed');
    expect(refreshSessions).toHaveBeenCalledTimes(1);
  });

  it('surfaces rename errors without clearing the form', async () => {
    renameDomain.mockRejectedValue(new Error('A domain with this name already exists.'));
    renderSidebar();

    await screen.findByRole('button', { name: 'alpha' });
    await userEvent.click(screen.getByRole('button', { name: 'Domain actions for alpha' }));
    await userEvent.click(screen.getByRole('menuitem', { name: 'Rename domain' }));

    const input = screen.getByRole('textbox', { name: 'Rename domain alpha' });
    await userEvent.clear(input);
    await userEvent.type(input, 'beta');
    await userEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByText('A domain with this name already exists.')).toBeInTheDocument();
    expect(setActiveDomainId).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Save' })).toBeInTheDocument();
  });

  it('warns about cascading deletion and can cancel', async () => {
    renderSidebar();

    await screen.findByRole('button', { name: 'alpha' });
    await userEvent.click(screen.getByRole('button', { name: 'Domain actions for alpha' }));
    await userEvent.click(screen.getByRole('menuitem', { name: 'Delete domain' }));

    expect(screen.getByRole('dialog', { name: 'Delete domain?' })).toBeInTheDocument();
    expect(screen.getByText(/chapters/i)).toBeInTheDocument();
    expect(screen.getByText(/compiled wiki/i)).toBeInTheDocument();
    expect(screen.getByText(/sessions/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('dialog', { name: 'Delete domain?' })).not.toBeInTheDocument();
    expect(deleteDomain).not.toHaveBeenCalled();
  });

  it('deletes a domain and refreshes catalog plus sessions', async () => {
    deleteDomain.mockResolvedValue({
      domain_id: 'beta',
      deleted: true,
      sessions_deleted: 1,
    });
    renderSidebar();

    await screen.findByRole('button', { name: 'beta' });
    await userEvent.click(screen.getByRole('button', { name: 'Domain actions for beta' }));
    await userEvent.click(screen.getByRole('menuitem', { name: 'Delete domain' }));
    await userEvent.click(screen.getByRole('button', { name: 'Delete domain' }));

    await waitFor(() => {
      expect(deleteDomain).toHaveBeenCalledWith('beta');
    });
    expect(refreshCatalog).toHaveBeenCalled();
    expect(refreshSessions).toHaveBeenCalledTimes(1);
  });
});
