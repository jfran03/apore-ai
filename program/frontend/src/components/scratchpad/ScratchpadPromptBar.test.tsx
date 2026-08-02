import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ScratchpadPromptBar } from './ScratchpadPromptBar';

describe('ScratchpadPromptBar', () => {
  it('asks on send / Enter and submits as answer', async () => {
    const onAsk = vi.fn();
    const onSubmit = vi.fn();
    const onClose = vi.fn();
    const onPromptChange = vi.fn();

    render(
      <ScratchpadPromptBar
        open
        busy={false}
        selectionCount={2}
        prompt="check this"
        position={{ left: 40, top: 80 }}
        onPromptChange={onPromptChange}
        onAsk={onAsk}
        onSubmit={onSubmit}
        onClose={onClose}
      />,
    );

    expect(screen.getByRole('dialog', { name: /Ask about selection/i })).toBeInTheDocument();
    expect(screen.getByText(/2 selected/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /Ask Apore/i }));
    expect(onAsk).toHaveBeenCalledTimes(1);

    await userEvent.click(screen.getByRole('button', { name: /Submit answer/i }));
    expect(onSubmit).toHaveBeenCalledTimes(1);

    await userEvent.click(screen.getByRole('button', { name: /Clear selection prompt/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('hides when closed', () => {
    const { container } = render(
      <ScratchpadPromptBar
        open={false}
        busy={false}
        selectionCount={1}
        prompt=""
        position={{ left: 0, top: 0 }}
        onPromptChange={vi.fn()}
        onAsk={vi.fn()}
        onSubmit={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
