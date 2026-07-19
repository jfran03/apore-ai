import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import {
  getKnowledgeCatalog,
  getStoredKnowledgeSource,
  setStoredKnowledgeSource,
} from '../api/client';
import type { KnowledgeCatalog, KnowledgeChapter, KnowledgeDomain } from '../api/types';

export function parseKnowledgeSource(
  source: string,
): { domainId: string; chapterId: string } | null {
  if (!source.startsWith('domain:')) return null;
  const rest = source.slice('domain:'.length);
  const [domainId, chapterId] = rest.split('/', 2);
  if (!domainId || !chapterId) return null;
  return { domainId, chapterId };
}

interface ActiveDomainValue {
  catalog: KnowledgeCatalog | null;
  catalogError: string | null;
  catalogLoading: boolean;
  activeDomainId: string | null;
  activeDomain: KnowledgeDomain | null;
  activeChapterId: string | null;
  activeChapter: KnowledgeChapter | null;
  setActiveDomainId: (domainId: string) => void;
  setActiveChapterId: (chapterId: string) => void;
  refreshCatalog: () => Promise<void>;
}

const ActiveDomainContext = createContext<ActiveDomainValue | null>(null);

export function ActiveDomainProvider({ children }: { children: ReactNode }) {
  const [catalog, setCatalog] = useState<KnowledgeCatalog | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const storedSource = parseKnowledgeSource(getStoredKnowledgeSource());
  const [activeDomainId, setActiveDomainIdState] = useState<string | null>(
    () => storedSource?.domainId ?? null,
  );
  const [activeChapterId, setActiveChapterIdState] = useState<string | null>(
    () => storedSource?.chapterId ?? null,
  );

  const refreshCatalog = useCallback(async () => {
    try {
      const data = await getKnowledgeCatalog();
      setCatalog(data);
      setCatalogError(null);
    } catch (err) {
      setCatalogError(err instanceof Error ? err.message : 'Failed to load catalog');
      throw err;
    } finally {
      setCatalogLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshCatalog().catch(() => {
      /* error surfaced via catalogError */
    });
  }, [refreshCatalog]);

  // Reconcile the active domain/chapter against the catalog. Only corrects
  // selections that no longer exist; explicit user choices are preserved.
  useEffect(() => {
    if (!catalog?.domains.length) return;
    const domain =
      catalog.domains.find((d) => d.id === activeDomainId) ?? catalog.domains[0];
    const chapter =
      domain.chapters.find((c) => c.id === activeChapterId) ?? domain.chapters[0] ?? null;

    if (domain.id !== activeDomainId) setActiveDomainIdState(domain.id);
    if ((chapter?.id ?? null) !== activeChapterId) {
      setActiveChapterIdState(chapter?.id ?? null);
    }
    if (chapter) setStoredKnowledgeSource(chapter.knowledge_source);
  }, [catalog, activeDomainId, activeChapterId]);

  const setActiveDomainId = useCallback(
    (domainId: string) => {
      setActiveDomainIdState(domainId);
      const firstChapter = catalog?.domains.find((d) => d.id === domainId)?.chapters[0];
      setActiveChapterIdState(firstChapter?.id ?? null);
      if (firstChapter) setStoredKnowledgeSource(firstChapter.knowledge_source);
    },
    [catalog],
  );

  const setActiveChapterId = useCallback(
    (chapterId: string) => {
      setActiveChapterIdState(chapterId);
      const chapter = catalog?.domains
        .find((d) => d.id === activeDomainId)
        ?.chapters.find((c) => c.id === chapterId);
      if (chapter) setStoredKnowledgeSource(chapter.knowledge_source);
    },
    [catalog, activeDomainId],
  );

  const activeDomain = catalog?.domains.find((d) => d.id === activeDomainId) ?? null;
  const activeChapter =
    activeDomain?.chapters.find((c) => c.id === activeChapterId) ?? null;

  const value = useMemo<ActiveDomainValue>(
    () => ({
      catalog,
      catalogError,
      catalogLoading,
      activeDomainId,
      activeDomain,
      activeChapterId,
      activeChapter,
      setActiveDomainId,
      setActiveChapterId,
      refreshCatalog,
    }),
    [
      catalog,
      catalogError,
      catalogLoading,
      activeDomainId,
      activeDomain,
      activeChapterId,
      activeChapter,
      setActiveDomainId,
      setActiveChapterId,
      refreshCatalog,
    ],
  );

  return <ActiveDomainContext.Provider value={value}>{children}</ActiveDomainContext.Provider>;
}

export function useActiveDomain(): ActiveDomainValue {
  const ctx = useContext(ActiveDomainContext);
  if (!ctx) throw new Error('useActiveDomain must be used within ActiveDomainProvider');
  return ctx;
}
