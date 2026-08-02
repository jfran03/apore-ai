import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
  type Dispatch,
} from 'react';
import Konva from 'konva';
import {
  Ellipse,
  Group,
  Layer,
  Line,
  Rect,
  Stage,
  Text,
  Transformer,
} from 'react-konva';
import type {
  FeedbackRegion,
  ScratchpadCamera,
  ScratchpadExportBounds,
  ScratchpadNode,
} from '../../api/types';
import {
  feedbackRegionToScene,
  nodeBounds,
  screenToScene,
  type Point,
  type ScratchpadAction,
  type ScratchpadHistory,
  type ScratchpadTool,
  type SceneRect,
} from './scratchpadModel';

export interface ScratchpadCanvasHandle {
  focus: () => void;
}

interface ScratchpadCanvasProps {
  history: ScratchpadHistory;
  dispatch: Dispatch<ScratchpadAction>;
  camera: ScratchpadCamera;
  onCameraChange: (camera: ScratchpadCamera) => void;
  tool: ScratchpadTool;
  feedbackRegions: FeedbackRegion[];
  exportBounds: ScratchpadExportBounds | null;
  disabled: boolean;
}

interface TextDraft {
  id?: string;
  x: number;
  y: number;
  value: string;
}

const MIN_SCALE = 0.2;
const MAX_SCALE = 4;
const STROKE_WIDTH = 3;

function cssColor(name: string, fallback: string): string {
  if (typeof document === 'undefined') return fallback;
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
}

