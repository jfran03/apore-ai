import { useCallback, useEffect, useState } from 'react';
import {
  getHealth,
  getKnowledgeCatalog,
  getProviderConfig,
} from '../api/client';
import type { HealthResponse, KnowledgeCatalog, ProviderConfig } from '../api/types';

export type ConnectionStatus = 'checking' | 'online' | 'offline';

export interface BackendState {
  status: ConnectionStatus;
  health: HealthResponse | null;
  catalog: KnowledgeCatalog | null;
  provider: ProviderConfig | null;
  error: string | null;
  refresh: () => void;
}

// Single source of truth for "is the local Python runtime reachable, and what
// does it currently hold?" This is the wiring that proves the desktop loop:
// React shell -> localhost FastAPI -> tutor runtime + inspectable files.
export function useBackend(): BackendState {
  const [status, setStatus] = useState<ConnectionStatus>('checking');
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [catalog, setCatalog] = useState<KnowledgeCatalog | null>(null);
  const [provider, setProvider] = useState<ProviderConfig | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const refresh = useCallback(() => setTick((value) => value + 1), []);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setStatus('checking');
      setError(null);
      try {
        const healthResult = await getHealth();
        if (cancelled) return;
        setHealth(healthResult);
        setStatus('online');

        // These are best-effort: an online backend with no curriculum or no
        // provider key is still a valid, connected state.
        const [catalogResult, providerResult] = await Promise.allSettled([
          getKnowledgeCatalog(),
          getProviderConfig(),
        ]);
        if (cancelled) return;
        if (catalogResult.status === 'fulfilled') setCatalog(catalogResult.value);
        if (providerResult.status === 'fulfilled') setProvider(providerResult.value);
      } catch (err) {
        if (cancelled) return;
        setStatus('offline');
        setError(err instanceof Error ? err.message : String(err));
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [tick]);

  return { status, health, catalog, provider, error, refresh };
}
