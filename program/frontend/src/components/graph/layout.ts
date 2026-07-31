import { MarkerType, type Edge, type Node } from '@xyflow/react';
import type { DomainGraph, GraphChapter, MasteryBand } from '../../api/types';

// A mid-neutral that reads on both light and dark canvases. SVG markers are
// drawn with an inline fill and cannot resolve theme CSS variables, so we pin a
// value close to --color-muted in both themes.
const EDGE_MARKER = { type: MarkerType.ArrowClosed, color: '#8f8b7e', width: 16, height: 16 };

export interface DomainNodeData extends Record<string, unknown> {
  label: string;
}

export interface ChapterNodeData extends Record<string, unknown> {
  chapterId: string;
  knowledgeSource: string;
  label: string;
  masteryPct: number;
  conceptsProficient: number;
  conceptsTotal: number;
  hasConceptGraph: boolean;
}

export interface ConceptNodeData extends Record<string, unknown> {
  conceptId: string;
  chapterId: string;
  knowledgeSource: string;
  label: string;
  band: MasteryBand;
  displayPct: number | null;
  nObserved: number;
  hasWiki: boolean;
  onClose?: () => void;
}

export type DomainFlowNode = Node<DomainNodeData, 'domain'>;
export type ChapterFlowNode = Node<ChapterNodeData, 'chapter'>;
export type ConceptFlowNode = Node<ConceptNodeData, 'concept'>;
export type GraphFlowNode = DomainFlowNode | ChapterFlowNode | ConceptFlowNode;

export const CONCEPT_NODE_SIZE = {
  collapsed: { width: 196, height: 60 },
  expanded: { width: 380, height: 360 },
} as const;

/** Spacing for overview + chapter-focus layouts and expand push. */
export const GRAPH_LAYOUT = {
  overviewRankGap: 120,
  overviewChapterGap: 48,
  /** Horizontal step between consecutive concepts on the wave. */
  chapterStepX: 220,
  chapterWaveAmplitude: 120,
  /** Radians per concept index along the sine wave (quarter period). */
  chapterWavePhase: Math.PI / 2,
  expandPadding: 28,
  expandIterations: 6,
} as const;

const NODE_SIZE = {
  domain: { width: 200, height: 64 },
  chapter: { width: 216, height: 92 },
  concept: CONCEPT_NODE_SIZE.collapsed,
} as const;

const DOMAIN_ID = 'domain';

export function chapterNodeId(chapterId: string): string {
  return `chapter:${chapterId}`;
}

export function conceptNodeId(chapterId: string, conceptId: string): string {
  return `concept:${chapterId}:${conceptId}`;
}

function centerTopLeft(
  cx: number,
  cy: number,
  size: { width: number; height: number },
): { x: number; y: number } {
  return { x: cx - size.width / 2, y: cy - size.height / 2 };
}

function nodeSize(node: GraphFlowNode): { width: number; height: number } {
  return {
    width: node.width ?? NODE_SIZE[node.type].width,
    height: node.height ?? NODE_SIZE[node.type].height,
  };
}

function nodeCenter(node: GraphFlowNode): { x: number; y: number } {
  const size = nodeSize(node);
  return {
    x: node.position.x + size.width / 2,
    y: node.position.y + size.height / 2,
  };
}

type Aabb = { left: number; top: number; right: number; bottom: number };

function nodeAabb(node: GraphFlowNode, padding = 0): Aabb {
  const size = nodeSize(node);
  return {
    left: node.position.x - padding,
    top: node.position.y - padding,
    right: node.position.x + size.width + padding,
    bottom: node.position.y + size.height + padding,
  };
}

function aabbsOverlap(a: Aabb, b: Aabb): boolean {
  return a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
}

/**
 * Push neighbors away from an expanded node so AABBs no longer overlap.
 * The expanded node stays fixed; others move along the vector from expanded
 * center to neighbor center.
 */
export function applyExpandSeparation(
  nodes: GraphFlowNode[],
  expandedId: string,
  expandedSize: { width: number; height: number },
  padding: number = GRAPH_LAYOUT.expandPadding,
  iterations: number = GRAPH_LAYOUT.expandIterations,
): GraphFlowNode[] {
  const next = nodes.map((n) => {
    if (n.id !== expandedId) return { ...n };
    return {
      ...n,
      width: expandedSize.width,
      height: expandedSize.height,
    };
  }) as GraphFlowNode[];

  const expanded = next.find((n) => n.id === expandedId);
  if (!expanded) return next;

  for (let iter = 0; iter < iterations; iter++) {
    const expBox = nodeAabb(expanded, padding);
    const expCenter = nodeCenter(expanded);

    for (const node of next) {
      if (node.id === expandedId) continue;
      const box = nodeAabb(node);
      if (!aabbsOverlap(expBox, box)) continue;

      const center = nodeCenter(node);
      let dx = center.x - expCenter.x;
      let dy = center.y - expCenter.y;
      const len = Math.hypot(dx, dy);
      if (len < 1e-6) {
        dx = 1;
        dy = 0;
      } else {
        dx /= len;
        dy /= len;
      }

      const overlapX =
        Math.min(expBox.right, box.right) - Math.max(expBox.left, box.left);
      const overlapY =
        Math.min(expBox.bottom, box.bottom) - Math.max(expBox.top, box.top);
      const push = Math.max(overlapX, overlapY) + 1;

      node.position = {
        x: node.position.x + dx * push,
        y: node.position.y + dy * push,
      };
    }
  }

  return next;
}

