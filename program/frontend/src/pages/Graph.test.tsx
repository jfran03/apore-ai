import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { DomainGraph, KnowledgeCatalog, KnowledgeChapter } from '../api/types';

const getKnowledgeCatalog = vi.fn();
const listSessions = vi.fn();
const getProviderConfig = vi.fn();
const getDomainGraph = vi.fn();
const getWikiPreview = vi.fn();

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client');
  return {
    ...actual,
    getKnowledgeCatalog: () => getKnowledgeCatalog(),
    listSessions: () => listSessions(),
    getProviderConfig: () => getProviderConfig(),
    getDomainGraph: (domainId: string) => getDomainGraph(domainId),
    getWikiPreview: (source: 'staging' | 'published', knowledgeSource?: string) =>
      getWikiPreview(source, knowledgeSource),
  };
});

vi.mock('../assets/logo-no-bg.png', () => ({ default: 'logo-mock.png' }));

/** React Flow needs a real DOM layout; stub it and render nodeTypes in-place. */
vi.mock('@xyflow/react', () => {
  return {
    ReactFlow: ({
      nodes,
      onNodeClick,
      onPaneClick,
      children,
      nodeTypes,
    }: {
      nodes: Array<{
        id: string;
        type?: string;
        selected?: boolean;
        data: Record<string, unknown>;
      }>;
      onNodeClick?: (event: unknown, node: unknown) => void;
      onPaneClick?: () => void;
      children?: React.ReactNode;
      nodeTypes?: Record<
        string,
        React.ComponentType<{
          id: string;
          type?: string;
          data: Record<string, unknown>;
          selected?: boolean;
        }>
      >;
    }) => (
      <div data-testid="graph-canvas-stub" onClick={() => onPaneClick?.()}>
        {nodes.map((node) => {
          const NodeComp = node.type ? nodeTypes?.[node.type] : undefined;
          return (
            <div
              key={node.id}
              data-testid={`node-${node.id}`}
              role="button"
              tabIndex={0}
              onClick={(e) => {
                e.stopPropagation();
                onNodeClick?.(e, node);
              }}
            >
              {NodeComp ? (
                <NodeComp
                  id={node.id}
                  type={node.type}
                  data={node.data}
                  selected={Boolean(node.selected)}
                />
              ) : (
                String(node.data.label ?? node.id)
              )}
            </div>
          );
        })}
        {children}
      </div>
    ),
    Background: () => null,
    BackgroundVariant: { Dots: 'dots' },
    Controls: () => null,
    Handle: () => null,
    Position: { Top: 'top', Bottom: 'bottom', Left: 'left', Right: 'right' },
    MarkerType: { ArrowClosed: 'arrowclosed' },
    useReactFlow: () => ({
      getViewport: () => ({ x: 0, y: 0, zoom: 1 }),
      setViewport: () => undefined,
      setCenter: () => undefined,
      getNode: () => undefined,
    }),
  };
});

import { ActiveDomainProvider } from '../shell/ActiveDomainContext';
import { AppShell } from '../shell/AppShell';
import { Graph } from './Graph';

function chapter(id: string, domainId: string): KnowledgeChapter {
  return {
    id,
    knowledge_source: `domain:${domainId}/${id}`,
    sources_present: true,
    source_count: 1,
    source_files: ['notes.md'],
    has_concept_graph: true,
    wiki_count: 2,
    has_question_bank: false,
    question_bank_count: 0,
    compile_stage: 'ready',
    is_approved: true,
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
        chapters: [chapter('01-set-theory', 'discrete-math')],
      },
    ],
  };
}

function domainGraphFixture(): DomainGraph {
  return {
    domain_id: 'discrete-math',
    chapters: [
      {
        id: '01-set-theory',
        knowledge_source: 'domain:discrete-math/01-set-theory',
        has_concept_graph: true,
        mastery_pct: 40,
        concepts_proficient: 1,
        concepts_total: 2,
        concepts: [
          {
            id: 'sets_definition',
            label: 'Definition of a Set',
            depth: 0,
            p_mastery: 0.8,
            band: 'proficient',
            n_observed: 3,
            display_pct: 80,
            has_wiki: true,
          },
          {
            id: 'set_theory_intro',
            label: 'Introduction to Set Theory',
            depth: 1,
            p_mastery: null,
            band: 'new',
            n_observed: 0,
            display_pct: null,
            has_wiki: false,
          },
        ],
        edges: [
          {
            source: 'sets_definition',
            target: 'set_theory_intro',
            relation: 'prerequisite_of',
          },
        ],
      },
    ],
  };
}

function renderGraph() {
  localStorage.setItem('apore.knowledge_source', 'domain:discrete-math/01-set-theory');
  return render(
    <MemoryRouter initialEntries={['/graph']}>
      <ActiveDomainProvider>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/graph" element={<Graph />} />
          </Route>
        </Routes>
      </ActiveDomainProvider>
    </MemoryRouter>,
  );
}

async function drillIntoChapter() {
  await waitFor(() => {
    expect(screen.getByTestId('node-chapter:01-set-theory')).toBeInTheDocument();
  });
  await userEvent.click(screen.getByTestId('node-chapter:01-set-theory'));
  await waitFor(() => {
    expect(
      screen.getByTestId('node-concept:01-set-theory:sets_definition'),
    ).toBeInTheDocument();
  });
}

beforeEach(() => {
  getKnowledgeCatalog.mockReset().mockResolvedValue(catalogFixture());
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
  getDomainGraph.mockReset().mockResolvedValue(domainGraphFixture());
  getWikiPreview.mockReset().mockResolvedValue({
    source: 'published',
    version: 1,
    pages: [
      {
        concept_id: 'sets_definition',
        label: 'Definition of a Set',
        depth: 0,
        order: 0,
        body: 'A **set** is a collection of distinct objects.',
      },
    ],
    edges: [],
  });
  localStorage.clear();
});

