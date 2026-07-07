import { useCallback, useEffect, useState } from 'react';
import { listDomainSessions } from '../api/client';
import type { WorkspaceSessionSummary } from '../api/types';

export interface DomainSessionsState {
  sessions: WorkspaceSessionSummary[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

export function useDomainSessions(domainId: string | null): DomainSessionsState {
  const [sessions, setSessions] = useState<WorkspaceSessionSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const refresh = useCallback(() => setTick((v) => v + 1), []);

  useEffect(() => {
    if (!domainId) {
      setSessions([]);
      setLoading(false);
      setError(null);
      return;
    }
    let cancelled = false;
    setSessions([]);
    setLoading(true);
    setError(null);
    listDomainSessions(domainId)
      .then((result) => {
        if (cancelled) return;
        setSessions(result.sessions);
      })
      .catch((err) => {
        if (cancelled) return;
        setSessions([]);
        setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [domainId, tick]);

  return { sessions, loading, error, refresh };
}
