import { describe, expect, it } from 'vitest';
import type { ScratchpadNode } from '../../api/types';
import {
  createHistory,
  feedbackRegionToScene,
  historyReducer,
  nodeBounds,
  sceneToScreen,
  screenToScene,
  selectedExportBounds,
} from './scratchpadModel';

const rectangle: ScratchpadNode = {
  id: 'rect-1',
  type: 'rectangle',
  x: 10,
  y: 20,
  width: 40,
  height: 30,
  stroke: '#000',
  stroke_width: 2,
};

describe('scratchpad history', () => {
  it('undoes and redoes document changes without including selection', () => {
    let state = createHistory([]);
    state = historyReducer(state, { type: 'add', node: rectangle });
    state = historyReducer(state, { type: 'select', ids: ['rect-1'] });
    state = historyReducer(state, { type: 'undo' });

    expect(state.present).toEqual([]);
    expect(state.selectedIds).toEqual([]);

    state = historyReducer(state, { type: 'redo' });
    expect(state.present).toEqual([rectangle]);
  });

  it('clears redo history after a new document change', () => {
    let state = createHistory([rectangle]);
    state = historyReducer(state, { type: 'delete', ids: ['rect-1'] });
    state = historyReducer(state, { type: 'undo' });
    state = historyReducer(state, {
      type: 'add',
      node: { ...rectangle, id: 'rect-2' },
    });

    expect(historyReducer(state, { type: 'redo' })).toEqual(state);
  });

  it('hydrates a resumed question without creating undo history', () => {
    const state = historyReducer(createHistory([]), {
      type: 'hydrate',
      nodes: [rectangle],
    });

    expect(state).toEqual(createHistory([rectangle]));
    expect(historyReducer(state, { type: 'undo' })).toEqual(state);
  });

  it('moves selected nodes through z-order as one undoable change', () => {
    const second = { ...rectangle, id: 'rect-2' };
    let state = createHistory([rectangle, second]);
    state = historyReducer(state, {
      type: 'reorder',
      ids: ['rect-1'],
      position: 'front',
    });
    expect(state.present.map((node) => node.id)).toEqual(['rect-2', 'rect-1']);
    expect(historyReducer(state, { type: 'undo' }).present).toEqual([rectangle, second]);
  });
});

describe('scratchpad geometry', () => {
  it('computes stroke bounds from points and stroke width', () => {
    expect(
      nodeBounds({
        id: 'stroke-1',
        type: 'stroke',
        x: 5,
        y: 8,
        points: [0, 0, 20, 10, -5, 12],
        stroke: '#000',
        stroke_width: 4,
      }),
    ).toEqual({ x: -2, y: 6, width: 29, height: 16 });
  });

  it('includes group scaling in stroke export bounds', () => {
    expect(
      nodeBounds({
        id: 'stroke-1',
        type: 'stroke',
        x: 5,
        y: 8,
        points: [0, 0, 20, 10, -5, 12],
        stroke: '#000',
        stroke_width: 4,
        scale_x: 2,
        scale_y: 0.5,
      }),
    ).toEqual({ x: -9, y: 7, width: 58, height: 8 });
  });

  it('uses identical padded bounds for export and feedback anchoring', () => {
    expect(selectedExportBounds([rectangle], ['rect-1'], 8)).toEqual({
      x: 1,
      y: 11,
      width: 58,
      height: 48,
      padding: 8,
    });
  });

  it('round-trips scene and screen points through the camera', () => {
    const camera = { x: 30, y: -10, scale: 2 };
    const screen = sceneToScreen({ x: 12, y: 8 }, camera);
    expect(screen).toEqual({ x: 54, y: 6 });
    expect(screenToScene(screen, camera)).toEqual({ x: 12, y: 8 });
  });

  it('maps normalized feedback through the exact exported image bounds', () => {
    expect(
      feedbackRegionToScene(
        { x: 0.25, y: 0.5, w: 0.5, h: 0.25, label: 'Check', explanation: '' },
        { x: 10, y: 20, width: 200, height: 100, padding: 12 },
      ),
    ).toEqual({ x: 60, y: 70, width: 100, height: 25 });
  });
});
