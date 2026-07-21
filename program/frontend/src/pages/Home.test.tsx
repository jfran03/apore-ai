import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { KnowledgeCatalog, KnowledgeChapter } from '../api/types';

const getKnowledgeCatalog = vi.fn();
const listSessions = vi.fn();
const getProviderConfig = vi.fn();

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client');
  return {
    ...actual,
    getKnowledgeCatalog: () => getKnowledgeCatalog(),
    listSessions: () => listSessions(),
    getProviderConfig: () => getProviderConfig(),
  };
});

vi.mock('../assets/logo-no-bg.png', () => ({ default: 'logo-mock.png' }));

import {
  getStoredKnowledgeSource,
  isOnboardingComplete,
  setOnboardingComplete,
} from '../api/client';
import { ActiveDomainProvider } from '../shell/ActiveDomainContext';
import { AppShell } from '../shell/AppShell';
import { Home } from './Home';

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
      {
        id: 'discrete-math',
        chapters: [
          chapter('01-set-theory', 'discrete-math'),
          chapter('02-logic-and-proof', 'discrete-math'),
        ],
      },
      {
        id: 'beta',
        chapters: [chapter('b1', 'beta')],
      },
    ],
  };
}

function renderHome(initialPath = '/') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <ActiveDomainProvider>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/" element={<Home />} />
            <Route path="/study" element={<div>Study page</div>} />
          </Route>
        </Routes>
      </ActiveDomainProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  getKnowledgeCatalog.mockReset();
  listSessions.mockReset().mockResolvedValue({ sessions: [] });
  getProviderConfig.mockReset().mockResolvedValue({
    anthropic_api_key_set: true,
    anthropic_api_key_hint: 'sk-…',
    nim_api_key_set: false,
    nim_api_key_hint: null,
    model: 'claude-sonnet-4-20250514',
    active_provider: 'anthropic',
    active_model: 'claude-sonnet-4-20250514',
  });
  localStorage.clear();
});

describe('Home chapter chooser', () => {
  it('renders the welcome hero and domain chapters on first visit', async () => {
    getKnowledgeCatalog.mockResolvedValue(catalogFixture());
    renderHome();

    expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'discrete-math' })).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: 'chapter 1' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'chapter 2' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'b1' })).toBeInTheDocument();
  });

  it('shows a loading status while the catalog loads', () => {
    getKnowledgeCatalog.mockReturnValue(new Promise(() => {}));
    renderHome();
    expect(screen.getByRole('status')).toHaveTextContent('Loading domains');
  });

  it('shows a catalog error', async () => {
    getKnowledgeCatalog.mockRejectedValue(new Error('Catalog offline'));
    renderHome();
    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Catalog offline');
    });
  });

  it('shows an empty state when there are no domains', async () => {
    getKnowledgeCatalog.mockResolvedValue({ fixtures: [], domains: [] });
    renderHome();
    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent('No domains yet');
    });
  });

  it('selecting a chapter persists selection, completes onboarding, and opens study', async () => {
    getKnowledgeCatalog.mockResolvedValue(catalogFixture());
    renderHome();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'chapter 2' })).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole('button', { name: 'chapter 2' }));

    expect(getStoredKnowledgeSource()).toBe('domain:discrete-math/02-logic-and-proof');
    expect(isOnboardingComplete()).toBe(true);
    expect(screen.getByText('Study page')).toBeInTheDocument();
  });

  it('redirects completed users from / to /study', async () => {
    setOnboardingComplete();
    getKnowledgeCatalog.mockResolvedValue(catalogFixture());
    renderHome();

    await waitFor(() => {
      expect(screen.getByText('Study page')).toBeInTheDocument();
    });
    expect(screen.queryByRole('heading', { name: 'Welcome back' })).not.toBeInTheDocument();
  });

  it('hides left and center nav on the landing route, keeping settings', async () => {
    getKnowledgeCatalog.mockResolvedValue(catalogFixture());
    renderHome();

    expect(screen.queryByLabelText(/navigation/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: 'Main navigation' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Settings' })).toBeInTheDocument();
  });
});
