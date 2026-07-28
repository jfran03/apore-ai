import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type {
  CreateSessionResponse,
  KnowledgeCatalog,
  KnowledgeChapter,
  QuestionBankResponse,
  QuestionResponse,
  WikiPreview,
} from '../api/types';

const getKnowledgeCatalog = vi.fn();
const getWikiPreview = vi.fn();
const getQuestionBank = vi.fn();
const getLearnerMastery = vi.fn();
const createSession = vi.fn();
const fetchQuestion = vi.fn();
const getSessionState = vi.fn();
const postTurn = vi.fn();
const listSessions = vi.fn();
const endSession = vi.fn();
const setStoredKnowledgeSource = vi.fn();

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client');
  return {
    ...actual,
    getKnowledgeCatalog: (...args: unknown[]) => getKnowledgeCatalog(...args),
    getWikiPreview: (...args: unknown[]) => getWikiPreview(...args),
    getQuestionBank: (...args: unknown[]) => getQuestionBank(...args),
    getLearnerMastery: (...args: unknown[]) => getLearnerMastery(...args),
    createSession: (...args: unknown[]) => createSession(...args),
    fetchQuestion: (...args: unknown[]) => fetchQuestion(...args),
    getSessionState: (...args: unknown[]) => getSessionState(...args),
    postTurn: (...args: unknown[]) => postTurn(...args),
    listSessions: (...args: unknown[]) => listSessions(...args),
    endSession: (...args: unknown[]) => endSession(...args),
    setStoredKnowledgeSource: (...args: unknown[]) => setStoredKnowledgeSource(...args),
  };
});

import { ActiveDomainProvider } from '../shell/ActiveDomainContext';
import { AppShell } from '../shell/AppShell';
import { Study } from './Study';

function readyChapter(id: string, domainId: string, count = 12): KnowledgeChapter {
  return {
    id,
    knowledge_source: `domain:${domainId}/${id}`,
    sources_present: true,
    source_count: 1,
    source_files: ['notes.md'],
    has_concept_graph: true,
    wiki_count: 2,
    has_question_bank: true,
    question_bank_count: count,
    compile_stage: 'idle',
    is_approved: true,
    is_stale: false,
    has_unapproved_compile: false,
  };
}

function catalogFixture(): KnowledgeCatalog {
  return {
    fixtures: [],
    domains: [
      {
        id: 'discrete-math',
        chapters: [readyChapter('01-set-theory', 'discrete-math', 12)],
      },
    ],
  };
}

function wikiPreview(): WikiPreview {
  return {
    source: 'published',
    version: 1,
    pages: [
      {
        concept_id: 'what_is_a_set',
        label: 'What is a Set',
        depth: 0,
        order: 0,
        body: 'A set is a collection.',
      },
      {
        concept_id: 'set_operations',
        label: 'Set Operations',
        depth: 1,
        order: 1,
        body: 'Union and intersection.',
      },
      {
        concept_id: 'empty_topic',
        label: 'Empty Topic',
        depth: 2,
        order: 2,
        body: 'No questions yet.',
      },
    ],
    edges: [],
  };
}

function bankResponse(): QuestionBankResponse {
  return {
    version: 1,
    path: 'question-bank.json',
    questions: [
      {
        id: 'what_is_a_set-recall-01',
        concept_id: 'what_is_a_set',
        type: 'recall',
        intended_difficulty: 0.2,
        text: 'Define a set.',
      },
      {
        id: 'set_operations-apply-01',
        concept_id: 'set_operations',
        type: 'apply',
        intended_difficulty: 0.5,
        text: 'Compute A ∪ B.',
      },
    ],
  };
}

function sessionResponse(
  conceptIds: string[],
  extras: Partial<CreateSessionResponse> = {},
): CreateSessionResponse {
  return {
    session_id: 'sess-1',
    title: '01 Set Theory — Adaptive Practice',
    scalar: 0.5,
    created_at: '2026-01-01T00:00:00Z',
    knowledge_source: 'domain:discrete-math/01-set-theory',
    focus_mode: 'adaptive',
    max_questions: 10,
    concept_ids: conceptIds,
    title_pending: false,
    ...extras,
  };
}

