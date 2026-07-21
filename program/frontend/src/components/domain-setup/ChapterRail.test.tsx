import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { KnowledgeCatalog, KnowledgeChapter, KnowledgeDomain } from '../../api/types';

const createChapter = vi.fn();
const renameChapter = vi.fn();
const deleteChapter = vi.fn();
const refreshCatalog = vi.fn();
const setActiveChapterId = vi.fn();

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client');
  return {
    ...actual,
    createChapter: (...args: unknown[]) => createChapter(...args),
    renameChapter: (...args: unknown[]) => renameChapter(...args),
    deleteChapter: (...args: unknown[]) => deleteChapter(...args),
  };
});

vi.mock('../../shell/ActiveDomainContext', () => ({
  useActiveDomain: () => mockActiveDomain,
}));

import { ChapterRail } from './ChapterRail';

function chapter(id: string, domainId = 'alpha'): KnowledgeChapter {
  return {
    id,
    knowledge_source: `domain:${domainId}/${id}`,
    sources_present: false,
    source_count: 0,
    source_files: [],
    has_concept_graph: false,
    wiki_count: 0,
    has_question_bank: false,
    question_bank_count: 0,
    compile_stage: 'idle',
    is_approved: false,
    is_stale: false,
    has_unapproved_compile: false,
  };
}

function domain(chapters: KnowledgeChapter[]): KnowledgeDomain {
  return { id: 'alpha', chapters };
}

let mockActiveDomain: {
  activeDomain: KnowledgeDomain | null;
  activeChapterId: string | null;
  setActiveChapterId: typeof setActiveChapterId;
  refreshCatalog: typeof refreshCatalog;
  catalog: KnowledgeCatalog | null;
};

beforeEach(() => {
  createChapter.mockReset();
  renameChapter.mockReset();
  deleteChapter.mockReset();
  refreshCatalog.mockReset().mockResolvedValue(undefined);
  setActiveChapterId.mockReset();
  mockActiveDomain = {
    activeDomain: domain([chapter('ch1'), chapter('ch2')]),
    activeChapterId: 'ch1',
    setActiveChapterId,
    refreshCatalog,
    catalog: null,
  };
});

describe('ChapterRail', () => {
  it('renames a chapter and selects the new id after catalog refresh', async () => {
    renameChapter.mockResolvedValue({
      chapter_id: 'ch1-renamed',
      knowledge_source: 'domain:alpha/ch1-renamed',
    });
    render(<ChapterRail />);

    await userEvent.click(screen.getByRole('button', { name: 'Rename chapter ch1' }));
    const input = screen.getByRole('textbox', { name: 'Rename chapter ch1' });
    await userEvent.clear(input);
    await userEvent.type(input, 'ch1-renamed');
    await userEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(renameChapter).toHaveBeenCalledWith('alpha', 'ch1', 'ch1-renamed');
    });
    expect(refreshCatalog).toHaveBeenCalled();
    expect(setActiveChapterId).toHaveBeenCalledWith('ch1-renamed');
  });

  it('surfaces duplicate rename errors without clearing selection', async () => {
    renameChapter.mockRejectedValue(new Error('A chapter with this name already exists.'));
    render(<ChapterRail />);

    await userEvent.click(screen.getByRole('button', { name: 'Rename chapter ch1' }));
    const input = screen.getByRole('textbox', { name: 'Rename chapter ch1' });
    await userEvent.clear(input);
    await userEvent.type(input, 'ch2');
    await userEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByText('A chapter with this name already exists.')).toBeInTheDocument();
    expect(setActiveChapterId).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Save' })).toBeInTheDocument();
  });

  it('warns about downstream deletion and can cancel', async () => {
    render(<ChapterRail />);

    await userEvent.click(screen.getByRole('button', { name: 'Delete chapter ch1' }));
    expect(screen.getByRole('dialog', { name: 'Delete chapter?' })).toBeInTheDocument();
    expect(screen.getByText(/sources/i)).toBeInTheDocument();
    expect(screen.getByText(/compiled wiki/i)).toBeInTheDocument();
    expect(screen.getByText(/question bank/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('dialog', { name: 'Delete chapter?' })).not.toBeInTheDocument();
    expect(deleteChapter).not.toHaveBeenCalled();
  });

  it('deletes a chapter and refreshes the catalog', async () => {
    deleteChapter.mockResolvedValue({ deleted: true });
    render(<ChapterRail />);

    await userEvent.click(screen.getByRole('button', { name: 'Delete chapter ch2' }));
    await userEvent.click(screen.getByRole('button', { name: 'Delete chapter' }));

    await waitFor(() => {
      expect(deleteChapter).toHaveBeenCalledWith('alpha', 'ch2');
    });
    expect(refreshCatalog).toHaveBeenCalled();
  });
});
