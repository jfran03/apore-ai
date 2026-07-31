import { describe, it, expect } from 'vitest';
import type { DomainGraph, GraphChapter } from '../../api/types';
import {
  CONCEPT_NODE_SIZE,
  GRAPH_LAYOUT,
  applyExpandSeparation,
  chapterNodeId,
  conceptNodeId,
  layoutChapterConcepts,
  layoutDomainOverview,
  type GraphFlowNode,
} from './layout';

function sampleChapter(): GraphChapter {
  return {
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
        has_wiki: true,
      },
    ],
    edges: [
      {
        source: 'sets_definition',
        target: 'set_theory_intro',
        relation: 'prerequisite_of',
      },
    ],
  };
}

function sampleGraph(): DomainGraph {
  return {
    domain_id: 'discrete-math',
    chapters: [
      sampleChapter(),
      {
        id: '02-empty',
        knowledge_source: 'domain:discrete-math/02-empty',
        has_concept_graph: false,
        mastery_pct: 0,
        concepts_proficient: 0,
        concepts_total: 0,
        concepts: [],
        edges: [],
      },
    ],
  };
}

function aabb(node: GraphFlowNode, padding = 0) {
  const w = node.width ?? 0;
  const h = node.height ?? 0;
  return {
    left: node.position.x - padding,
    top: node.position.y - padding,
    right: node.position.x + w + padding,
    bottom: node.position.y + h + padding,
  };
}

function overlaps(
  a: ReturnType<typeof aabb>,
  b: ReturnType<typeof aabb>,
): boolean {
  return a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
}

describe('layoutDomainOverview', () => {
  it('builds only domain and chapter nodes', () => {
    const { nodes, edges } = layoutDomainOverview(sampleGraph());

    expect(nodes.every((n) => n.type === 'domain' || n.type === 'chapter')).toBe(
      true,
    );
    expect(nodes.some((n) => n.id.startsWith('concept:'))).toBe(false);
    expect(nodes.find((n) => n.id === 'domain')?.type).toBe('domain');
    expect(nodes.find((n) => n.id === chapterNodeId('01-set-theory'))?.type).toBe(
      'chapter',
    );
    expect(nodes.find((n) => n.id === chapterNodeId('02-empty'))?.type).toBe(
      'chapter',
    );

    const domain = nodes.find((n) => n.id === 'domain')!;
    const chapter = nodes.find((n) => n.id === chapterNodeId('01-set-theory'))!;
    expect(domain.position.y).toBeLessThan(chapter.position.y);

    expect(edges.every((e) => e.source === 'domain')).toBe(true);
    expect(edges.every((e) => e.type === 'default')).toBe(true);
  });
});