function questionResponse(): QuestionResponse {
  return {
    question_number: 1,
    question_id: 'what_is_a_set-recall-01',
    concept_id: 'what_is_a_set',
    concept_label: 'What is a Set',
    concept: 'What is a Set',
    question_type: 'recall',
    intended_difficulty: 0.2,
    question_text: 'Define a set.',
  };
}

function renderStudy(initialPath = '/study') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <ActiveDomainProvider>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/study" element={<Study />} />
            <Route path="/sessions/:id" element={<div>Transcript sess</div>} />
          </Route>
        </Routes>
      </ActiveDomainProvider>
    </MemoryRouter>,
  );
}

async function openChatConfig() {
  renderStudy();
  await waitFor(() => expect(screen.getByText('Chat Mode')).toBeInTheDocument());
  await userEvent.click(screen.getByRole('button', { name: /Chat Mode/i }));
  await waitFor(() => expect(screen.getByText('Concepts')).toBeInTheDocument());
}

async function startActiveSession() {
  await openChatConfig();
  await waitFor(() => expect(screen.getByLabelText(/What is a Set/i)).toBeChecked());
  await userEvent.click(screen.getByRole('button', { name: 'Start' }));
  await waitFor(() => {
    expect(screen.getByText('Define a set.')).toBeInTheDocument();
  });
}

beforeEach(() => {
  getKnowledgeCatalog.mockReset();
  getWikiPreview.mockReset();
  getQuestionBank.mockReset();
  getLearnerMastery.mockReset().mockResolvedValue({
    knowledge_source: 'domain:discrete-math/01-set-theory',
    params: { p_L0: 0, p_T: 0.1, p_G: 0.2, p_S: 0.1, p_F: 0 },
    concepts: {
      what_is_a_set: {
        p_mastery: 0.82,
        band: 'proficient',
        n_observed: 7,
        display_pct: 82,
      },
      set_operations: {
        p_mastery: null,
        band: 'new',
        n_observed: 0,
        display_pct: null,
      },
      empty_topic: {
        p_mastery: null,
        band: 'new',
        n_observed: 0,
        display_pct: null,
      },
    },
  });
  createSession.mockReset();
  fetchQuestion.mockReset();
  getSessionState.mockReset();
  postTurn.mockReset();
  listSessions.mockReset().mockResolvedValue({ sessions: [] });
  endSession.mockReset();
  setStoredKnowledgeSource.mockReset();
  localStorage.clear();

  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });

  getKnowledgeCatalog.mockResolvedValue(catalogFixture());
  getWikiPreview.mockResolvedValue(wikiPreview());
  getQuestionBank.mockResolvedValue(bankResponse());
  createSession.mockResolvedValue(sessionResponse(['what_is_a_set', 'set_operations']));
  fetchQuestion.mockResolvedValue(questionResponse());
  endSession.mockResolvedValue({
    session_id: 'sess-1',
    status: 'ended_early',
    ended_at: '2026-01-01T01:00:00Z',
    title: '01 Set Theory — Adaptive Practice',
    knowledge_source: 'domain:discrete-math/01-set-theory',
    question_count: 0,
    max_questions: 10,
    scalar: 0.5,
  });
});