export interface LayoutResult {
  nodes: GraphFlowNode[];
  edges: Edge[];
}

/**
 * Domain overview: domain + chapter nodes only (no concepts).
 * Domain on top; chapters in a horizontal row below.
 */
export function layoutDomainOverview(graph: DomainGraph): LayoutResult {
  const domainSize = NODE_SIZE.domain;
  const chapterSize = NODE_SIZE.chapter;
  const chapters = graph.chapters;

  const nodes: GraphFlowNode[] = [
    {
      id: DOMAIN_ID,
      type: 'domain',
      position: centerTopLeft(0, 0, domainSize),
      width: domainSize.width,
      height: domainSize.height,
      data: { label: graph.domain_id },
    },
  ];

  const edges: Edge[] = [];
  const n = chapters.length;
  const rowWidth =
    n === 0
      ? 0
      : n * chapterSize.width + Math.max(0, n - 1) * GRAPH_LAYOUT.overviewChapterGap;
  const startX = -rowWidth / 2;
  const chapterY = domainSize.height / 2 + GRAPH_LAYOUT.overviewRankGap;

  chapters.forEach((chapter, i) => {
    const id = chapterNodeId(chapter.id);
    const cx =
      startX +
      i * (chapterSize.width + GRAPH_LAYOUT.overviewChapterGap) +
      chapterSize.width / 2;
    nodes.push({
      id,
      type: 'chapter',
      position: centerTopLeft(cx, chapterY, chapterSize),
      width: chapterSize.width,
      height: chapterSize.height,
      data: {
        chapterId: chapter.id,
        knowledgeSource: chapter.knowledge_source,
        label: chapter.id,
        masteryPct: chapter.mastery_pct,
        conceptsProficient: chapter.concepts_proficient,
        conceptsTotal: chapter.concepts_total,
        hasConceptGraph: chapter.has_concept_graph,
      },
    });
    edges.push({
      id: `e:${DOMAIN_ID}-${id}`,
      source: DOMAIN_ID,
      target: id,
      type: 'default',
      className: 'graph-edge graph-edge--structural',
    });
  });

  return { nodes, edges };
}

/**
 * Chapter focus: concepts + prerequisite edges only for one chapter.
 * Concepts ordered by depth then id, placed along a spaced sine wave
 * left-to-right with cubic bezier edges.
 */
export function layoutChapterConcepts(chapter: GraphChapter): LayoutResult {
  const conceptSize = NODE_SIZE.concept;
  const ordered = [...chapter.concepts].sort((a, b) => {
    const depthCmp = (a.depth ?? 0) - (b.depth ?? 0);
    if (depthCmp !== 0) return depthCmp;
    return a.id.localeCompare(b.id);
  });

  const nodes: ConceptFlowNode[] = ordered.map((concept, i) => {
    const cx = i * (conceptSize.width + GRAPH_LAYOUT.chapterStepX);
    const cy =
      GRAPH_LAYOUT.chapterWaveAmplitude *
      Math.sin(i * GRAPH_LAYOUT.chapterWavePhase);
    return {
      id: conceptNodeId(chapter.id, concept.id),
      type: 'concept',
      position: centerTopLeft(cx, cy, conceptSize),
      width: conceptSize.width,
      height: conceptSize.height,
      data: {
        conceptId: concept.id,
        chapterId: chapter.id,
        knowledgeSource: chapter.knowledge_source,
        label: concept.label,
        band: concept.band,
        displayPct: concept.display_pct,
        nObserved: concept.n_observed,
        hasWiki: concept.has_wiki,
      },
    };
  });

  const edges: Edge[] = chapter.edges.map((edge) => ({
    id: `e:${chapter.id}:${edge.source}-${edge.target}`,
    source: conceptNodeId(chapter.id, edge.source),
    target: conceptNodeId(chapter.id, edge.target),
    type: 'default',
    className: 'graph-edge graph-edge--prereq',
    markerEnd: EDGE_MARKER,
  }));

  return { nodes, edges };
}
