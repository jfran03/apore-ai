import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Background,
  BackgroundVariant,
  Controls,
  ReactFlow,
  useReactFlow,
  type NodeMouseHandler,
  type NodeTypes,
  type Viewport,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { getDomainGraph } from '../api/client';
import type { DomainGraph, GraphChapter } from '../api/types';
import { useActiveDomain } from '../shell/ActiveDomainContext';
import { ChapterNode } from '../components/graph/ChapterNode';
import { ConceptNode } from '../components/graph/ConceptNode';
import { DomainNode } from '../components/graph/DomainNode';
import {
  CONCEPT_NODE_SIZE,
  GRAPH_LAYOUT,
  applyExpandSeparation,
  layoutChapterConcepts,
  layoutDomainOverview,
  type ChapterNodeData,
  type ConceptNodeData,
  type GraphFlowNode,
} from '../components/graph/layout';
import '../styles/graph.css';

const nodeTypes: NodeTypes = {
  domain: DomainNode,
  chapter: ChapterNode,
  concept: ConceptNode,
};

const FOCUS_DURATION_MS = 400;
const FOCUS_ZOOM = 1;

type LoadState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'ready'; graph: DomainGraph }
  | { status: 'error'; message: string };

type Focus = { chapterId: string } | null;

/** Tween camera to an expanded concept; restore prior viewport on deselect. */
function ConceptFocusCamera({
  selectedNodeId,
  nodes,
}: {
  selectedNodeId: string | null;
  nodes: GraphFlowNode[];
}) {
  const { getViewport, setViewport, setCenter } = useReactFlow();
  const savedViewport = useRef<Viewport | null>(null);
  const selected = selectedNodeId
    ? nodes.find((n) => n.id === selectedNodeId)
    : undefined;

  useEffect(() => {
    if (selectedNodeId && selected) {
      if (!savedViewport.current) {
        savedViewport.current = getViewport();
      }
      const w = selected.width ?? CONCEPT_NODE_SIZE.expanded.width;
      const h = selected.height ?? CONCEPT_NODE_SIZE.expanded.height;
      const cx = selected.position.x + w / 2;
      const cy = selected.position.y + h / 2;
      setCenter(cx, cy, { zoom: FOCUS_ZOOM, duration: FOCUS_DURATION_MS });
      return;
    }

    if (!selectedNodeId && savedViewport.current) {
      setViewport(savedViewport.current, { duration: FOCUS_DURATION_MS });
      savedViewport.current = null;
    }
  }, [
    selectedNodeId,
    selected,
    selected?.position.x,
    selected?.position.y,
    selected?.width,
    selected?.height,
    getViewport,
    setViewport,
    setCenter,
  ]);

  return null;
}