function nextNodeId(): string {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `node-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function intersects(a: SceneRect, b: SceneRect): boolean {
  return !(
    a.x + a.width < b.x ||
    b.x + b.width < a.x ||
    a.y + a.height < b.y ||
    b.y + b.height < a.y
  );
}

function normalizedDraft(node: ScratchpadNode): ScratchpadNode {
  if (node.type === 'stroke' || node.type === 'text') return node;
  const x = node.width < 0 ? node.x + node.width : node.x;
  const y = node.height < 0 ? node.y + node.height : node.y;
  return { ...node, x, y, width: Math.abs(node.width), height: Math.abs(node.height) };
}

function CanvasNode({
  node,
  selectable,
  erasable,
  selected,
  disabled,
  register,
  onSelect,
  onErase,
  onEdit,
  onChange,
}: {
  node: ScratchpadNode;
  selectable: boolean;
  erasable: boolean;
  selected: boolean;
  disabled: boolean;
  register: (id: string, instance: Konva.Group | null) => void;
  onSelect: (id: string, additive: boolean) => void;
  onErase: (id: string) => void;
  onEdit: (node: Extract<ScratchpadNode, { type: 'text' }>) => void;
  onChange: (id: string, changes: Partial<ScratchpadNode>) => void;
}) {
  const common = {
    stroke: 'stroke' in node ? node.stroke : undefined,
    strokeWidth: 'stroke_width' in node ? node.stroke_width : undefined,
  };
  return (
    <Group
      ref={(instance) => register(node.id, instance)}
      id={node.id}
      name="scratchpad-node"
      x={node.x}
      y={node.y}
      rotation={node.rotation ?? 0}
      scaleX={node.scale_x ?? 1}
      scaleY={node.scale_y ?? 1}
      draggable={selectable && selected && !disabled}
      onPointerDown={(event) => {
        if (disabled) return;
        if (erasable) {
          event.cancelBubble = true;
          onErase(node.id);
          return;
        }
        if (selectable) {
          event.cancelBubble = true;
          onSelect(node.id, event.evt.shiftKey);
        }
      }}
      onDragEnd={(event) =>
        onChange(node.id, { x: event.target.x(), y: event.target.y() })
      }
      onTransformEnd={(event) =>
        onChange(node.id, {
          x: event.target.x(),
          y: event.target.y(),
          scale_x: event.target.scaleX(),
          scale_y: event.target.scaleY(),
        })
      }
      onDblClick={(event) => {
        if (node.type === 'text' && selectable && !disabled) {
          event.cancelBubble = true;
          onEdit(node);
        }
      }}
      onDblTap={(event) => {
        if (node.type === 'text' && selectable && !disabled) {
          event.cancelBubble = true;
          onEdit(node);
        }
      }}
    >
      {node.type === 'stroke' && (
        <Line
          points={node.points}
          {...common}
          lineCap="round"
          lineJoin="round"
          tension={0.35}
        />
      )}
      {node.type === 'rectangle' && (
        <Rect width={node.width} height={node.height} {...common} />
      )}
      {node.type === 'ellipse' && (
        <Ellipse
          x={node.width / 2}
          y={node.height / 2}
          radiusX={Math.abs(node.width / 2)}
          radiusY={Math.abs(node.height / 2)}
          {...common}
        />
      )}
      {node.type === 'line' && (
        <Line
          points={[0, 0, node.width, node.height]}
          {...common}
          lineCap="round"
        />
      )}
      {node.type === 'text' && (
        <Text
          text={node.text}
          fill={node.fill}
          fontSize={node.font_size}
          width={node.width}
          height={node.height}
          fontFamily="CursorGothic, system-ui, sans-serif"
        />
      )}
    </Group>
  );
}

export const ScratchpadCanvas = forwardRef<
  ScratchpadCanvasHandle,
  ScratchpadCanvasProps
>(function ScratchpadCanvas(
  {
    history,
    dispatch,
    camera,
    onCameraChange,
    tool,
    feedbackRegions,
    exportBounds,
    disabled,
  },
  ref,
) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const transformerRef = useRef<Konva.Transformer | null>(null);
  const nodeRefs = useRef(new Map<string, Konva.Group>());
  const panRef = useRef<{ pointer: Point; camera: ScratchpadCamera } | null>(null);
  const selectionStartRef = useRef<Point | null>(null);
  const pinchRef = useRef<{ distance: number; camera: ScratchpadCamera } | null>(null);
  const [size, setSize] = useState({ width: 800, height: 600 });
  const [draft, setDraft] = useState<ScratchpadNode | null>(null);
  const [selectionRect, setSelectionRect] = useState<SceneRect | null>(null);
  const [textDraft, setTextDraft] = useState<TextDraft | null>(null);
  const ink = cssColor('--color-ink', '#26251e');

  useImperativeHandle(ref, () => ({
    focus: () => hostRef.current?.focus(),
  }));

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const update = () => {
      const rect = host.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        setSize({ width: rect.width, height: rect.height });
      }
    };
    update();
    if (typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(update);
    observer.observe(host);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const selected = history.selectedIds
      .map((id) => nodeRefs.current.get(id))
      .filter((node): node is Konva.Group => Boolean(node));
    transformerRef.current?.nodes(selected);
    transformerRef.current?.getLayer()?.batchDraw();
  }, [history.present, history.selectedIds]);

  const pointerScene = useCallback(
    (stage: Konva.Stage): Point | null => {
      const point = stage.getPointerPosition();
      return point ? screenToScene(point, camera) : null;
    },
    [camera],
  );

  const selectNode = useCallback(
    (id: string, additive: boolean) => {
      const ids = !additive && history.selectedIds.includes(id)
        ? history.selectedIds
        : additive
        ? history.selectedIds.includes(id)
          ? history.selectedIds.filter((selectedId) => selectedId !== id)
          : [...history.selectedIds, id]
        : [id];
      dispatch({ type: 'select', ids });
    },
    [dispatch, history.selectedIds],
  );

  const beginDrawing = useCallback(
    (point: Point) => {
      const id = nextNodeId();
      if (tool === 'pen') {
        setDraft({
          id,
          type: 'stroke',
          x: point.x,
          y: point.y,
          points: [0, 0],
          stroke: ink,
          stroke_width: STROKE_WIDTH,
        });
      } else if (tool === 'rectangle' || tool === 'ellipse') {
        setDraft({
          id,
          type: tool,
          x: point.x,
          y: point.y,
          width: 0,
          height: 0,
          stroke: ink,
          stroke_width: STROKE_WIDTH,
        });
      }
    },
    [ink, tool],
  );

  const handlePointerDown = useCallback(
    (event: Konva.KonvaEventObject<PointerEvent>) => {
      if (disabled) return;
      const stage = event.target.getStage();
      if (!stage) return;
      const screen = stage.getPointerPosition();
      const point = pointerScene(stage);
      if (!screen || !point) return;
      if (tool === 'hand' || event.evt.button === 1) {
        panRef.current = { pointer: screen, camera };
        return;
      }
      if (tool === 'text') {
        setTextDraft({ x: point.x, y: point.y, value: '' });
        return;
      }
      if (tool === 'select') {
        dispatch({ type: 'select', ids: [] });
        selectionStartRef.current = point;
        setSelectionRect({ x: point.x, y: point.y, width: 0, height: 0 });
        return;
      }
      if (tool === 'pen' || tool === 'rectangle' || tool === 'ellipse') {
        beginDrawing(point);
      }
    },
    [beginDrawing, camera, disabled, dispatch, pointerScene, tool],
  );

  const handlePointerMove = useCallback(
    (event: Konva.KonvaEventObject<PointerEvent>) => {
      const stage = event.target.getStage();
      if (!stage) return;
      const screen = stage.getPointerPosition();
      const point = pointerScene(stage);
      if (!screen || !point) return;
      if (panRef.current) {
        onCameraChange({
          ...panRef.current.camera,
          x: panRef.current.camera.x + screen.x - panRef.current.pointer.x,
          y: panRef.current.camera.y + screen.y - panRef.current.pointer.y,
        });
        return;
      }
      if (draft?.type === 'stroke') {
        setDraft({
          ...draft,
          points: [...draft.points, point.x - draft.x, point.y - draft.y],
        });
      } else if (draft && draft.type !== 'text') {
        setDraft({ ...draft, width: point.x - draft.x, height: point.y - draft.y });
      } else if (selectionStartRef.current) {
        const start = selectionStartRef.current;
        setSelectionRect({
          x: Math.min(start.x, point.x),
          y: Math.min(start.y, point.y),
          width: Math.abs(point.x - start.x),
          height: Math.abs(point.y - start.y),
        });
      }
    },
    [draft, onCameraChange, pointerScene],
  );

  const finishPointer = useCallback(() => {
    panRef.current = null;
    if (draft) {
      const node = normalizedDraft(draft);
      const bounds = nodeBounds(node);
      if (bounds.width > 1 && bounds.height > 1) dispatch({ type: 'add', node });
      setDraft(null);
    }
    if (selectionRect && (selectionRect.width > 1 || selectionRect.height > 1)) {
      dispatch({
        type: 'select',
        ids: history.present
          .filter((node) => intersects(nodeBounds(node), selectionRect))
          .map((node) => node.id),
      });
    }
    selectionStartRef.current = null;
    setSelectionRect(null);
  }, [dispatch, draft, history.present, selectionRect]);

  const feedback = useMemo(() => {
    if (!exportBounds) return [];
    return feedbackRegions.map((region, index) => ({
      ...region,
      ...feedbackRegionToScene(region, exportBounds),
      index,
    }));
  }, [exportBounds, feedbackRegions]);

  return (
    <div
      ref={hostRef}
      className="scratchpad-canvas"
      role="application"
      aria-label="Scratchpad canvas"
      tabIndex={0}
    >
      <Stage
        width={size.width}
        height={size.height}
        x={camera.x}
        y={camera.y}
        scaleX={camera.scale}
        scaleY={camera.scale}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={finishPointer}
        onPointerLeave={finishPointer}
        onWheel={(event) => {
          event.evt.preventDefault();
          const stage = event.target.getStage();
          const pointer = stage?.getPointerPosition();
          if (!pointer) return;
          const scene = screenToScene(pointer, camera);
          const factor = event.evt.deltaY > 0 ? 0.9 : 1.1;
          const scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, camera.scale * factor));
          onCameraChange({
            x: pointer.x - scene.x * scale,
            y: pointer.y - scene.y * scale,
            scale,
          });
        }}
        onTouchMove={(event) => {
          const touches = event.evt.touches;
          if (touches.length !== 2) return;
          event.evt.preventDefault();
          const distance = Math.hypot(
            touches[1].clientX - touches[0].clientX,
            touches[1].clientY - touches[0].clientY,
          );
          const rect = hostRef.current?.getBoundingClientRect();
          const center = {
            x: (touches[0].clientX + touches[1].clientX) / 2 - (rect?.left ?? 0),
            y: (touches[0].clientY + touches[1].clientY) / 2 - (rect?.top ?? 0),
          };
          if (!pinchRef.current) {
            pinchRef.current = { distance, camera };
            return;
          }
          const start = pinchRef.current;
          const scale = Math.min(
            MAX_SCALE,
            Math.max(MIN_SCALE, start.camera.scale * (distance / start.distance)),
          );
          const scene = screenToScene(center, start.camera);
          onCameraChange({
            x: center.x - scene.x * scale,
            y: center.y - scene.y * scale,
            scale,
          });
        }}
        onTouchEnd={() => {
          pinchRef.current = null;
          finishPointer();
        }}
      >
        <Layer>
          {history.present.map((node) => (
            <CanvasNode
              key={node.id}
              node={node}
              selectable={tool === 'select'}
              erasable={tool === 'eraser'}
              selected={history.selectedIds.includes(node.id)}
              disabled={disabled}
              register={(id, instance) => {
                if (instance) nodeRefs.current.set(id, instance);
                else nodeRefs.current.delete(id);
              }}
              onSelect={selectNode}
              onErase={(id) => dispatch({ type: 'delete', ids: [id] })}
              onEdit={(textNode) =>
                setTextDraft({
                  id: textNode.id,
                  x: textNode.x,
                  y: textNode.y,
                  value: textNode.text,
                })
              }
              onChange={(id, changes) => dispatch({ type: 'update', id, changes })}
            />
          ))}
          {draft && (
            <CanvasNode
              node={draft}
              selectable={false}
              erasable={false}
              selected={false}
              disabled
              register={() => undefined}
              onSelect={() => undefined}
              onErase={() => undefined}
              onEdit={() => undefined}
              onChange={() => undefined}
            />
          )}
          {selectionRect && (
            <Rect
              {...selectionRect}
              fill="rgba(245, 78, 0, 0.08)"
              stroke="#f54e00"
              strokeWidth={1 / camera.scale}
              dash={[4 / camera.scale, 4 / camera.scale]}
            />
          )}
          <Transformer
            ref={transformerRef}
            rotateEnabled={false}
            flipEnabled={false}
            borderStroke="#f54e00"
            anchorStroke="#f54e00"
            anchorFill="#ffffff"
            anchorSize={8}
          />
        </Layer>
        <Layer listening={false}>
          {feedback.map((region) => (
            <Group key={`${region.index}-${region.label}`} x={region.x} y={region.y}>
              <Rect
                width={Math.max(24 / camera.scale, region.width)}
                height={Math.max(24 / camera.scale, region.height)}
                stroke="#cf2d56"
                strokeWidth={2 / camera.scale}
                dash={[6 / camera.scale, 4 / camera.scale]}
              />
              <Ellipse
                x={0}
                y={0}
                radiusX={11 / camera.scale}
                radiusY={11 / camera.scale}
                fill="#cf2d56"
              />
              <Text
                text={String(region.index + 1)}
                x={-11 / camera.scale}
                y={-11 / camera.scale}
                width={22 / camera.scale}
                height={22 / camera.scale}
                align="center"
                verticalAlign="middle"
                fill="#ffffff"
                fontSize={12 / camera.scale}
              />
            </Group>
          ))}
        </Layer>
      </Stage>
      <div className="scratchpad-feedback-callouts">
        {feedback.map((region) => (
          <button
            key={`callout-${region.index}`}
            type="button"
            className="scratchpad-feedback-callout"
            aria-label={`${region.index + 1}. ${region.label}${region.explanation ? `: ${region.explanation}` : ''}`}
            style={{
              left: region.x * camera.scale + camera.x,
              top: (region.y + region.height) * camera.scale + camera.y + 8,
            }}
          >
            <span>{region.index + 1}</span>
            <span className="scratchpad-feedback-callout__tooltip">
              <strong>{region.label || `Issue ${region.index + 1}`}</strong>
              {region.explanation && <small>{region.explanation}</small>}
            </span>
          </button>
        ))}
      </div>
      {textDraft && (
        <textarea
          className="scratchpad-canvas__text-editor"
          aria-label="Canvas text"
          autoFocus
          value={textDraft.value}
          style={{
            left: textDraft.x * camera.scale + camera.x,
            top: textDraft.y * camera.scale + camera.y,
          }}
          onChange={(event) =>
            setTextDraft((current) =>
              current ? { ...current, value: event.target.value } : null,
            )
          }
          onKeyDown={(event) => {
            if (event.key === 'Escape') setTextDraft(null);
            if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
              event.currentTarget.blur();
            }
          }}
          onBlur={() => {
            if (textDraft.value.trim()) {
              if (textDraft.id) {
                dispatch({
                  type: 'update',
                  id: textDraft.id,
                  changes: { text: textDraft.value.trim() },
                });
              } else {
                dispatch({
                  type: 'add',
                  node: {
                    id: nextNodeId(),
                    type: 'text',
                    x: textDraft.x,
                    y: textDraft.y,
                    text: textDraft.value.trim(),
                    fill: ink,
                    font_size: 20,
                    width: 220,
                    height: 80,
                  },
                });
              }
            }
            setTextDraft(null);
          }}
        />
      )}
      <div className="visually-hidden" aria-live="polite">
        {feedback.map((region) => (
          <p key={`accessible-${region.index}`}>
            {region.index + 1}. {region.label}
            {region.explanation ? `: ${region.explanation}` : ''}
          </p>
        ))}
      </div>
    </div>
  );
});
