import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { SessionTranscript } from '../api/types';

const getSessionTranscript = vi.fn();

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client');
  return {
    ...actual,
    getSessionTranscript: (...args: unknown[]) => getSessionTranscript(...args),
  };
});

import { SessionTranscriptPage } from './SessionTranscript';

function transcript(extras: Partial<SessionTranscript> = {}): SessionTranscript {
  return {
    session_id: 'sess-1',
    title: 'Sets Drill',
    created_at: '2026-01-01T00:00:00Z',
    knowledge_source: 'domain:discrete-math/01-set-theory',
    focus_mode: 'adaptive',
    max_questions: 10,
    status: 'ended_early',
    ended_at: '2026-01-01T01:00:00Z',
    body: '# Sets Drill\n',
    ...extras,
  };
}

beforeEach(() => {
  getSessionTranscript.mockReset();
});

describe('SessionTranscriptPage', () => {
  it('labels an early-ended session', async () => {
    getSessionTranscript.mockResolvedValue(transcript());
    render(
      <MemoryRouter initialEntries={['/sessions/sess-1']}>
        <Routes>
          <Route path="/sessions/:id" element={<SessionTranscriptPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText('Sets Drill')).toBeInTheDocument());
    expect(screen.getByText(/Ended early/)).toBeInTheDocument();
  });
});