describe('Study concept selection', () => {
  it('loads compiled concepts and selects those with questions by default', async () => {
    await openChatConfig();

    await waitFor(() => {
      expect(screen.getByLabelText(/What is a Set/i)).toBeChecked();
      expect(screen.getByLabelText(/Set Operations/i)).toBeChecked();
    });
    expect(screen.getByLabelText(/Empty Topic/i)).toBeDisabled();
    expect(screen.getByLabelText(/Empty Topic/i)).not.toBeChecked();
    expect(screen.getByText('82%')).toBeInTheDocument();
    expect(screen.getAllByText('New').length).toBeGreaterThanOrEqual(1);
  });

  it('soft-degrades when mastery endpoint fails', async () => {
    getLearnerMastery.mockRejectedValueOnce(new Error('mastery unavailable'));
    await openChatConfig();

    await waitFor(() => {
      expect(screen.getByLabelText(/What is a Set/i)).toBeChecked();
    });
    expect(screen.queryByText('82%')).not.toBeInTheDocument();
    expect(screen.queryByText('New')).not.toBeInTheDocument();
    expect(screen.getAllByText('1 questions').length).toBeGreaterThanOrEqual(1);
  });

  it('prevents deselecting the last concept', async () => {
    await openChatConfig();
    await waitFor(() => expect(screen.getByLabelText(/What is a Set/i)).toBeChecked());

    await userEvent.click(screen.getByLabelText(/Set Operations/i));
    expect(screen.getByLabelText(/Set Operations/i)).not.toBeChecked();

    await userEvent.click(screen.getByLabelText(/What is a Set/i));
    expect(screen.getByLabelText(/What is a Set/i)).toBeChecked();
  });

  it('restores all selectable concepts with Select all', async () => {
    await openChatConfig();
    await waitFor(() => expect(screen.getByLabelText(/What is a Set/i)).toBeChecked());

    await userEvent.click(screen.getByLabelText(/Set Operations/i));
    expect(screen.getByLabelText(/Set Operations/i)).not.toBeChecked();

    await userEvent.click(screen.getByRole('button', { name: 'Select all' }));
    expect(screen.getByLabelText(/What is a Set/i)).toBeChecked();
    expect(screen.getByLabelText(/Set Operations/i)).toBeChecked();
  });

  it('starts a session with selected concept ids and skips the pre-question state fetch', async () => {
    await openChatConfig();
    await waitFor(() => expect(screen.getByLabelText(/What is a Set/i)).toBeChecked());

    await userEvent.click(screen.getByLabelText(/Set Operations/i));
    await userEvent.click(screen.getByRole('button', { name: 'Start' }));

    await waitFor(() => expect(createSession).toHaveBeenCalled());
    expect(createSession).toHaveBeenCalledWith({
      knowledge_source: 'domain:discrete-math/01-set-theory',
      focus_mode: 'adaptive',
      max_questions: 10,
      concept_ids: ['what_is_a_set'],
    });
    expect(fetchQuestion).toHaveBeenCalledWith('sess-1', {});
    expect(getSessionState).not.toHaveBeenCalled();
    await waitFor(() => expect(listSessions).toHaveBeenCalledTimes(2));

    await waitFor(() => {
      expect(screen.getByText('Define a set.')).toBeInTheDocument();
    });
  });

  it('polls session state and swaps the title when title_pending is true', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    createSession.mockResolvedValue(
      sessionResponse(['what_is_a_set', 'set_operations'], {
        title_pending: true,
        title: '01 Set Theory — Adaptive Practice',
      }),
    );
    getSessionState
      .mockResolvedValueOnce({
        session_id: 'sess-1',
        title: '01 Set Theory — Adaptive Practice',
        scalar: 0.5,
        question_count: 1,
        mastery: {},
        knowledge_source: 'domain:discrete-math/01-set-theory',
        focus_mode: 'adaptive',
        max_questions: 10,
        questions_remaining: 9,
        concept_ids: ['what_is_a_set', 'set_operations'],
        title_pending: true,
      })
      .mockResolvedValue({
        session_id: 'sess-1',
        title: 'Sets Foundations Drill',
        scalar: 0.5,
        question_count: 1,
        mastery: {},
        knowledge_source: 'domain:discrete-math/01-set-theory',
        focus_mode: 'adaptive',
        max_questions: 10,
        questions_remaining: 9,
        concept_ids: ['what_is_a_set', 'set_operations'],
        title_pending: false,
      });

    await openChatConfig();
    await waitFor(() => expect(screen.getByLabelText(/What is a Set/i)).toBeChecked());
    await userEvent.click(screen.getByRole('button', { name: 'Start' }));

    await waitFor(() => {
      expect(screen.getByText(/01 Set Theory — Adaptive Practice/)).toBeInTheDocument();
    });

    await waitFor(() => expect(getSessionState).toHaveBeenCalled());
    await vi.advanceTimersByTimeAsync(1600);

    await waitFor(() => {
      expect(screen.getByText(/Sets Foundations Drill/)).toBeInTheDocument();
    });

    vi.useRealTimers();
  });
});

