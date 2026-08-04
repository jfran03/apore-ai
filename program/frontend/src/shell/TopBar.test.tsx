import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { render, screen } from '@testing-library/react';
import type { KnowledgeCatalog, KnowledgeChapter, KnowledgeDomain } from '../api/types';

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client');
  return {
    ...actual,
    getProviderConfig: vi.fn().mockResolvedValue({
      anthropic_api_key_set: true,
      anthropic_api_key_hint: 'sk-…',
      nim_api_key_set: false,
      nim_api_key_hint: null,
      model: 'claude-sonnet-4-20250514',
      active_provider: 'anthropic',
      active_model: 'claude-sonnet-4-20250514',
    }),
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

vi.mock('./StudyFocusContext', () => ({
  useStudyFocus: () => ({ focused: false, focusMode: null, onExitRequest: null }),
}));

vi.mock('../assets/logo-no-bg.png', () => ({ default: 'logo-mock.png' }));

import { TopBar } from './TopBar';

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

let mockActiveDomain: {
  catalog: KnowledgeCatalog;
  activeDomain: KnowledgeDomain;
  activeDomainId: string;
};

beforeEach(() => {
  mockActiveDomain = {
    catalog: {
      fixtures: [],
      domains: [domain('discrete-math', [chapter('01-set-theory', 'discrete-math')])],
    },
    activeDomain: domain('discrete-math', [chapter('01-set-theory', 'discrete-math')]),
    activeDomainId: 'discrete-math',
  };
});

describe('TopBar domain label', () => {
  it('links the active domain label to /graph on Study', () => {
    render(
      <MemoryRouter initialEntries={['/study']}>
        <Routes>
          <Route path="*" element={<TopBar />} />
        </Routes>
      </MemoryRouter>,
    );

    const domainLink = screen.getByRole('link', {
      name: 'Open graph for discrete-math',
    });
    expect(domainLink).toHaveAttribute('href', '/graph');
    expect(domainLink).toHaveTextContent('discrete-math');
  });

  it('shows the active domain label on Setup', () => {
    render(
      <MemoryRouter initialEntries={['/setup']}>
        <Routes>
          <Route path="*" element={<TopBar />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(
      screen.getByRole('link', { name: 'Open graph for discrete-math' }),
    ).toBeInTheDocument();
  });

  it('hides the active domain label on Graph', () => {
    render(
      <MemoryRouter initialEntries={['/graph']}>
        <Routes>
          <Route path="*" element={<TopBar />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(
      screen.queryByRole('link', { name: 'Open graph for discrete-math' }),
    ).not.toBeInTheDocument();
  });
});