describe('layoutChapterConcepts', () => {
  it('builds only concepts for that chapter along a left-to-right sine wave', () => {
    const chapter = sampleChapter();
    const { nodes, edges } = layoutChapterConcepts(chapter);

    expect(nodes.every((n) => n.type === 'concept')).toBe(true);
    expect(nodes).toHaveLength(2);
    expect(
      nodes.find((n) => n.id === conceptNodeId('01-set-theory', 'sets_definition')),
    ).toBeTruthy();

    const depth0 = nodes.find(
      (n) => n.id === conceptNodeId('01-set-theory', 'sets_definition'),
    )!;
    const depth1 = nodes.find(
      (n) => n.id === conceptNodeId('01-set-theory', 'set_theory_intro'),
    )!;
    expect(depth0.position.x).toBeLessThan(depth1.position.x);

    expect(edges).toHaveLength(1);
    expect(edges[0].type).toBe('default');
    expect(edges[0].markerEnd).toBeTruthy();
    expect(edges[0].source).toBe(
      conceptNodeId('01-set-theory', 'sets_definition'),
    );
  });

  it('places concepts on a consistent quarter-period sine wave', () => {
    const chapter: GraphChapter = {
      id: 'ch-wave',
      knowledge_source: 'domain:d/ch-wave',
      has_concept_graph: true,
      mastery_pct: 0,
      concepts_proficient: 0,
      concepts_total: 6,
      concepts: Array.from({ length: 6 }, (_, i) => ({
        id: `c${i}`,
        label: `C${i}`,
        depth: 0,
        p_mastery: null,
        band: 'new' as const,
        n_observed: 0,
        display_pct: null,
        has_wiki: false,
      })),
      edges: [],
    };

    const { nodes } = layoutChapterConcepts(chapter);
    const halfH = CONCEPT_NODE_SIZE.collapsed.height / 2;
    const A = GRAPH_LAYOUT.chapterWaveAmplitude;

    nodes.forEach((node, i) => {
      const cy = node.position.y + halfH;
      expect(cy).toBeCloseTo(A * Math.sin(i * (Math.PI / 2)));
    });
  });

  it('places sibling concepts at distinct positions', () => {
    const chapter: GraphChapter = {
      id: 'ch-a',
      knowledge_source: 'domain:d/ch-a',
      has_concept_graph: true,
      mastery_pct: 0,
      concepts_proficient: 0,
      concepts_total: 2,
      concepts: [
        {
          id: 'a',
          label: 'A',
          depth: 0,
          p_mastery: null,
          band: 'new',
          n_observed: 0,
          display_pct: null,
          has_wiki: false,
        },
        {
          id: 'b',
          label: 'B',
          depth: 0,
          p_mastery: null,
          band: 'new',
          n_observed: 0,
          display_pct: null,
          has_wiki: false,
        },
      ],
      edges: [],
    };

    const { nodes } = layoutChapterConcepts(chapter);
    const a = nodes.find((n) => n.id === conceptNodeId('ch-a', 'a'))!;
    const b = nodes.find((n) => n.id === conceptNodeId('ch-a', 'b'))!;
    expect(a.position.x !== b.position.x || a.position.y !== b.position.y).toBe(
      true,
    );
  });

  it('namespaces concept ids by chapter', () => {
    const chapter: GraphChapter = {
      id: 'ch-a',
      knowledge_source: 'domain:d/ch-a',
      has_concept_graph: true,
      mastery_pct: 0,
      concepts_proficient: 0,
      concepts_total: 1,
      concepts: [
        {
          id: 'shared',
          label: 'A',
          depth: 0,
          p_mastery: null,
          band: 'new',
          n_observed: 0,
          display_pct: null,
          has_wiki: false,
        },
      ],
      edges: [],
    };
    const { nodes } = layoutChapterConcepts(chapter);
    expect(nodes[0].id).toBe(conceptNodeId('ch-a', 'shared'));
  });
});

describe('applyExpandSeparation', () => {
  it('pushes an overlapping neighbor clear of the expanded AABB', () => {
    const expandedId = 'concept:ch:a';
    const nodes: GraphFlowNode[] = [
      {
        id: expandedId,
        type: 'concept',
        position: { x: 0, y: 0 },
        width: CONCEPT_NODE_SIZE.collapsed.width,
        height: CONCEPT_NODE_SIZE.collapsed.height,
        data: {
          conceptId: 'a',
          chapterId: 'ch',
          knowledgeSource: 'domain:d/ch',
          label: 'A',
          band: 'new',
          displayPct: null,
          nObserved: 0,
          hasWiki: true,
        },
      },
      {
        id: 'concept:ch:b',
        type: 'concept',
        position: { x: 40, y: 40 },
        width: CONCEPT_NODE_SIZE.collapsed.width,
        height: CONCEPT_NODE_SIZE.collapsed.height,
        data: {
          conceptId: 'b',
          chapterId: 'ch',
          knowledgeSource: 'domain:d/ch',
          label: 'B',
          band: 'new',
          displayPct: null,
          nObserved: 0,
          hasWiki: false,
        },
      },
    ];

    const result = applyExpandSeparation(
      nodes,
      expandedId,
      CONCEPT_NODE_SIZE.expanded,
      GRAPH_LAYOUT.expandPadding,
    );

    const expanded = result.find((n) => n.id === expandedId)!;
    const neighbor = result.find((n) => n.id === 'concept:ch:b')!;

    expect(expanded.position).toEqual({ x: 0, y: 0 });
    expect(expanded.width).toBe(CONCEPT_NODE_SIZE.expanded.width);
    expect(expanded.height).toBe(CONCEPT_NODE_SIZE.expanded.height);

    expect(
      overlaps(aabb(expanded, GRAPH_LAYOUT.expandPadding), aabb(neighbor)),
    ).toBe(false);
  });
});
