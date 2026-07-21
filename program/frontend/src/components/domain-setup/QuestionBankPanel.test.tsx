import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import type {
  QuestionBankResponse,
  QuestionBankGenerateStatus,
  WikiPreview,
} from '../../api/types';

const getQuestionBank = vi.fn();
const getWikiPreview = vi.fn();
const getQuestionBankGenerateStatus = vi.fn();

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client');
  return {
    ...actual,
    getQuestionBank: (...a: unknown[]) => getQuestionBank(...a),
    getWikiPreview: (...a: unknown[]) => getWikiPreview(...a),
    getQuestionBankGenerateStatus: (...a: unknown[]) => getQuestionBankGenerateStatus(...a),
  };
});

import { QuestionBankPanel } from './QuestionBankPanel';

function bank(): QuestionBankResponse {
  return {
    version: 1,
    path: 'question-bank.json',
    questions: [
      { id: 'beta-1', concept_id: 'beta', type: 'recall', intended_difficulty: 0.25, text: 'q' },
      { id: 'alpha-1', concept_id: 'alpha', type: 'recall', intended_difficulty: 0.25, text: 'q' },
    ],
  };
}

function idleStatus(): QuestionBankGenerateStatus {
  return {
    status: 'idle',
    concepts_total: 0,
    concepts_done: 0,
    questions: null,
    concepts: null,
    path: null,
    error: null,
    started_at: null,
  };
}

function wiki(): WikiPreview {
  // Teaching order (order field) puts alpha before beta even though beta has lower depth.
  return {
    source: 'published',
    version: 1,
    edges: [],
    pages: [
      { concept_id: 'alpha', label: 'Alpha', depth: 5, order: 0, body: '' },
      { concept_id: 'beta', label: 'Beta', depth: 0, order: 1, body: '' },
    ],
  };
}

beforeEach(() => {
  getQuestionBank.mockReset();
  getWikiPreview.mockReset();
  getQuestionBankGenerateStatus.mockReset();
});

describe('QuestionBankPanel', () => {
  it('orders concept groups by teaching order, not depth', async () => {
    getQuestionBank.mockResolvedValue(bank());
    getWikiPreview.mockResolvedValue(wiki());
    getQuestionBankGenerateStatus.mockResolvedValue(idleStatus());

    const { container } = render(
      <QuestionBankPanel knowledgeSource="domain:x/y" canGenerate generateBlockedReason={null} />,
    );

    await waitFor(() => expect(screen.getByText('Alpha')).toBeInTheDocument());

    const labels = Array.from(container.querySelectorAll('.wb-wiki__page-label')).map(
      (el) => el.textContent,
    );
    expect(labels).toEqual(['Alpha', 'Beta']);
  });
});