describe('Study focused exit', () => {
  it('hides global nav during an active session and shows Exit session', async () => {
    renderStudy();
    await waitFor(() => expect(screen.getByText('Chat Mode')).toBeInTheDocument());
    expect(screen.getByRole('navigation', { name: 'Main navigation' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Open navigation/i })).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /Chat Mode/i }));
    await waitFor(() => expect(screen.getByText('Concepts')).toBeInTheDocument());
    await userEvent.click(screen.getByRole('button', { name: 'Start' }));
    await waitFor(() => expect(screen.getByText('Define a set.')).toBeInTheDocument());

    expect(screen.queryByRole('navigation', { name: 'Main navigation' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Open navigation/i })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Exit session' })).toBeInTheDocument();
  });

  it('cancels exit confirmation and keeps the session', async () => {
    await startActiveSession();
    await userEvent.click(screen.getByRole('button', { name: 'Exit session' }));

    const dialog = screen.getByRole('dialog', { name: /End this session/i });
    expect(dialog).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Continue studying' }));

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(endSession).not.toHaveBeenCalled();
    expect(screen.getByText('Define a set.')).toBeInTheDocument();
  });

  it('ends the session and navigates to the transcript', async () => {
    const listCallsBefore = () => listSessions.mock.calls.length;
    await startActiveSession();
    const callsAtStart = listCallsBefore();

    await userEvent.click(screen.getByRole('button', { name: 'Exit session' }));
    await userEvent.click(screen.getByRole('button', { name: 'End session' }));

    await waitFor(() => expect(endSession).toHaveBeenCalledWith('sess-1'));
    await waitFor(() => expect(listSessions.mock.calls.length).toBeGreaterThan(callsAtStart));
    await waitFor(() => expect(screen.getByText('Transcript sess')).toBeInTheDocument());
  });

  it('keeps the learner in-session when endSession fails', async () => {
    endSession.mockRejectedValueOnce(new Error('Network down'));
    await startActiveSession();

    await userEvent.click(screen.getByRole('button', { name: 'Exit session' }));
    await userEvent.click(screen.getByRole('button', { name: 'End session' }));

    await waitFor(() => expect(screen.getByText('Network down')).toBeInTheDocument());
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('Define a set.')).toBeInTheDocument();
  });
});

describe('Study tutor mode', () => {
  it('shows a tutor-mode badge after a help turn and labels assisted correct', async () => {
    postTurn
      .mockResolvedValueOnce({
        phase: 'dialogue',
        question_number: 1,
        tutor_message: "Tutor mode — let's work through this together.\n\nThink about distinct elements.",
        question_closed: false,
        mode: 'tutor',
        correct: 'no',
        hint_count: 0,
        turn_count: 0,
        hedging_count: 0,
        inconsistency_flag: false,
      })
      .mockResolvedValueOnce({
        phase: 'graded',
        question_number: 1,
        tutor_message: null,
        question_closed: true,
        mode: 'tutor',
        correct: 'yes',
        hint_count: 1,
        turn_count: 2,
        hedging_count: 0,
        inconsistency_flag: false,
        assisted: true,
      });

    await startActiveSession();

    await userEvent.type(screen.getByLabelText('Your message'), 'I need help');
    await userEvent.click(screen.getByRole('button', { name: 'Send message' }));

    await waitFor(
      () => {
        expect(screen.getByText('Tutor mode')).toBeInTheDocument();
      },
      { timeout: 5000 },
    );

    await waitFor(() => {
      expect(screen.getByLabelText('Your message')).not.toBeDisabled();
    });

    await userEvent.type(screen.getByLabelText('Your message'), 'distinct elements');
    await userEvent.click(screen.getByRole('button', { name: 'Send message' }));

    await waitFor(() => {
      expect(screen.getByText('✓ Correct (with tutor help)')).toBeInTheDocument();
    });
    expect(screen.queryByText('Tutor mode')).not.toBeInTheDocument();
  });
});

