import { describe, expect, it } from 'vitest';
import type { ScratchpadNode } from '../../api/types';
import { konvaClientRectsBounds, konvaSelectionBounds } from './scratchpadKonva';

describe('Konva selection export geometry', () => {
  it('uses rendered client bounds including stroke and padding', () => {
    const nodes: ScratchpadNode[] = [
      {
        id: 'rect-1',
        type: 'rectangle',
        x: 10,
        y: 20,
        width: 40,
        height: 30,
        stroke: '#000',
        stroke_width: 2,
      },
    ];

    expect(konvaSelectionBounds(nodes, ['rect-1'], 8)).toEqual({
      x: 1,
      y: 11,
      width: 58,
      height: 48,
      padding: 8,
    });
  });

  it('rounds fractional bounds outward to the exported canvas pixels', () => {
    const nodes: ScratchpadNode[] = [
      {
        id: 'rect-1',
        type: 'rectangle',
        x: 10.25,
        y: 20.25,
        width: 40.2,
        height: 30.2,
        stroke: '#000',
        stroke_width: 1,
      },
    ];

    expect(konvaSelectionBounds(nodes, ['rect-1'], 0)).toEqual({
      x: 9,
      y: 19,
      width: 42,
      height: 32,
      padding: 0,
    });
  });

  it('unions rendered Konva client rectangles before adding export padding', () => {
    expect(
      konvaClientRectsBounds(
        [
          { x: 10.4, y: 20.2, width: 30.2, height: 10.6 },
          { x: -2.2, y: 24, width: 8, height: 20.1 },
        ],
        4,
      ),
    ).toEqual({ x: -7, y: 16, width: 52, height: 33, padding: 4 });
  });
});
