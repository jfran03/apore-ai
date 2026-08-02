import { forwardRef, type ComponentProps } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const putScratchpadScene = vi.fn().mockResolvedValue({});
const exportKonvaSelection = vi.fn();

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client');
  return {
    ...actual,
    putScratchpadScene: (...args: unknown[]) => putScratchpadScene(...args),
  };
});

vi.mock('./scratchpadKonva', () => ({
  exportKonvaSelection: (...args: unknown[]) => exportKonvaSelection(...args),
}));

vi.mock('./ScratchpadCanvas', async () => {
  const { createHistory } = await vi.importActual<typeof import('./scratchpadModel')>(
    './scratchpadModel',
  );
  return {
    ScratchpadCanvas: forwardRef(function FakeCanvas(
      {
        dispatch,
        tool,
      }: {
        dispatch: (action: unknown) => void;
        tool: string;
      },
      _ref,
    ) {
      return (
        <button
          type="button"
          data-testid="fake-konva"
          data-tool={tool}
          onClick={() => {
            const node = {
              id: 'rect-1',
              type: 'rectangle' as const,
              x: 10,
              y: 20,
              width: 40,
              height: 30,
              stroke: '#26251e',
              stroke_width: 2,
            };
            dispatch({ type: 'add', node });
            dispatch({ type: 'select', ids: [node.id] });
          }}
        >
          canvas
        </button>
      );
    }),
    createHistory,
  };
});

import { ScratchpadWorkspace } from './ScratchpadWorkspace';

function renderWorkspace(
  overrides: Partial<ComponentProps<typeof ScratchpadWorkspace>> = {},
) {
  const props: ComponentProps<typeof ScratchpadWorkspace> = {
    sessionId: 'sess-1',
    questionNumber: 1,
    questionText: 'Define a set.',
    conceptLabel: 'What is a Set',
    maxQuestions: 10,
    scalar: 0.62,
    turnCount: 3,
    initialScene: null,
    chatStatus: 'idle',
    pendingReveal: null,
    phase: 'dialogue',
    graded: null,
    feedbackRegions: [],
    disabled: false,
    metaOpen: false,
    onMetaOpenChange: vi.fn(),
    onExitSession: vi.fn(),
    onAskSelection: vi.fn(),
    onSubmitSelection: vi.fn(),
    onSubmitRating: vi.fn(),
    onContinueToNext: vi.fn(),
    onSkip: vi.fn(),
    onRevealComplete: vi.fn(),
    clearSceneToken: 0,
    ...overrides,
  };
  return { ...render(<ScratchpadWorkspace {...props} />), props };
}

beforeEach(() => {
  putScratchpadScene.mockClear().mockResolvedValue({});
  exportKonvaSelection.mockReset().mockReturnValue({
    imageDataUri: 'data:image/png;base64,cG5n',
    bounds: { x: 0, y: 10, width: 70, height: 60, padding: 12 },
  });
});

