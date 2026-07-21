import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../api/client', () => ({
  uploadSource: vi.fn(() => new Promise(() => {})), // never resolves: keep pending
  addUrlSource: vi.fn(),
}));

import {
  enqueueFiles,
  getPending,
  hasInFlight,
  resetSourceUploadStoreForTests,
  subscribe,
} from './sourceUploadStore';

const KS_A = 'domain:demo/chapter-a';
const KS_B = 'domain:demo/chapter-b';

function fakeFile(name: string): File {
  return new File(['x'], name, { type: 'text/plain' });
}

describe('sourceUploadStore', () => {
  beforeEach(() => {
    resetSourceUploadStoreForTests();
  });

  afterEach(() => {
    resetSourceUploadStoreForTests();
  });

  it('scopes pending rows by knowledgeSource', async () => {
    enqueueFiles(KS_A, [fakeFile('a.md')]);
    enqueueFiles(KS_B, [fakeFile('b.md')]);

    // Allow microtask pump to mark uploading
    await Promise.resolve();
    await Promise.resolve();

    const pendingA = getPending(KS_A);
    const pendingB = getPending(KS_B);

    expect(pendingA).toHaveLength(1);
    expect(pendingA[0].name).toBe('a.md');
    expect(pendingA[0].knowledgeSource).toBe(KS_A);

    expect(pendingB).toHaveLength(1);
    expect(pendingB[0].name).toBe('b.md');
    expect(pendingB[0].knowledgeSource).toBe(KS_B);

    expect(hasInFlight(KS_A)).toBe(true);
    expect(hasInFlight(KS_B)).toBe(true);
  });

  it('notifies only subscribers of that knowledgeSource', async () => {
    const onA = vi.fn();
    const onB = vi.fn();
    const unsubA = subscribe(KS_A, onA);
    const unsubB = subscribe(KS_B, onB);

    enqueueFiles(KS_A, [fakeFile('only-a.md')]);
    await Promise.resolve();

    expect(onA).toHaveBeenCalled();
    expect(onB).not.toHaveBeenCalled();
    expect(getPending(KS_B)).toHaveLength(0);

    unsubA();
    unsubB();
  });
});
