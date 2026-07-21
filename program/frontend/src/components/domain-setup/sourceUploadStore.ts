/**
 * Module-level, chapter-scoped source upload queue.
 *
 * Pending rows are keyed by knowledgeSource so uploads survive SourcesPanel
 * unmount (tab switch) and never bleed into another chapter's UI.
 */

import { addUrlSource, uploadSource } from '../../api/client';
import { parseKnowledgeSource } from '../../shell/ActiveDomainContext';

export type PendingStatus = 'queued' | 'uploading' | 'failed';

export interface PendingUpload {
  knowledgeSource: string;
  localId: string;
  kind: 'file' | 'url';
  name: string;
  size: number | null;
  status: PendingStatus;
  error?: string;
  file?: File;
  url?: string;
}

export type SettledListener = (knowledgeSource: string) => void;

const UPLOAD_CONCURRENCY = 3;

const pendingBySource = new Map<string, PendingUpload[]>();
const listenersBySource = new Map<string, Set<() => void>>();
const settledListeners = new Set<SettledListener>();

function newLocalId(): string {
  return `pending-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function listFor(knowledgeSource: string): PendingUpload[] {
  return pendingBySource.get(knowledgeSource) ?? [];
}

function setList(knowledgeSource: string, next: PendingUpload[]): void {
  if (next.length === 0) {
    pendingBySource.delete(knowledgeSource);
  } else {
    pendingBySource.set(knowledgeSource, next);
  }
  const listeners = listenersBySource.get(knowledgeSource);
  if (listeners) {
    for (const listener of listeners) listener();
  }
}

function notifySettled(knowledgeSource: string): void {
  for (const listener of settledListeners) {
    listener(knowledgeSource);
  }
}

function patchItem(
  knowledgeSource: string,
  localId: string,
  patch: Partial<PendingUpload>,
): void {
  const list = listFor(knowledgeSource);
  const next = list.map((item) =>
    item.localId === localId ? { ...item, ...patch } : item,
  );
  setList(knowledgeSource, next);
}

function removeItem(knowledgeSource: string, localId: string): void {
  setList(
    knowledgeSource,
    listFor(knowledgeSource).filter((item) => item.localId !== localId),
  );
}

async function runUpload(item: PendingUpload): Promise<void> {
  const parsed = parseKnowledgeSource(item.knowledgeSource);
  if (!parsed) {
    throw new Error('Invalid knowledge source');
  }

  if (item.kind === 'file' && item.file) {
    await uploadSource(parsed.domainId, parsed.chapterId, item.file);
    return;
  }
  if (item.kind === 'url' && item.url) {
    const entry = await addUrlSource(item.url, item.knowledgeSource);
    if (entry.normalize_status === 'failed') {
      throw new Error(entry.normalize_error ?? 'The URL could not be converted.');
    }
    return;
  }
  throw new Error('Invalid pending upload');
}

function kickPump(knowledgeSource: string): void {
  const list = listFor(knowledgeSource);
  const uploadingCount = list.filter((p) => p.status === 'uploading').length;
  const slots = UPLOAD_CONCURRENCY - uploadingCount;
  if (slots <= 0) return;

  const toStart = list.filter((p) => p.status === 'queued').slice(0, slots);
  for (const item of toStart) {
    patchItem(item.knowledgeSource, item.localId, {
      status: 'uploading',
      error: undefined,
    });
    void (async () => {
      try {
        await runUpload(item);
        removeItem(item.knowledgeSource, item.localId);
        notifySettled(item.knowledgeSource);
      } catch (err) {
        patchItem(item.knowledgeSource, item.localId, {
          status: 'failed',
          error: err instanceof Error ? err.message : 'Upload failed',
        });
      } finally {
        kickPump(item.knowledgeSource);
      }
    })();
  }
}

export function getPending(knowledgeSource: string): PendingUpload[] {
  return listFor(knowledgeSource);
}

export function hasInFlight(knowledgeSource: string): boolean {
  return listFor(knowledgeSource).some(
    (p) => p.status === 'queued' || p.status === 'uploading',
  );
}

export function subscribe(
  knowledgeSource: string,
  listener: () => void,
): () => void {
  let set = listenersBySource.get(knowledgeSource);
  if (!set) {
    set = new Set();
    listenersBySource.set(knowledgeSource, set);
  }
  set.add(listener);
  return () => {
    set!.delete(listener);
    if (set!.size === 0) {
      listenersBySource.delete(knowledgeSource);
    }
  };
}

export function subscribeSettled(listener: SettledListener): () => void {
  settledListeners.add(listener);
  return () => {
    settledListeners.delete(listener);
  };
}

export function enqueueFiles(knowledgeSource: string, files: File[]): void {
  if (!files.length) return;
  if (!parseKnowledgeSource(knowledgeSource)) return;

  const items: PendingUpload[] = files.map((file) => ({
    knowledgeSource,
    localId: newLocalId(),
    kind: 'file' as const,
    name: file.name,
    size: file.size,
    status: 'queued' as const,
    file,
  }));
  setList(knowledgeSource, [...listFor(knowledgeSource), ...items]);
  queueMicrotask(() => kickPump(knowledgeSource));
}

export function enqueueUrl(knowledgeSource: string, url: string): void {
  const trimmed = url.trim();
  if (!trimmed) return;
  if (!parseKnowledgeSource(knowledgeSource)) return;

  const item: PendingUpload = {
    knowledgeSource,
    localId: newLocalId(),
    kind: 'url',
    name: trimmed,
    size: null,
    status: 'queued',
    url: trimmed,
  };
  setList(knowledgeSource, [...listFor(knowledgeSource), item]);
  queueMicrotask(() => kickPump(knowledgeSource));
}

export function dismiss(knowledgeSource: string, localId: string): void {
  removeItem(knowledgeSource, localId);
}

/** Test helper: clear all pending state. */
export function resetSourceUploadStoreForTests(): void {
  pendingBySource.clear();
  listenersBySource.clear();
  settledListeners.clear();
}
