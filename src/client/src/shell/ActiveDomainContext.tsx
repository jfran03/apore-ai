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
import type { KnowledgeCatalog, KnowledgeDomain } from '../api/types';

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
  activeDomainId: string | null;
  activeDomain: KnowledgeDomain | null;
  setActiveDomainId: (domainId: string) => void;
}

const ActiveDomainContext = createContext<ActiveDomainValue | null>(null);

export function ActiveDomainProvider({ children }: { children: ReactNode }) {
  const [catalog, setCatalog] = useState<KnowledgeCatalog | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [activeDomainId, setActiveDomainIdState] = useState<string | null>(
    () => parseKnowledgeSource(getStoredKnowledgeSource())?.domainId ?? null,
  );

  useEffect(() => {
    getKnowledgeCatalog()
      .then(setCatalog)
      .catch((err) =>
        setCatalogError(err instanceof Error ? err.message : 'Failed to load catalog'),
      );
  }, []);

  // Fall back to the first catalog domain when the stored one no longer exists.
  useEffect(() => {
    if (!catalog?.domains.length) return;
    if (!activeDomainId || !catalog.domains.some((d) => d.id === activeDomainId)) {
      setActiveDomainIdState(catalog.domains[0].id);
    }
  }, [catalog, activeDomainId]);

  const setActiveDomainId = useCallback(
    (domainId: string) => {
      setActiveDomainIdState(domainId);
      const firstChapter = catalog?.domains.find((d) => d.id === domainId)?.chapters[0];
      if (firstChapter) {
        setStoredKnowledgeSource(firstChapter.knowledge_source);
      }
    },
    [catalog],
  );

  const activeDomain = catalog?.domains.find((d) => d.id === activeDomainId) ?? null;

  const value = useMemo<ActiveDomainValue>(
    () => ({ catalog, catalogError, activeDomainId, activeDomain, setActiveDomainId }),
    [catalog, catalogError, activeDomainId, activeDomain, setActiveDomainId],
  );

  return <ActiveDomainContext.Provider value={value}>{children}</ActiveDomainContext.Provider>;
}

export function useActiveDomain(): ActiveDomainValue {
  const ctx = useContext(ActiveDomainContext);
  if (!ctx) throw new Error('useActiveDomain must be used within ActiveDomainProvider');
  return ctx;
}