export function Graph() {
  const { activeDomainId, catalogLoading } = useActiveDomain();
  const [load, setLoad] = useState<LoadState>({ status: 'idle' });
  const [focus, setFocus] = useState<Focus>(null);
  const [selected, setSelected] = useState<ConceptNodeData | null>(null);

  const clearSelection = useCallback(() => setSelected(null), []);

  const goOverview = useCallback(() => {
    setFocus(null);
    setSelected(null);
  }, []);

  useEffect(() => {
    if (!activeDomainId) {
      setLoad({ status: 'idle' });
      return;
    }
    let active = true;
    setLoad({ status: 'loading' });
    setFocus(null);
    setSelected(null);
    getDomainGraph(activeDomainId)
      .then((graph) => {
        if (active) setLoad({ status: 'ready', graph });
      })
      .catch((err: unknown) => {
        if (active)
          setLoad({
            status: 'error',
            message: err instanceof Error ? err.message : 'Failed to load graph',
          });
      });
    return () => {
      active = false;
    };
  }, [activeDomainId]);

  const focusedChapter: GraphChapter | null = useMemo(() => {
    if (load.status !== 'ready' || !focus) return null;
    return load.graph.chapters.find((c) => c.id === focus.chapterId) ?? null;
  }, [load, focus]);

  const layout = useMemo(() => {
    if (load.status !== 'ready') return null;
    if (focus) {
      const chapter = load.graph.chapters.find((c) => c.id === focus.chapterId);
      if (!chapter) return null;
      return layoutChapterConcepts(chapter);
    }
    return layoutDomainOverview(load.graph);
  }, [load, focus]);

  const hasChapters = useMemo(
    () => load.status === 'ready' && load.graph.chapters.length > 0,
    [load],
  );

  const onNodeClick = useCallback<NodeMouseHandler>((_event, node) => {
    if (node.type === 'chapter') {
      const data = (node as GraphFlowNode).data as ChapterNodeData;
      setFocus({ chapterId: data.chapterId });
      setSelected(null);
      return;
    }
    if (node.type === 'concept') {
      setSelected((node as GraphFlowNode).data as ConceptNodeData);
      return;
    }
    setSelected(null);
  }, []);

  const selectedNodeId = selected
    ? `concept:${selected.chapterId}:${selected.conceptId}`
    : null;

  const nodes = useMemo(() => {
    if (!layout) return [];
    if (!selectedNodeId || !focus) return layout.nodes;

    const sized = layout.nodes.map((n) => {
      if (n.id !== selectedNodeId || n.type !== 'concept') return n;
      return {
        ...n,
        selected: true,
        width: CONCEPT_NODE_SIZE.expanded.width,
        height: CONCEPT_NODE_SIZE.expanded.height,
        measured: {
          width: CONCEPT_NODE_SIZE.expanded.width,
          height: CONCEPT_NODE_SIZE.expanded.height,
        },
        style: {
          ...n.style,
          width: CONCEPT_NODE_SIZE.expanded.width,
          height: CONCEPT_NODE_SIZE.expanded.height,
          zIndex: 10,
        },
        data: {
          ...n.data,
          onClose: clearSelection,
        },
      };
    });

    return applyExpandSeparation(
      sized,
      selectedNodeId,
      CONCEPT_NODE_SIZE.expanded,
      GRAPH_LAYOUT.expandPadding,
    );
  }, [layout, selectedNodeId, clearSelection, focus]);

  if (!activeDomainId) {
    return (
      <GraphShell>
        <GraphEmpty
          title="No domain selected"
          note={
            catalogLoading
              ? 'Loading your knowledge base…'
              : 'Pick a domain from the sidebar to see its knowledge graph.'
          }
        />
      </GraphShell>
    );
  }

  if (load.status === 'loading' || load.status === 'idle') {
    return (
      <GraphShell>
        <GraphEmpty title="Loading graph" note={`Assembling ${activeDomainId}…`} />
      </GraphShell>
    );
  }

  if (load.status === 'error') {
    return (
      <GraphShell>
        <GraphEmpty title="Could not load graph" note={load.message} tone="error" />
      </GraphShell>
    );
  }

  if (!hasChapters) {
    return (
      <GraphShell>
        <GraphEmpty
          title="Nothing to map yet"
          note="This domain has no chapters yet. Add a chapter in Setup to build its graph."
        />
      </GraphShell>
    );
  }

  const domainLabel = load.graph.domain_id;
  const inChapterView = focus !== null;
  const chapterEmpty =
    inChapterView && focusedChapter !== null && focusedChapter.concepts.length === 0;

  return (
    <GraphShell>
      {inChapterView && (
        <nav className="graph-breadcrumb" aria-label="Graph navigation">
          <button type="button" className="graph-breadcrumb__link" onClick={goOverview}>
            {domainLabel}
          </button>
          <span className="graph-breadcrumb__sep" aria-hidden="true">
            /
          </span>
          <span className="graph-breadcrumb__current">{focus.chapterId}</span>
          <button type="button" className="graph-breadcrumb__back" onClick={goOverview}>
            Back
          </button>
        </nav>
      )}

      {chapterEmpty ? (
        <GraphEmpty
          title="No concepts in this chapter"
          note="Compile this chapter in Setup to generate its concept graph."
        />
      ) : (
        <div className="graph-canvas">
          <ReactFlow
            key={focus?.chapterId ?? 'overview'}
            nodes={nodes}
            edges={layout?.edges ?? []}
            nodeTypes={nodeTypes}
            onNodeClick={onNodeClick}
            onPaneClick={clearSelection}
            fitView
            fitViewOptions={{ padding: 0.2, maxZoom: 1 }}
            minZoom={0.2}
            maxZoom={1.5}
            proOptions={{ hideAttribution: true }}
            nodesDraggable={false}
            nodesConnectable={false}
            elementsSelectable
          >
            <Background variant={BackgroundVariant.Dots} gap={22} size={1} />
            <Controls showInteractive={false} />
            {focus ? (
              <ConceptFocusCamera selectedNodeId={selectedNodeId} nodes={nodes} />
            ) : null}
          </ReactFlow>
        </div>
      )}
    </GraphShell>
  );
}

function GraphShell({ children }: { children: React.ReactNode }) {
  return <div className="graph-page">{children}</div>;
}

function GraphEmpty({
  title,
  note,
  tone,
}: {
  title: string;
  note: string;
  tone?: 'error';
}) {
  return (
    <div className={`graph-empty${tone === 'error' ? ' graph-empty--error' : ''}`}>
      <h1 className="graph-empty__title">{title}</h1>
      <p className="graph-empty__note">{note}</p>
    </div>
  );
}
