import { act, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { createHistory } from './scratchpadModel';

type StageProps = {
  children?: React.ReactNode;
  onPointerDown?: (event: {
    target: { getStage: () => { getPointerPosition: () => { x: number; y: number } } };
    evt: PointerEvent;
  }) => void;
  onPointerUp?: () => void;
};

vi.mock('react-konva', () => ({
  Stage: ({ children, onPointerDown, onPointerUp }: StageProps) => (
    <div
      data-testid="konva-stage"
      onPointerDown={(event) => {
        onPointerDown?.({
          target: {
            getStage: () => ({
              getPointerPosition: () => ({ x: 120, y: 80 }),
            }),
          },
          evt: event.nativeEvent,
        });
      }}
      onPointerUp={() => onPointerUp?.()}
    >
      {children}
    </div>
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

function renderCanvas(
  overrides: Partial<React.ComponentProps<typeof ScratchpadCanvas>> = {},
) {
  const dispatch = vi.fn();
  const result = render(
    <ScratchpadCanvas
      history={createHistory([])}
      dispatch={dispatch}
      camera={{ x: 0, y: 0, scale: 1 }}
      onCameraChange={vi.fn()}
      tool="text"
      feedbackRegions={[]}
      exportBounds={null}
      disabled={false}
      {...overrides}
    />,
  );
  return { ...result, dispatch };
}

describe('ScratchpadCanvas', () => {
  it('exposes the drawing surface as an accessible application', () => {
    renderCanvas({ tool: 'pen' });

    expect(screen.getByRole('application', { name: /Scratchpad canvas/i })).toBeInTheDocument();
    expect(screen.getByTestId('konva-stage')).toBeInTheDocument();
  });

  it('opens a text editor on canvas click in text mode and keeps it through the opening gesture', async () => {
    renderCanvas({ tool: 'text' });

    fireEvent.pointerDown(screen.getByTestId('konva-stage'));
    const editor = await screen.findByLabelText('Canvas text');
    expect(editor).toBeInTheDocument();

    // Opening pointer gesture finishes after the overlay mounts; the editor must survive.
    fireEvent.pointerUp(screen.getByTestId('konva-stage'));
    await act(async () => {
      await new Promise((resolve) => requestAnimationFrame(() => resolve(undefined)));
    });
    expect(screen.getByLabelText('Canvas text')).toBeInTheDocument();
    expect(screen.getByLabelText('Canvas text')).toHaveFocus();
  });

  it('survives premature blur from the opening pointer gesture', async () => {
    renderCanvas({ tool: 'text' });

    fireEvent.pointerDown(screen.getByTestId('konva-stage'));
    const editor = await screen.findByLabelText('Canvas text');

    // Real browsers often blur a newly focused overlay before the opening click settles.
    fireEvent.blur(editor);
    fireEvent.pointerUp(screen.getByTestId('konva-stage'));
    await act(async () => {
      await new Promise((resolve) => requestAnimationFrame(() => resolve(undefined)));
    });

    expect(screen.getByLabelText('Canvas text')).toBeInTheDocument();
    expect(screen.getByLabelText('Canvas text')).toHaveFocus();
  });

  it('commits typed text on blur', async () => {
    const { dispatch } = renderCanvas({ tool: 'text' });

    fireEvent.pointerDown(screen.getByTestId('konva-stage'));
    const editor = await screen.findByLabelText('Canvas text');
    fireEvent.pointerUp(screen.getByTestId('konva-stage'));
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 120));
    });
    await userEvent.type(editor, 'A ⊆ B');
    await act(async () => {
      editor.blur();
    });

    expect(dispatch).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'add',
        node: expect.objectContaining({
          type: 'text',
          text: 'A ⊆ B',
          x: 120,
          y: 80,
        }),
      }),
    );
    expect(screen.queryByLabelText('Canvas text')).not.toBeInTheDocument();
  });

  it('cancels an empty text draft with Escape', async () => {
    const { dispatch } = renderCanvas({ tool: 'text' });

    fireEvent.pointerDown(screen.getByTestId('konva-stage'));
    const editor = await screen.findByLabelText('Canvas text');
    fireEvent.pointerUp(screen.getByTestId('konva-stage'));
    await userEvent.type(editor, '{Escape}');

    expect(dispatch).not.toHaveBeenCalled();
    expect(screen.queryByLabelText('Canvas text')).not.toBeInTheDocument();
  });
});
