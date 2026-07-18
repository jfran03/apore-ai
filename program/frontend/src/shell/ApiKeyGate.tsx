import { useEffect, useState } from 'react';
import { getProviderConfig, setProviderConfig } from '../api/client';
import type { ProviderConfig } from '../api/types';
import { buildProviderConfigUpdate, detectApiKeyProvider } from './detectApiKeyProvider';

type GateStatus = 'loading' | 'blocked' | 'ready' | 'load-error';

function hasKey(cfg: ProviderConfig): boolean {
  return cfg.anthropic_api_key_set || cfg.nim_api_key_set;
}

export function ApiKeyGate() {
  const [status, setStatus] = useState<GateStatus>('loading');

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const cfg = await getProviderConfig();
        if (cancelled) return;
        setStatus(hasKey(cfg) ? 'ready' : 'blocked');
      } catch {
        if (!cancelled) setStatus('load-error');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (status === 'ready' || status === 'loading') return null;

  return (
    <ApiKeyGateOverlay
      loadError={status === 'load-error'}
      onConfigured={() => setStatus('ready')}
      onRetry={() => setStatus('loading')}
    />
  );
}

interface OverlayProps {
  loadError: boolean;
  onConfigured: () => void;
  onRetry: () => void;
}

function ApiKeyGateOverlay({ loadError, onConfigured, onRetry }: OverlayProps) {
  const [key, setKey] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const detected = detectApiKeyProvider(key);
  const trimmed = key.trim();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const update = buildProviderConfigUpdate(key);
    if (!update) {
      setError('That key is not recognized. Enter an Anthropic key (sk-ant-…) or a NIM key (nvapi-…).');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const cfg = await setProviderConfig(update);
      if (hasKey(cfg)) {
        onConfigured();
      } else {
        setError('The key was not saved. Please try again.');
      }
    } catch {
      setError('Could not reach the server. Is it running?');
    } finally {
      setSaving(false);
    }
  }

  if (loadError) {
    return (
      <div className="api-key-gate" role="dialog" aria-modal="true" aria-label="Configuration unavailable">
        <div className="api-key-gate__dialog">
          <h2 className="api-key-gate__title">Can't reach the server</h2>
          <p className="api-key-gate__body">
            Apore needs to check your provider configuration before you can start.
          </p>
          <div className="api-key-gate__actions">
            <button type="button" className="btn btn--primary" onClick={onRetry}>
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  let hint: string;
  if (trimmed.length === 0) {
    hint = 'Anthropic keys start with sk-ant-, NVIDIA NIM keys start with nvapi-.';
  } else if (detected === 'anthropic') {
    hint = 'Detected: Anthropic';
  } else if (detected === 'nim') {
    hint = 'Detected: NVIDIA NIM';
  } else {
    hint = 'Unrecognized key. Must be an Anthropic (sk-ant-…) or NIM (nvapi-…) key.';
  }

  return (
    <div className="api-key-gate" role="dialog" aria-modal="true" aria-label="Add an API key">
      <form className="api-key-gate__dialog" onSubmit={handleSubmit}>
        <h2 className="api-key-gate__title">Add an API key to get started</h2>
        <p className="api-key-gate__body">
          Apore brings your own key. Paste an Anthropic or NVIDIA NIM key and we'll set up the right
          provider for you.
        </p>

        <label className="api-key-gate__field">
          <span className="api-key-gate__label">API key</span>
          <input
            type="password"
            className="api-key-gate__input"
            value={key}
            onChange={(e) => {
              setKey(e.target.value);
              if (error) setError(null);
            }}
            placeholder="sk-ant-… or nvapi-…"
            spellCheck={false}
            autoComplete="off"
            autoFocus
          />
          <span
            className={`api-key-gate__hint${detected === null && trimmed.length > 0 ? ' api-key-gate__hint--error' : ''}`}
          >
            {hint}
          </span>
        </label>

        {error && <p className="api-key-gate__error">{error}</p>}

        <div className="api-key-gate__actions">
          <button
            type="submit"
            className="btn btn--primary"
            disabled={saving || detected === null}
          >
            {saving ? 'Saving…' : 'Save key'}
          </button>
        </div>
      </form>
    </div>
  );
}
