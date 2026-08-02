import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { createHistory } from './scratchpadModel';

vi.mock('react-konva', () => ({
  Stage: ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="konva-stage">{children}</div>
  ),
  Layer: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
  Group: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
  Line: () => null,
  Rect: () => null,
  Ellipse: () => null,
  Text: () => null,
  Transformer: () => null,
}));

import { ScratchpadCanvas } from './ScratchpadCanvas';

describe('ScratchpadCanvas', () => {
  it('exposes the drawing surface as an accessible application', () => {
    render(
      <ScratchpadCanvas
        history={createHistory([])}
        dispatch={vi.fn()}
        camera={{ x: 0, y: 0, scale: 1 }}
        onCameraChange={vi.fn()}
        tool="pen"
        feedbackRegions={[]}
        exportBounds={null}
        disabled={false}
      />,
    );

    expect(screen.getByRole('application', { name: /Scratchpad canvas/i })).toBeInTheDocument();
    expect(screen.getByTestId('konva-stage')).toBeInTheDocument();
  });
});
