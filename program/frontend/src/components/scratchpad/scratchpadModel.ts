import type {
  FeedbackRegion,
  ScratchpadCamera,
  ScratchpadExportBounds,
  ScratchpadNode,
} from '../../api/types';

export type ScratchpadTool =
  | 'select'
  | 'pen'
  | 'rectangle'
  | 'ellipse'
  | 'line'
  | 'text'
  | 'eraser'
  | 'hand';

export interface ScratchpadHistory {
  past: ScratchpadNode[][];
  present: ScratchpadNode[];
  future: ScratchpadNode[][];
  selectedIds: string[];
}

export type ScratchpadAction =
  | { type: 'add'; node: ScratchpadNode }
  | { type: 'update'; id: string; changes: Partial<ScratchpadNode> }
  | { type: 'delete'; ids: string[] }
  | { type: 'replace'; nodes: ScratchpadNode[] }
  | { type: 'hydrate'; nodes: ScratchpadNode[] }
  | { type: 'reorder'; ids: string[]; position: 'front' | 'back' }
  | { type: 'clear' }
  | { type: 'select'; ids: string[] }
  | { type: 'undo' }
  | { type: 'redo' };

export interface Point {
  x: number;
  y: number;
}

export interface SceneRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export function createHistory(nodes: ScratchpadNode[]): ScratchpadHistory {
  return { past: [], present: nodes, future: [], selectedIds: [] };
}

function selectedStillPresent(ids: string[], nodes: ScratchpadNode[]): string[] {
  const present = new Set(nodes.map((node) => node.id));
  return ids.filter((id) => present.has(id));
}

function commit(state: ScratchpadHistory, present: ScratchpadNode[]): ScratchpadHistory {
  if (present === state.present) return state;
  return {
    past: [...state.past, state.present],
    present,
    future: [],
    selectedIds: selectedStillPresent(state.selectedIds, present),
  };
}

export function historyReducer(
  state: ScratchpadHistory,
  action: ScratchpadAction,
): ScratchpadHistory {
  switch (action.type) {
    case 'add':
      return commit(state, [...state.present, action.node]);
    case 'update': {
      const index = state.present.findIndex((node) => node.id === action.id);
      if (index < 0) return state;
      const nodes = [...state.present];
      nodes[index] = { ...nodes[index], ...action.changes } as ScratchpadNode;
      return commit(state, nodes);
    }
    case 'delete': {
      const removed = new Set(action.ids);
      const nodes = state.present.filter((node) => !removed.has(node.id));
      return nodes.length === state.present.length ? state : commit(state, nodes);
    }
    case 'replace':
      return commit(state, action.nodes);
    case 'hydrate':
      return createHistory(action.nodes);
    case 'reorder': {
      const selected = new Set(action.ids);
      const moving = state.present.filter((node) => selected.has(node.id));
      if (moving.length === 0) return state;
      const remaining = state.present.filter((node) => !selected.has(node.id));
      return commit(
        state,
        action.position === 'front'
          ? [...remaining, ...moving]
          : [...moving, ...remaining],
      );
    }
    case 'clear':
      return state.present.length === 0 ? state : commit(state, []);
    case 'select':
      return {
        ...state,
        selectedIds: selectedStillPresent(action.ids, state.present),
      };
    case 'undo': {
      const previous = state.past[state.past.length - 1];
      if (!previous) return state;
      return {
        past: state.past.slice(0, -1),
        present: previous,
        future: [state.present, ...state.future],
        selectedIds: selectedStillPresent(state.selectedIds, previous),
      };
    }
    case 'redo': {
      const next = state.future[0];
      if (!next) return state;
      return {
        past: [...state.past, state.present],
        present: next,
        future: state.future.slice(1),
        selectedIds: selectedStillPresent(state.selectedIds, next),
      };
    }
  }
}

export function nodeBounds(node: ScratchpadNode): SceneRect {
  const halfStroke = 'stroke_width' in node ? node.stroke_width / 2 : 0;
  const scaleX = Math.abs(node.scale_x ?? 1);
  const scaleY = Math.abs(node.scale_y ?? 1);
  if (node.type === 'stroke') {
    const xs: number[] = [];
    const ys: number[] = [];
    for (let index = 0; index < node.points.length; index += 2) {
      xs.push(node.x + node.points[index] * scaleX);
      ys.push(node.y + node.points[index + 1] * scaleY);
    }
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    return {
      x: minX - halfStroke * scaleX,
      y: minY - halfStroke * scaleY,
      width: maxX - minX + halfStroke * scaleX * 2,
      height: maxY - minY + halfStroke * scaleY * 2,
    };
  }
  return {
    x: node.x - halfStroke * scaleX,
    y: node.y - halfStroke * scaleY,
    width: Math.abs(node.width * scaleX) + halfStroke * scaleX * 2,
    height: Math.abs(node.height * scaleY) + halfStroke * scaleY * 2,
  };
}

export function selectedExportBounds(
  nodes: ScratchpadNode[],
  selectedIds: string[],
  padding: number,
): ScratchpadExportBounds | null {
  const selected = new Set(selectedIds);
  const bounds = nodes.filter((node) => selected.has(node.id)).map(nodeBounds);
  if (bounds.length === 0) return null;
  const minX = Math.min(...bounds.map((rect) => rect.x));
  const minY = Math.min(...bounds.map((rect) => rect.y));
  const maxX = Math.max(...bounds.map((rect) => rect.x + rect.width));
  const maxY = Math.max(...bounds.map((rect) => rect.y + rect.height));
  return {
    x: minX - padding,
    y: minY - padding,
    width: maxX - minX + padding * 2,
    height: maxY - minY + padding * 2,
    padding,
  };
}

export function screenToScene(point: Point, camera: ScratchpadCamera): Point {
  return {
    x: (point.x - camera.x) / camera.scale,
    y: (point.y - camera.y) / camera.scale,
  };
}

export function sceneToScreen(point: Point, camera: ScratchpadCamera): Point {
  return {
    x: point.x * camera.scale + camera.x,
    y: point.y * camera.scale + camera.y,
  };
}

export function feedbackRegionToScene(
  region: FeedbackRegion,
  bounds: ScratchpadExportBounds,
): SceneRect {
  return {
    x: bounds.x + region.x * bounds.width,
    y: bounds.y + region.y * bounds.height,
    width: region.w * bounds.width,
    height: region.h * bounds.height,
  };
}