describe('ScratchpadWorkspace', () => {
  it('opens the selection prompt from the contextual action and slash shortcut', async () => {
    renderWorkspace();
    await userEvent.click(await screen.findByTestId('fake-konva'));

    await userEvent.click(screen.getByRole('button', { name: /Ask or submit selection/i }));
    expect(await screen.findByRole('dialog', { name: /Ask about selection/i })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /Clear selection prompt/i }));

    await act(async () => {
      document.dispatchEvent(new KeyboardEvent('keydown', { key: '/', bubbles: true }));
    });
    expect(await screen.findByRole('button', { name: /Ask Apore/i })).toBeInTheDocument();
  });

  it('keeps exit, session, difficulty, and turns in the state rail', async () => {
    const onExitSession = vi.fn();
    const onMetaOpenChange = vi.fn();
    renderWorkspace({ onExitSession, onMetaOpenChange });

    expect(screen.getByText(/Difficulty/)).toHaveTextContent('0.62');
    expect(screen.getByText(/Turns/)).toHaveTextContent('3');
    await userEvent.click(screen.getByRole('button', { name: /Exit session/i }));
    expect(onExitSession).toHaveBeenCalledOnce();
    await userEvent.click(screen.getByRole('button', { name: /^Session$/i }));
    expect(onMetaOpenChange).toHaveBeenCalledWith(true);
  });

  it('keeps Skip in the toolbar and omits dialogue tutor metadata', async () => {
    const onSkip = vi.fn().mockResolvedValue(undefined);
    renderWorkspace({
      onSkip,
    });

    const skip = screen.getByRole('button', { name: /Skip question/i });
    expect(skip.closest('.scratchpad-toolbar')).toBeTruthy();
    expect(document.querySelector('.scratchpad-tutor-overlay')).toBeNull();
    expect(screen.queryByText(/QUESTION concept:/i)).not.toBeInTheDocument();

    await userEvent.click(skip);
    await waitFor(() => expect(onSkip).toHaveBeenCalledOnce());
  });

  it('retains the rating overlay after grading', () => {
    renderWorkspace({
      phase: 'rating',
      graded: {
        question_number: 1,
        correct: 'yes',
        hint_count: 0,
        turn_count: 1,
        hedging_count: 0,
      },
    });

    expect(screen.getByText('How difficult was that?')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Skip question/i })).not.toBeInTheDocument();
  });

  it('requires a selection and ignores slash inside editable fields', async () => {
    renderWorkspace();
    const input = document.createElement('input');
    document.body.appendChild(input);
    input.focus();
    input.dispatchEvent(new KeyboardEvent('keydown', { key: '/', bubbles: true }));
    expect(screen.queryByRole('dialog', { name: /Ask about selection/i })).not.toBeInTheDocument();
    input.remove();

    document.dispatchEvent(new KeyboardEvent('keydown', { key: '/', bubbles: true }));
    expect(await screen.findByText(/Select the work you want to send/i)).toBeInTheDocument();
  });

  it('routes Ask and Submit with the selected PNG', async () => {
    const onAskSelection = vi.fn().mockResolvedValue(undefined);
    const onSubmitSelection = vi.fn().mockResolvedValue(undefined);
    renderWorkspace({ onAskSelection, onSubmitSelection });
    await userEvent.click(await screen.findByTestId('fake-konva'));
    await userEvent.click(screen.getByRole('button', { name: /Ask or submit selection/i }));
    const prompt = await screen.findByPlaceholderText(/Ask Apore about this/i);
    await userEvent.type(prompt, 'Is this right?');
    await userEvent.click(screen.getByRole('button', { name: /Ask Apore/i }));
    expect(onAskSelection).toHaveBeenCalledWith(
      'data:image/png;base64,cG5n',
      'Is this right?',
    );

    await userEvent.click(screen.getByRole('button', { name: /Ask or submit selection/i }));
    await userEvent.click(screen.getByRole('button', { name: /Submit answer/i }));
    expect(onSubmitSelection).toHaveBeenCalledWith('data:image/png;base64,cG5n');
  });

  it('keeps local work on save failure and clears only on clearSceneToken', async () => {
    putScratchpadScene.mockRejectedValueOnce(new Error('network'));
    const { rerender, props } = renderWorkspace();
    await userEvent.click(await screen.findByTestId('fake-konva'));
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 850));
    });
    expect(screen.getByText('Canvas not saved yet')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Ask or submit selection/i })).toBeInTheDocument();
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 2050));
    });
    expect(putScratchpadScene.mock.calls.length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText('Canvas not saved yet')).not.toBeInTheDocument();

    rerender(<ScratchpadWorkspace {...props} clearSceneToken={1} />);
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: /Ask or submit selection/i })).not.toBeInTheDocument(),
    );
  });

  it('switches tools with the dock and keyboard shortcuts', async () => {
    renderWorkspace();
    const canvas = await screen.findByTestId('fake-konva');
    expect(screen.getByRole('button', { name: 'Select' }).querySelector('svg')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Pen' }).querySelector('svg')).toBeTruthy();
    expect(canvas).toHaveAttribute('data-tool', 'pen');
    await userEvent.click(screen.getByRole('button', { name: 'Rectangle' }));
    expect(canvas).toHaveAttribute('data-tool', 'rectangle');

    await act(async () => {
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'e', bubbles: true }));
    });
    expect(canvas).toHaveAttribute('data-tool', 'eraser');
  });

  it('shows the question while the concept trigger is hovered or focused', async () => {
    renderWorkspace();
    const trigger = screen.getByRole('button', { name: /Q1\/10 · What is a Set/i });
    expect(screen.queryByLabelText('Current question')).not.toBeInTheDocument();

    await userEvent.hover(trigger);
    expect(screen.getByLabelText('Current question')).toHaveTextContent('Define a set.');
    await userEvent.unhover(trigger);
    expect(screen.queryByLabelText('Current question')).not.toBeInTheDocument();

    fireEvent.focus(trigger);
    expect(screen.getByLabelText('Current question')).toBeInTheDocument();
    fireEvent.blur(trigger);
    expect(screen.queryByLabelText('Current question')).not.toBeInTheDocument();
  });

  it('toggles the question preview by click for touch input', async () => {
    renderWorkspace();
    const trigger = screen.getByRole('button', { name: /Q1\/10 · What is a Set/i });

    fireEvent.click(trigger);
    expect(screen.getByLabelText('Current question')).toBeInTheDocument();
    fireEvent.click(trigger);
    expect(screen.queryByLabelText('Current question')).not.toBeInTheDocument();
  });

  it('serializes autosaves so stale requests cannot overwrite newer work', async () => {
    let resolveFirst!: () => void;
    putScratchpadScene
      .mockImplementationOnce(
        () =>
          new Promise<void>((resolve) => {
            resolveFirst = resolve;
          }),
      )
      .mockResolvedValue({});
    renderWorkspace();
    const canvas = await screen.findByTestId('fake-konva');
    await userEvent.click(canvas);
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 850));
    });
    expect(putScratchpadScene).toHaveBeenCalledTimes(1);

    await userEvent.click(canvas);
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 850));
    });
    expect(putScratchpadScene).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveFirst();
      await Promise.resolve();
    });
    await waitFor(() => expect(putScratchpadScene).toHaveBeenCalledTimes(2));
    expect(putScratchpadScene.mock.calls[1][1].nodes).toHaveLength(2);
  });
});
