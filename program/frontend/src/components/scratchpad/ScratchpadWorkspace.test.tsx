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
        history,
        tool,
      }: {
        dispatch: (action: unknown) => void;
        history: { present: Array<{ id: string }> };
        tool: string;
      },
      _ref,
    ) {
      return (
        <div>
          <button
            type="button"
            data-testid="fake-konva"
            data-tool={tool}
            onClick={() => {
              const node = {
                id: `rect-${history.present.length + 1}`,
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
          <button
            type="button"
            data-testid="fake-select-all"
            onClick={() =>
              dispatch({
                type: 'select',
                ids: history.present.map((node) => node.id),
              })
            }
          >
            select all
          </button>
        </div>
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
    onAskSelection: vi.fn().mockResolvedValue({
      tutorMessage: 'Look at the marked step.',
      feedbackRegions: [],
    }),
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

    await userEvent.click(screen.getByRole('button', { name: /Ask about selection/i }));
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

  it('shows Why skip? in the bottom overlay and submits a reason', async () => {
    const onSubmitSkipReason = vi.fn().mockResolvedValue(undefined);
    renderWorkspace({
      skipPrompt: true,
      onSubmitSkipReason,
    });

    expect(screen.getByText('Why skip?')).toBeInTheDocument();
    expect(document.querySelector('.scratchpad-tutor-overlay')).toBeTruthy();
    expect(screen.getByRole('button', { name: /Skip question/i })).toBeDisabled();
    expect(screen.queryByRole('button', { name: /Ask about selection/i })).not.toBeInTheDocument();

    const continueBtn = screen.getByRole('button', { name: /^Continue$/i });
    expect(continueBtn).toBeDisabled();

    await userEvent.type(
      screen.getByRole('textbox', { name: /Skip reason/i }),
      'Already know this',
    );
    expect(continueBtn).toBeEnabled();
    await userEvent.click(continueBtn);

    await waitFor(() =>
      expect(onSubmitSkipReason).toHaveBeenCalledWith('Already know this'),
    );
  });

  it('submits skip reason with Enter and stays disabled while busy', async () => {
    const onSubmitSkipReason = vi.fn().mockResolvedValue(undefined);
    const { rerender, props } = renderWorkspace({
      skipPrompt: true,
      onSubmitSkipReason,
      chatStatus: 'idle',
    });

    const input = screen.getByRole('textbox', { name: /Skip reason/i });
    await userEvent.type(input, 'Too hard{Enter}');
    await waitFor(() => expect(onSubmitSkipReason).toHaveBeenCalledWith('Too hard'));

    rerender(
      <ScratchpadWorkspace
        {...props}
        skipPrompt
        onSubmitSkipReason={onSubmitSkipReason}
        chatStatus="generating"
      />,
    );
    expect(screen.getByRole('textbox', { name: /Skip reason/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /^Continue$/i })).toBeDisabled();
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
        feedback: 'Correct. The intersection is {2}. [Source: sets_definition — §1]',
      },
      initialScene: {
        question_number: 1,
        schema_version: 1,
        engine: 'apore-konva',
        nodes: [
          {
            id: 'rect-1',
            type: 'rectangle',
            x: 10,
            y: 20,
            width: 40,
            height: 30,
            stroke: '#26251e',
            stroke_width: 2,
          },
        ],
        camera: { x: 0, y: 0, scale: 1 },
        last_export_bounds: { x: 0, y: 10, width: 70, height: 60, padding: 12 },
        feedback_regions: [],
        annotations: [],
      },
    });

    expect(
      screen.getByRole('dialog', { name: /Grade result for selection/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent(/✓ Correct/i);
    expect(screen.getByText(/The intersection is \{2\}/i)).toBeInTheDocument();
    expect(screen.getByText('How difficult was that?')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Skip question/i })).not.toBeInTheDocument();
  });

  it('keeps the grade reply visible during reflection while overlay shows continue', () => {
    renderWorkspace({
      phase: 'reflection',
      graded: {
        question_number: 1,
        correct: 'no',
        hint_count: 1,
        turn_count: 2,
        hedging_count: 0,
        feedback: 'Not quite. Revisit the union boundary. [Source: set_operations — §2]',
      },
      initialScene: {
        question_number: 1,
        schema_version: 1,
        engine: 'apore-konva',
        nodes: [
          {
            id: 'rect-1',
            type: 'rectangle',
            x: 10,
            y: 20,
            width: 40,
            height: 30,
            stroke: '#26251e',
            stroke_width: 2,
          },
        ],
        camera: { x: 0, y: 0, scale: 1 },
        last_export_bounds: { x: 0, y: 10, width: 70, height: 60, padding: 12 },
        feedback_regions: [],
        annotations: [],
      },
    });

    expect(
      screen.getByRole('dialog', { name: /Grade result for selection/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent(/✗ Incorrect/i);
    expect(screen.getByText(/Revisit the union boundary/i)).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /Continue to next question/i }),
    ).toBeInTheDocument();
    expect(screen.queryByText('How difficult was that?')).not.toBeInTheDocument();
  });

  it('shows assisted correct wording in the anchored grade panel', () => {
    renderWorkspace({
      phase: 'rating',
      graded: {
        question_number: 1,
        correct: 'yes',
        hint_count: 2,
        turn_count: 3,
        hedging_count: 0,
        assisted: true,
        feedback: 'Correct. You got there with a hint.',
      },
      initialScene: {
        question_number: 1,
        schema_version: 1,
        engine: 'apore-konva',
        nodes: [
          {
            id: 'rect-1',
            type: 'rectangle',
            x: 10,
            y: 20,
            width: 40,
            height: 30,
            stroke: '#26251e',
            stroke_width: 2,
          },
        ],
        camera: { x: 0, y: 0, scale: 1 },
        last_export_bounds: { x: 0, y: 10, width: 70, height: 60, padding: 12 },
        feedback_regions: [],
        annotations: [],
      },
    });

    expect(screen.getByRole('status')).toHaveTextContent(/✓ Correct \(with tutor help\)/i);
    expect(screen.getByText(/You got there with a hint/i)).toBeInTheDocument();
    // Explanation lives in the anchored panel, not duplicated as overlay prose alone.
    expect(screen.getByText('How difficult was that?')).toBeInTheDocument();
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

  it('shows thinking immediately, then replaces it with the response at the same anchor', async () => {
    let resolveAsk!: (value: {
      tutorMessage: string;
      feedbackRegions: never[];
    }) => void;
    const onAskSelection = vi.fn(
      () =>
        new Promise<{ tutorMessage: string; feedbackRegions: never[] }>((resolve) => {
          resolveAsk = resolve;
        }),
    );
    renderWorkspace({ onAskSelection });
    await userEvent.click(await screen.findByTestId('fake-konva'));
    await userEvent.click(screen.getByRole('button', { name: /Ask about selection/i }));
    const prompt = await screen.findByPlaceholderText(/Ask Apore about this/i);
    await userEvent.type(prompt, 'Is this ordered?');
    await userEvent.click(screen.getByRole('button', { name: /Ask Apore/i }));

    const thinking = await screen.findByRole('status', { name: /Apore is thinking/i });
    expect(thinking).toHaveTextContent(/Is this ordered?/i);
    const thinkingLeft = thinking.style.left;
    const thinkingTop = thinking.style.top;
    expect(screen.queryByRole('dialog', { name: /Apore reply for selection/i })).not.toBeInTheDocument();

    await act(async () => {
      resolveAsk({
        tutorMessage: 'No — sets are unordered.',
        feedbackRegions: [],
      });
    });

    const reply = await screen.findByRole('dialog', { name: /Apore reply for selection/i });
    expect(reply).toHaveTextContent(/No — sets are unordered./i);
    expect(reply).toHaveStyle({ left: thinkingLeft, top: thinkingTop });
    expect(screen.queryByRole('status', { name: /Apore is thinking/i })).not.toBeInTheDocument();
  });

  it('routes Ask and Submit with the selected PNG', async () => {
    const onAskSelection = vi.fn().mockResolvedValue({
      tutorMessage: 'Check the definition again.',
      feedbackRegions: [],
    });
    const onSubmitSelection = vi.fn().mockResolvedValue(undefined);
    const { rerender, props } = renderWorkspace({ onAskSelection, onSubmitSelection });
    await userEvent.click(await screen.findByTestId('fake-konva'));
    await userEvent.click(screen.getByRole('button', { name: /Ask about selection/i }));
    const prompt = await screen.findByPlaceholderText(/Ask Apore about this/i);
    await userEvent.type(prompt, 'Is this right?');
    await userEvent.click(screen.getByRole('button', { name: /Ask Apore/i }));
    expect(onAskSelection).toHaveBeenCalledWith(
      'data:image/png;base64,cG5n',
      'Is this right?',
    );
    expect(
      await screen.findByRole('dialog', { name: /Apore reply for selection/i }),
    ).toHaveTextContent('Check the definition again.');

    await userEvent.click(await screen.findByTestId('fake-konva'));
    await userEvent.click(screen.getByRole('button', { name: /Submit as answer/i }));
    expect(await screen.findByRole('dialog', { name: /Submit selected answer/i })).toBeInTheDocument();
    expect(screen.getByText(/Only this selected region will be graded/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /Submit selected answer/i }));
    expect(onSubmitSelection).toHaveBeenCalledWith('data:image/png;base64,cG5n');

    rerender(<ScratchpadWorkspace {...props} phase="rating" graded={{
      question_number: 1,
      correct: 'yes',
      hint_count: 0,
      turn_count: 1,
      hedging_count: 0,
    }} />);
    expect(screen.queryByRole('dialog', { name: /Submit selected answer|Grading selected answer/i })).not.toBeInTheDocument();
  });

  it('opens slash composer at the selection-action top-right anchor', async () => {
    renderWorkspace();
    await userEvent.click(await screen.findByTestId('fake-konva'));
    const action = screen.getByTestId('scratchpad-selection-action');
    // Fake node is at (10,20)/(40×30) with stroke 2 → top-right screen ≈ (63,19),
    // clamped to toolbar floor (60) and desktop gutter (64).
    expect(action).toHaveStyle({ left: '64px', top: '60px' });
    const actionLeft = action.style.left;
    const actionTop = action.style.top;

    await act(async () => {
      document.dispatchEvent(new KeyboardEvent('keydown', { key: '/', bubbles: true }));
    });
    const dialog = await screen.findByRole('dialog', { name: /Ask about selection/i });
    expect(dialog).toHaveStyle({ left: actionLeft, top: actionTop });
    expect(dialog).toHaveStyle({ left: '64px', top: '60px' });
  });

  it('keeps Ask chip and prompt at selection top-right in narrow viewports', async () => {
    const matchMedia = window.matchMedia;
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: query.includes('max-width: 959px'),
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));

    try {
      renderWorkspace();
      await userEvent.click(await screen.findByTestId('fake-konva'));
      const action = screen.getByTestId('scratchpad-selection-action');
      // Narrow gutter is 12px, so left stays at selection top-right (63), not bottom-docked.
      expect(action).toHaveStyle({ left: '63px', top: '60px' });
      expect(Number.parseFloat(action.style.top)).toBeLessThan(200);

      await act(async () => {
        document.dispatchEvent(new KeyboardEvent('keydown', { key: '/', bubbles: true }));
      });
      const dialog = await screen.findByRole('dialog', { name: /Ask about selection/i });
      expect(dialog).toHaveStyle({ left: '63px', top: '60px' });
    } finally {
      window.matchMedia = matchMedia;
    }
  });

  it('shows retry on ask failure and dismisses the failed request', async () => {
    const onAskSelection = vi
      .fn()
      .mockRejectedValueOnce(new Error('network down'))
      .mockResolvedValueOnce({
        tutorMessage: 'Try rewriting the definition.',
        feedbackRegions: [],
      });
    renderWorkspace({ onAskSelection });
    await userEvent.click(await screen.findByTestId('fake-konva'));
    await userEvent.click(screen.getByRole('button', { name: /Ask about selection/i }));
    await userEvent.click(screen.getByRole('button', { name: /Ask Apore/i }));

    expect(await screen.findByRole('alertdialog', { name: /Ask failed/i })).toHaveTextContent(
      'network down',
    );
    await userEvent.click(screen.getByRole('button', { name: /^Retry$/i }));
    expect(
      await screen.findByRole('dialog', { name: /Apore reply for selection/i }),
    ).toHaveTextContent('Try rewriting the definition.');
    expect(onAskSelection).toHaveBeenCalledTimes(2);
  });

  it('collapses replies to markers and restores annotations from the scene', async () => {
    const onAskSelection = vi.fn().mockResolvedValue({
      tutorMessage: 'Sets have no order.',
      feedbackRegions: [],
    });
    renderWorkspace({ onAskSelection });
    await userEvent.click(await screen.findByTestId('fake-konva'));
    await userEvent.click(screen.getByRole('button', { name: /Ask about selection/i }));
    await userEvent.click(screen.getByRole('button', { name: /Ask Apore/i }));
    expect(
      await screen.findByRole('dialog', { name: /Apore reply for selection/i }),
    ).toHaveTextContent('Sets have no order.');

    await userEvent.click(document.body);
    expect(screen.queryByRole('dialog', { name: /Apore reply for selection/i })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /Open Apore reply for selection/i }));
    expect(screen.getByRole('dialog', { name: /Apore reply for selection/i })).toBeInTheDocument();
  });

  it('hydrates persisted annotations and allows dismiss', async () => {
    renderWorkspace({
      initialScene: {
        question_number: 1,
        schema_version: 1,
        engine: 'apore-konva',
        nodes: [
          {
            id: 'rect-1',
            type: 'rectangle',
            x: 10,
            y: 20,
            width: 40,
            height: 30,
            stroke: '#26251e',
            stroke_width: 2,
          },
        ],
        camera: { x: 0, y: 0, scale: 1 },
        last_export_bounds: null,
        feedback_regions: [],
        annotations: [
          {
            id: 'ann-1',
            node_ids: ['rect-1'],
            prompt: 'Is this ordered?',
            response: 'No — sets are unordered.',
            feedback_regions: [],
          },
        ],
      },
    });
    expect(screen.getByRole('button', { name: /Open Apore reply for selection/i })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /Open Apore reply for selection/i }));
    expect(screen.getByRole('dialog', { name: /Apore reply for selection/i })).toHaveTextContent(
      'No — sets are unordered.',
    );

    await userEvent.click(screen.getByRole('button', { name: /Dismiss reply/i }));
    await userEvent.click(screen.getByRole('button', { name: /Confirm dismiss reply/i }));
    expect(screen.queryByRole('button', { name: /Open Apore reply for selection/i })).not.toBeInTheDocument();
  });

  it('drops annotations when linked nodes are deleted', async () => {
    renderWorkspace({
      initialScene: {
        question_number: 1,
        schema_version: 1,
        engine: 'apore-konva',
        nodes: [
          {
            id: 'rect-1',
            type: 'rectangle',
            x: 10,
            y: 20,
            width: 40,
            height: 30,
            stroke: '#26251e',
            stroke_width: 2,
          },
        ],
        camera: { x: 0, y: 0, scale: 1 },
        last_export_bounds: null,
        feedback_regions: [],
        annotations: [
          {
            id: 'ann-gone',
            node_ids: ['rect-1'],
            prompt: '',
            response: 'Linked reply',
            feedback_regions: [],
          },
        ],
      },
    });
    expect(screen.getByRole('button', { name: /Open Apore reply for selection/i })).toBeInTheDocument();
    await userEvent.click(await screen.findByTestId('fake-select-all'));
    await act(async () => {
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Delete', bubbles: true }));
    });
    await waitFor(() =>
      expect(
        screen.queryByRole('button', { name: /Open Apore reply for selection/i }),
      ).not.toBeInTheDocument(),
    );
  });

  it('persists annotations in the autosaved scene payload', async () => {
    const onAskSelection = vi.fn().mockResolvedValue({
      tutorMessage: 'Persist me.',
      feedbackRegions: [],
    });
    renderWorkspace({ onAskSelection });
    await userEvent.click(await screen.findByTestId('fake-konva'));
    await userEvent.click(screen.getByRole('button', { name: /Ask about selection/i }));
    await userEvent.click(screen.getByRole('button', { name: /Ask Apore/i }));
    await screen.findByRole('dialog', { name: /Apore reply for selection/i });

    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 850));
    });
    const payloads = putScratchpadScene.mock.calls.map((call) => call[1]);
    expect(
      payloads.some(
        (payload) =>
          Array.isArray(payload.annotations) &&
          payload.annotations.some(
            (annotation: { response: string }) => annotation.response === 'Persist me.',
          ),
      ),
    ).toBe(true);
  });

  it('keeps local work on save failure and clears only on clearSceneToken', async () => {
    putScratchpadScene.mockRejectedValueOnce(new Error('network'));
    const { rerender, props } = renderWorkspace();
    await userEvent.click(await screen.findByTestId('fake-konva'));
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 850));
    });
    expect(screen.getByText('Canvas not saved yet')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Ask about selection/i })).toBeInTheDocument();
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 2050));
    });
    expect(putScratchpadScene.mock.calls.length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText('Canvas not saved yet')).not.toBeInTheDocument();

    rerender(<ScratchpadWorkspace {...props} clearSceneToken={1} />);
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: /Ask about selection/i })).not.toBeInTheDocument(),
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

    await userEvent.click(screen.getByRole('button', { name: 'Text' }));
    expect(canvas).toHaveAttribute('data-tool', 'text');

    await act(async () => {
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'e', bubbles: true }));
    });
    expect(canvas).toHaveAttribute('data-tool', 'eraser');
  });

  it('shows the question on initial entry as if already opened by click', () => {
    renderWorkspace();
    expect(screen.getByLabelText('Current question')).toHaveTextContent('Define a set.');
    expect(screen.getByRole('button', { name: /Q1\/10 · What is a Set/i })).toHaveAttribute(
      'aria-expanded',
      'true',
    );
  });

  it('reopens the question preview when the question number changes', () => {
    const { rerender, props } = renderWorkspace();
    const trigger = screen.getByRole('button', { name: /Q1\/10 · What is a Set/i });

    fireEvent.click(trigger);
    expect(screen.queryByLabelText('Current question')).not.toBeInTheDocument();

    rerender(
      <ScratchpadWorkspace
        {...props}
        questionNumber={2}
        questionText="What is the empty set?"
        conceptLabel="Empty Set"
      />,
    );

    expect(screen.getByLabelText('Current question')).toHaveTextContent('What is the empty set?');
    expect(screen.getByRole('button', { name: /Q2\/10 · Empty Set/i })).toHaveAttribute(
      'aria-expanded',
      'true',
    );
  });

  it('shows the question while the concept trigger is hovered or focused', async () => {
    renderWorkspace();
    const trigger = screen.getByRole('button', { name: /Q1\/10 · What is a Set/i });
    expect(screen.getByLabelText('Current question')).toBeInTheDocument();

    // Dismiss the initial click-open state, then leave click mode so hover/focus work.
    fireEvent.click(trigger);
    expect(screen.queryByLabelText('Current question')).not.toBeInTheDocument();
    fireEvent.mouseLeave(trigger);

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
    expect(screen.getByLabelText('Current question')).toBeInTheDocument();

    fireEvent.click(trigger);
    expect(screen.queryByLabelText('Current question')).not.toBeInTheDocument();
    fireEvent.click(trigger);
    expect(screen.getByLabelText('Current question')).toBeInTheDocument();
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
