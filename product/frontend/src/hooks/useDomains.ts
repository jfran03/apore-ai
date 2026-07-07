import { useCallback, useEffect, useState } from 'react';
import { listDomains } from '../api/client';
import type { WorkspaceDomain } from '../api/types';

export interface DomainsState {
  domains: WorkspaceDomain[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

export function useDomains(backendOnline: boolean): DomainsState {
  const [domains, setDomains] = useState<WorkspaceDomain[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const refresh = useCallback(() => setTick((v) => v + 1), []);

  useEffect(() => {
    if (!backendOnline) return;
    let cancelled = false;
    setLoading(true);
    listDomains()
      .then((result) => {
        if (cancelled) return;
        setDomains(result.domains);
        setError(null);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [backendOnline, tick]);

  return { domains, loading, error, refresh };
}
