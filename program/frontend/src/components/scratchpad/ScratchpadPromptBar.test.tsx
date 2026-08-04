import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ScratchpadPromptBar } from './ScratchpadPromptBar';
import { ScratchpadAnnotationPanel } from './ScratchpadAnnotationPanel';

describe('ScratchpadPromptBar', () => {
  it('asks on send / Enter in ask mode', async () => {
    const onAsk = vi.fn();
    const onClose = vi.fn();
    const onPromptChange = vi.fn();

    render(
      <ScratchpadPromptBar
        open
        mode="ask"
        busy={false}
        selectionCount={2}
        prompt="check this"
        previewDataUri={null}
        errorMessage={null}
        position={{ left: 40, top: 80 }}
        onPromptChange={onPromptChange}
        onAsk={onAsk}
        onConfirmSubmit={vi.fn()}
        onRetrySubmit={vi.fn()}
        onClose={onClose}
      />,
    );

    expect(screen.getByRole('dialog', { name: /Ask about selection/i })).toBeInTheDocument();
    expect(screen.getByText(/2 selected/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Submit selected answer/i })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /Ask Apore/i }));
    expect(onAsk).toHaveBeenCalledTimes(1);

    await userEvent.click(screen.getByRole('button', { name: /Clear selection prompt/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('confirms submit with preview and region copy', async () => {
    const onConfirmSubmit = vi.fn();
    const onClose = vi.fn();

    render(
      <ScratchpadPromptBar
        open
        mode="submit"
        busy={false}
        selectionCount={3}
        prompt=""
        previewDataUri="data:image/png;base64,abc"
        errorMessage={null}
        position={{ left: 40, top: 80 }}
        onPromptChange={vi.fn()}
        onAsk={vi.fn()}
        onConfirmSubmit={onConfirmSubmit}
        onRetrySubmit={vi.fn()}
        onClose={onClose}
      />,
    );

    expect(screen.getByRole('dialog', { name: /Submit selected answer/i })).toBeInTheDocument();
    expect(screen.getByText(/Only this selected region will be graded/i)).toBeInTheDocument();
    expect(screen.getByAltText(/Selected answer region/i)).toHaveAttribute(
      'src',
      'data:image/png;base64,abc',
    );

    await userEvent.click(screen.getByRole('button', { name: /Submit selected answer/i }));
    expect(onConfirmSubmit).toHaveBeenCalledTimes(1);

    await userEvent.click(screen.getByRole('button', { name: /^Cancel$/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('shows submitting status and disables cancel escape path via busy confirm', () => {
    render(
      <ScratchpadPromptBar
        open
        mode="submitting"
        busy
        selectionCount={1}
        prompt=""
        previewDataUri="data:image/png;base64,abc"
        errorMessage={null}
        position={{ left: 0, top: 0 }}
        onPromptChange={vi.fn()}
        onAsk={vi.fn()}
        onConfirmSubmit={vi.fn()}
        onRetrySubmit={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByRole('dialog', { name: /Grading selected answer/i })).toBeInTheDocument();
    expect(screen.getByText(/Saving canvas and grading/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Submitting/i })).toBeDisabled();
    expect(screen.queryByRole('button', { name: /^Cancel$/i })).not.toBeInTheDocument();
  });

  it('offers retry on submit error', async () => {
    const onRetrySubmit = vi.fn();
    render(
      <ScratchpadPromptBar
        open
        mode="submit-error"
        busy={false}
        selectionCount={1}
        prompt=""
        previewDataUri="data:image/png;base64,abc"
        errorMessage="Network failed"
        position={{ left: 0, top: 0 }}
        onPromptChange={vi.fn()}
        onAsk={vi.fn()}
        onConfirmSubmit={vi.fn()}
        onRetrySubmit={onRetrySubmit}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByRole('alert')).toHaveTextContent('Network failed');
    await userEvent.click(screen.getByRole('button', { name: /Retry submit/i }));
    expect(onRetrySubmit).toHaveBeenCalledTimes(1);
  });

  it('hides when closed', () => {
    const { container } = render(
      <ScratchpadPromptBar
        open={false}
        mode="ask"
        busy={false}
        selectionCount={1}
        prompt=""
        previewDataUri={null}
        errorMessage={null}
        position={{ left: 0, top: 0 }}
        onPromptChange={vi.fn()}
        onAsk={vi.fn()}
        onConfirmSubmit={vi.fn()}
        onRetrySubmit={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('disables ask controls while busy', () => {
    render(
      <ScratchpadPromptBar
        open
        mode="ask"
        busy
        selectionCount={1}
        prompt="busy"
        previewDataUri={null}
        errorMessage={null}
        position={{ left: 0, top: 0 }}
        onPromptChange={vi.fn()}
        onAsk={vi.fn()}
        onConfirmSubmit={vi.fn()}
        onRetrySubmit={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByPlaceholderText(/Ask Apore about this/i)).toBeDisabled();
    expect(screen.getByRole('button', { name: /Ask Apore/i })).toBeDisabled();
  });
});

describe('ScratchpadAnnotationPanel', () => {
  it('shows thinking prompt context with a live region', () => {
    render(
      <ScratchpadAnnotationPanel
        mode="loading"
        position={{ left: 12, top: 40 }}
        prompt="Is this a set?"
      />,
    );
    const status = screen.getByRole('status', { name: /Apore is thinking/i });
    expect(status).toHaveAttribute('aria-live', 'polite');
    expect(status).toHaveTextContent(/Is this a set?/i);
    expect(status).toHaveTextContent(/Reading the selected work/i);
  });

  it('renders Markdown responses and collapses on outside click', async () => {
    const onCollapse = vi.fn();
    const onDismiss = vi.fn();
    render(
      <div>
        <button type="button">Outside</button>
        <ScratchpadAnnotationPanel
          mode="response"
          position={{ left: 12, top: 40 }}
          prompt="Explain briefly"
          response="Not yet — revisit the **definition**."
          onCollapse={onCollapse}
          onDismiss={onDismiss}
        />
      </div>,
    );
    const dialog = screen.getByRole('dialog', { name: /Apore reply for selection/i });
    expect(dialog).toHaveTextContent(/Explain briefly/i);
    expect(dialog.querySelector('strong')).toHaveTextContent('definition');
    expect(screen.queryByRole('button', { name: /Collapse reply/i })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /^Outside$/i }));
    expect(onCollapse).toHaveBeenCalledTimes(1);
    expect(onDismiss).not.toHaveBeenCalled();
  });

  it('confirms before dismissing a response', async () => {
    const onDismiss = vi.fn();
    render(
      <ScratchpadAnnotationPanel
        mode="response"
        position={{ left: 12, top: 40 }}
        prompt="Explain briefly"
        response="A short reply."
        onCollapse={vi.fn()}
        onDismiss={onDismiss}
      />,
    );

    await userEvent.click(screen.getByRole('button', { name: /Dismiss reply/i }));
    expect(onDismiss).not.toHaveBeenCalled();
    expect(screen.getByText(/Dismiss this reply\?/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /^Cancel$/i }));
    expect(screen.queryByText(/Dismiss this reply\?/i)).not.toBeInTheDocument();
    expect(onDismiss).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole('button', { name: /Dismiss reply/i }));
    await userEvent.click(screen.getByRole('button', { name: /Confirm dismiss reply/i }));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it('renders error retry and marker modes', async () => {
    const onRetry = vi.fn();
    const onDismiss = vi.fn();
    const onExpand = vi.fn();

    const { rerender } = render(
      <ScratchpadAnnotationPanel
        mode="error"
        position={{ left: 12, top: 40 }}
        prompt="check this"
        error="boom"
        onRetry={onRetry}
        onDismiss={onDismiss}
      />,
    );
    expect(screen.getByRole('alertdialog', { name: /Ask failed/i })).toHaveTextContent('boom');
    expect(screen.getByText(/check this/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /^Retry$/i }));
    expect(onRetry).toHaveBeenCalledTimes(1);

    rerender(
      <ScratchpadAnnotationPanel
        mode="marker"
        position={{ left: 12, top: 40 }}
        onExpand={onExpand}
      />,
    );
    await userEvent.click(screen.getByRole('button', { name: /Open Apore reply for selection/i }));
    expect(onExpand).toHaveBeenCalledTimes(1);
  });

  it('renders grade verdict chrome on response mode', () => {
    render(
      <ScratchpadAnnotationPanel
        mode="response"
        kind="grade"
        position={{ left: 12, top: 40 }}
        response="Correct. The intersection is {2}."
        verdict="correct"
      />,
    );
    expect(
      screen.getByRole('dialog', { name: /Grade result for selection/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent(/✓ Correct/i);
    expect(screen.getByText(/The intersection is \{2\}/i)).toBeInTheDocument();
  });

  it('shows grade loading copy while grading', () => {
    render(
      <ScratchpadAnnotationPanel
        mode="loading"
        kind="grade"
        position={{ left: 12, top: 40 }}
      />,
    );
    const status = screen.getByRole('status', { name: /Grading selected answer/i });
    expect(status).toHaveTextContent(/Reading the selected answer/i);
  });
});