describe('Graph page', () => {
  it('renders domain and chapter overview without concepts', async () => {
    renderGraph();

    await waitFor(() => {
      expect(screen.getByTestId('node-domain')).toBeInTheDocument();
    });
    expect(getDomainGraph).toHaveBeenCalledWith('discrete-math');
    expect(screen.getByTestId('node-chapter:01-set-theory')).toBeInTheDocument();
    expect(
      screen.queryByTestId('node-concept:01-set-theory:sets_definition'),
    ).not.toBeInTheDocument();
    expect(screen.getByRole('navigation', { name: 'Graph navigation' })).toHaveTextContent(
      'discrete-math',
    );
  });

  it('drills into a chapter and shows only that chapter’s concepts', async () => {
    renderGraph();
    await drillIntoChapter();

    expect(screen.queryByTestId('node-domain')).not.toBeInTheDocument();
    expect(screen.queryByTestId('node-chapter:01-set-theory')).not.toBeInTheDocument();
    expect(
      screen.getByTestId('node-concept:01-set-theory:sets_definition'),
    ).toBeInTheDocument();
    expect(screen.getByText('Definition of a Set')).toBeInTheDocument();

    const nav = screen.getByRole('navigation', { name: 'Graph navigation' });
    expect(nav).toHaveTextContent('01-set-theory');
    expect(within(nav).getByRole('button', { name: 'Back' })).toBeInTheDocument();
  });

  it('returns to overview via Back', async () => {
    renderGraph();
    await drillIntoChapter();

    await userEvent.click(screen.getByRole('button', { name: 'Back' }));

    await waitFor(() => {
      expect(screen.getByTestId('node-domain')).toBeInTheDocument();
    });
    expect(screen.getByTestId('node-chapter:01-set-theory')).toBeInTheDocument();
    expect(
      screen.queryByTestId('node-concept:01-set-theory:sets_definition'),
    ).not.toBeInTheDocument();
  });

  it('shows an empty state when the domain has no chapters', async () => {
    getDomainGraph.mockResolvedValue({
      domain_id: 'discrete-math',
      chapters: [],
    });
    renderGraph();

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Nothing to map yet' })).toBeInTheDocument();
    });
  });

  it('shows chapter empty state when the chapter has no concepts', async () => {
    getDomainGraph.mockResolvedValue({
      domain_id: 'discrete-math',
      chapters: [
        {
          id: '01-set-theory',
          knowledge_source: 'domain:discrete-math/01-set-theory',
          has_concept_graph: false,
          mastery_pct: 0,
          concepts_proficient: 0,
          concepts_total: 0,
          concepts: [],
          edges: [],
        },
      ],
    });
    renderGraph();

    await waitFor(() => {
      expect(screen.getByTestId('node-chapter:01-set-theory')).toBeInTheDocument();
    });
    await userEvent.click(screen.getByTestId('node-chapter:01-set-theory'));

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: 'No concepts in this chapter' }),
      ).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: 'Back' })).toBeInTheDocument();
  });

  it('shows an error state when the graph endpoint fails', async () => {
    getDomainGraph.mockRejectedValue(new Error('Domain not found'));
    renderGraph();

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Could not load graph' })).toBeInTheDocument();
    });
    expect(screen.getByText('Domain not found')).toBeInTheDocument();
  });

  it('expands a concept node in place with wiki markdown', async () => {
    renderGraph();
    await drillIntoChapter();

    await userEvent.click(
      screen.getByTestId('node-concept:01-set-theory:sets_definition'),
    );

    const conceptNode = screen.getByTestId(
      'node-concept:01-set-theory:sets_definition',
    );
    await waitFor(() => {
      expect(
        within(conceptNode).getByText(/collection of distinct objects/i),
      ).toBeInTheDocument();
    });

    expect(conceptNode.querySelector('.graph-node--expanded')).not.toBeNull();
    expect(within(conceptNode).getByText('80%')).toBeInTheDocument();
    expect(within(conceptNode).getByText('Proficient')).toBeInTheDocument();
    expect(getWikiPreview).toHaveBeenCalledWith(
      'published',
      'domain:discrete-math/01-set-theory',
    );
  });

  it('collapses the expanded concept on Escape', async () => {
    renderGraph();
    await drillIntoChapter();

    await userEvent.click(
      screen.getByTestId('node-concept:01-set-theory:sets_definition'),
    );
    await waitFor(() => {
      expect(
        screen.getByTestId('node-concept:01-set-theory:sets_definition').querySelector(
          '.graph-node--expanded',
        ),
      ).not.toBeNull();
    });

    await userEvent.keyboard('{Escape}');
    await waitFor(() => {
      expect(
        screen.getByTestId('node-concept:01-set-theory:sets_definition').querySelector(
          '.graph-node--expanded',
        ),
      ).toBeNull();
    });
  });

  it('shows a missing-wiki message for concepts without published pages', async () => {
    renderGraph();
    await drillIntoChapter();

    await userEvent.click(
      screen.getByTestId('node-concept:01-set-theory:set_theory_intro'),
    );

    const conceptNode = screen.getByTestId(
      'node-concept:01-set-theory:set_theory_intro',
    );
    await waitFor(() => {
      expect(
        within(conceptNode).getByText(/No compiled wiki for this concept yet/i),
      ).toBeInTheDocument();
    });
    expect(getWikiPreview).not.toHaveBeenCalled();
  });
});
