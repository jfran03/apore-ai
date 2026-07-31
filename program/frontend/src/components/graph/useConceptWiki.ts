import { useEffect, useState } from 'react';
import { getWikiPreview } from '../../api/client';
import type { WikiPreview } from '../../api/types';

/** Per-chapter published-wiki cache; a concept click should not refetch a
 *  chapter already loaded during this page visit. */
const wikiCache = new Map<string, Promise<WikiPreview>>();

function loadPublishedWiki(knowledgeSource: string): Promise<WikiPreview> {
  const cached = wikiCache.get(knowledgeSource);
  if (cached) return cached;
  const pending = getWikiPreview('published', knowledgeSource);
  wikiCache.set(knowledgeSource, pending);
  pending.catch(() => wikiCache.delete(knowledgeSource));
  return pending;
}

export type ConceptWikiState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'ready'; body: string }
  | { status: 'missing' }
  | { status: 'error'; message: string };

/** Load published wiki for a concept when `enabled` (typically node selected). */
export function useConceptWiki(
  conceptId: string,
  knowledgeSource: string,
  hasWiki: boolean,
  enabled: boolean,
): ConceptWikiState {
  const [wiki, setWiki] = useState<ConceptWikiState>({ status: 'idle' });

  useEffect(() => {
    if (!enabled) {
      setWiki({ status: 'idle' });
      return;
    }
    if (!hasWiki) {
      setWiki({ status: 'missing' });
      return;
    }
    let active = true;
    setWiki({ status: 'loading' });
    loadPublishedWiki(knowledgeSource)
      .then((preview) => {
        if (!active) return;
        const page = preview.pages.find((p) => p.concept_id === conceptId);
        setWiki(page ? { status: 'ready', body: page.body } : { status: 'missing' });
      })
      .catch((err: unknown) => {
        if (!active) return;
        setWiki({
          status: 'error',
          message: err instanceof Error ? err.message : 'Failed to load wiki',
        });
      });
    return () => {
      active = false;
    };
  }, [enabled, conceptId, knowledgeSource, hasWiki]);

  return wiki;
}
