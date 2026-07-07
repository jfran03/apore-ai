import { useState, type FormEvent } from 'react';
import { updateProviderConfig } from '../api/client';
import type { ProviderConfig } from '../api/types';

interface SettingsModalProps {
  provider: ProviderConfig | null;
  onClose: () => void;
  onSaved: () => void;
}

export function SettingsModal({ provider, onClose, onSaved }: SettingsModalProps) {
  const [anthropicKey, setAnthropicKey] = useState('');
  const [nimKey, setNimKey] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await updateProviderConfig({
        ...(anthropicKey.trim() ? { anthropic_api_key: anthropicKey.trim() } : {}),
        ...(nimKey.trim() ? { nim_api_key: nimKey.trim() } : {}),
      });
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <article className="panel settings-modal" onClick={(e) => e.stopPropagation()}>
        <div className="screen-intro">
          <div>
            <p className="eyebrow">Settings</p>
            <h2>LLM providers</h2>
            <p>
              Keys are stored locally by the Python runtime. Anthropic is preferred when
              both are set; NIM is the fallback.
            </p>
          </div>
          <button className="button-secondary" onClick={onClose}>
            Close
          </button>
        </div>

        {!provider?.active_provider && (
          <div className="alert is-error">No provider configured - tutoring is disabled.</div>
        )}

        <form className="domain-form" onSubmit={save}>
          <label className="field is-wide">
            <span className="label">Anthropic API key</span>
            <input
              className="input"
              type="password"
              value={anthropicKey}
              onChange={(e) => setAnthropicKey(e.target.value)}
              placeholder={
                provider?.anthropic_api_key_set
                  ? `configured (${provider.anthropic_api_key_hint ?? '...'})`
                  : 'sk-ant-...'
              }
            />
          </label>
          <label className="field is-wide">
            <span className="label">NVIDIA NIM API key</span>
            <input
              className="input"
              type="password"
              value={nimKey}
              onChange={(e) => setNimKey(e.target.value)}
              placeholder={
                provider?.nim_api_key_set
                  ? `configured (${provider.nim_api_key_hint ?? '...'})`
                  : 'nvapi-...'
              }
            />
          </label>

          {error && <div className="alert is-error">{error}</div>}

          <div className="form-footer">
            <span className="help">
              Active: {provider?.active_provider ?? 'none'}
              {provider?.active_model ? ` - ${provider.active_model}` : ''}
            </span>
            <button
              type="submit"
              className="button-primary"
              disabled={busy || (!anthropicKey.trim() && !nimKey.trim())}
            >
              {busy ? 'Saving...' : 'Save keys'}
            </button>
          </div>
        </form>
      </article>
    </div>
  );
}