describe('Study mastery delta', () => {
  const masteryDelta = {
    what_is_a_set: {
      band_before: 'struggling' as const,
      band_after: 'learning' as const,
      pct_before: 34,
      pct_after: 61,
      n_observed_session: 1,
    },
  };

  function stateWithDelta(overrides: Record<string, unknown> = {}) {
    return {
      session_id: 'sess-1',
      title: '01 Set Theory — Adaptive Practice',
      scalar: 0.52,
      question_count: 1,
      mastery: { what_is_a_set: 0.61 },
      mastery_delta: masteryDelta,
      knowledge_source: 'domain:discrete-math/01-set-theory',
      focus_mode: 'adaptive',
      max_questions: 1,
      questions_remaining: 0,
      concept_ids: ['what_is_a_set', 'set_operations'],
      title_pending: false,
      ...overrides,
    };
  }

  async function answerGradeAndRate() {
    postTurn
      .mockResolvedValueOnce({
        phase: 'graded',
        question_number: 1,
        correct: 'yes',
        hint_count: 0,
        turn_count: 1,
        hedging_count: 0,
        inconsistency_flag: false,
        tutor_message: null,
      })
      .mockResolvedValueOnce({
        phase: 'reflection',
        question_number: 1,
        correct: 'yes',
        hint_count: 0,
        turn_count: 1,
        hedging_count: 0,
        explicit_rating: 'ok',
        reward: 0.2,
        new_difficulty: 0.52,
        inconsistency_flag: false,
      });

    getSessionState.mockResolvedValue(stateWithDelta());

    await startActiveSession();

    await userEvent.type(screen.getByLabelText('Your message'), 'a collection of objects');
    await userEvent.click(screen.getByRole('button', { name: 'Send message' }));

    await waitFor(() => {
      expect(screen.getByText('How difficult was this question?')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Ok' })).toBeEnabled();
    });
    await userEvent.click(screen.getByRole('button', { name: 'Ok' }));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Submit rating' })).toBeEnabled();
    });
    await userEvent.click(screen.getByRole('button', { name: 'Submit rating' }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Next question' })).toBeInTheDocument();
    });
  }

  it('shows live band movement for the current concept after rating', async () => {
    await answerGradeAndRate();

    const live = screen.getByRole('region', { name: 'Concept mastery movement' });
    expect(within(live).getByText('What is a Set')).toBeInTheDocument();
    expect(within(live).getByText('struggling')).toBeInTheDocument();
    expect(within(live).getByText('learning')).toBeInTheDocument();
    expect(within(live).getByText('34%')).toBeInTheDocument();
    expect(within(live).getByText('61%')).toBeInTheDocument();
  });

  it('shows a recap on session complete and collapses to a compact line', async () => {
    createSession.mockResolvedValue(
      sessionResponse(['what_is_a_set'], { max_questions: 1 }),
    );
    await answerGradeAndRate();

    postTurn.mockResolvedValueOnce({
      phase: 'session_complete',
      question_number: 1,
      correct: 'yes',
      hint_count: 0,
      turn_count: 1,
      hedging_count: 0,
      explicit_rating: 'ok',
      reward: 0.2,
      new_difficulty: 0.52,
      inconsistency_flag: false,
    });

    await userEvent.click(screen.getByRole('button', { name: 'Next question' }));

    await waitFor(() => {
      expect(screen.getByText('Session complete')).toBeInTheDocument();
    });
    expect(screen.getByText('Concepts practiced')).toBeInTheDocument();
    expect(screen.getByText('struggling')).toBeInTheDocument();
    expect(screen.getByText('learning')).toBeInTheDocument();
    expect(screen.queryByText(/Final difficulty/i)).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Close summary' }));
    expect(screen.getByText('1 concept moved')).toBeInTheDocument();
  });
});
