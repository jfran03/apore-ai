import { useEffect, useMemo, useState } from 'react';
import { getProviderConfig, setProviderConfig } from '../api/client';
import type { ProviderConfig, ProviderConfigUpdate } from '../api/types';

export function Settings() {
  const [config, setConfig] = useState<ProviderConfig | null>(null);
  const [anthropicKey, setAnthropicKey] = useState('');
  const [nimKey, setNimKey] = useState('');
  const [model, setModel] = useState('');
  const [anthropicTouched, setAnthropicTouched] = useState(false);
  const [nimTouched, setNimTouched] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [loadError, setLoadError] = useState<string | null>(null);

  const activeProviderLabel = useMemo(() => {
    if (!config?.active_provider) return 'No provider configured';
    return `${config.active_provider} (${config.active_model ?? 'default model'})`;
  }, [config]);

  useEffect(() => {
    void refreshConfig();
  }, []);

  async function refreshConfig() {
    try {
      const cfg = await getProviderConfig();
      setConfig(cfg);
      setModel(cfg.model);
      setAnthropicKey('');
      setNimKey('');
      setAnthropicTouched(false);
      setNimTouched(false);
      setLoadError(null);
    } catch (err: unknown) {
      setLoadError(err instanceof Error ? err.message : 'Failed to load config');
    }
  }

  async function handleSave() {
    setSaveStatus('saving');
    try {
      const payload: ProviderConfigUpdate = { model };
      if (anthropicTouched) payload.anthropic_api_key = anthropicKey;
      if (nimTouched) payload.nim_api_key = nimKey;
      await setProviderConfig(payload);
      await refreshConfig();
      setSaveStatus('saved');
      setTimeout(() => setSaveStatus('idle'), 2000);
    } catch {
      setSaveStatus('error');
    }
  }

  return (
    <main className="page">
      <h1 className="page__title">Settings</h1>

      <section style={styles.section}>
        <h2 style={styles.sectionHeading}>Bring Your Own Key</h2>
        <div className="card" style={styles.card}>
          {loadError && (
            <p style={styles.errorText}>Could not load current config: {loadError}</p>
          )}

          <p style={styles.statusLine}>
            <span style={styles.statusLabel}>Active provider</span>
            <span>{activeProviderLabel}</span>
          </p>

          <div style={styles.field}>
            <label htmlFor="anthropic-key" style={styles.fieldLabel}>
              Anthropic API key
            </label>
            <input
              id="anthropic-key"
              type="password"
              value={anthropicKey}
              onChange={(e) => {
                setAnthropicTouched(true);
                setAnthropicKey(e.target.value);
              }}
              placeholder="sk-ant-..."
              style={styles.textInput}
              spellCheck={false}
              autoComplete="off"
            />
            <span style={styles.hintText}>
              {config?.anthropic_api_key_set
                ? `Configured (${config.anthropic_api_key_hint ?? 'hidden'})`
                : 'Not configured'}
            </span>
          </div>

          <div style={styles.field}>
            <label htmlFor="nim-key" style={styles.fieldLabel}>
              NVIDIA NIM API key
            </label>
            <input
              id="nim-key"
              type="password"
              value={nimKey}
              onChange={(e) => {
                setNimTouched(true);
                setNimKey(e.target.value);
              }}
              placeholder="nvapi-..."
              style={styles.textInput}
              spellCheck={false}
              autoComplete="off"
            />
            <span style={styles.hintText}>
              {config?.nim_api_key_set
                ? `Configured (${config.nim_api_key_hint ?? 'hidden'})`
                : 'Not configured'}
            </span>
          </div>

          <div style={styles.field}>
            <label htmlFor="model-input" style={styles.fieldLabel}>
              Model override (optional)
            </label>
            <input
              id="model-input"
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              style={styles.textInput}
              spellCheck={false}
            />
            <span style={styles.hintText}>
              Leave blank to use provider defaults.
            </span>
          </div>

          <div style={styles.actionRow}>
            <button
              className="btn btn--primary"
              onClick={handleSave}
              disabled={saveStatus === 'saving'}
            >
              {saveStatus === 'saving' ? 'Saving…' : saveStatus === 'saved' ? 'Saved' : 'Save'}
            </button>
            {saveStatus === 'error' && (
              <span style={styles.errorText}>Save failed — is the server running?</span>
            )}
          </div>
        </div>
      </section>

      <section style={styles.section}>
        <h2 style={styles.sectionHeading}>Fixture</h2>
        <div className="card" style={styles.card}>
          <p style={styles.fixtureStatus}>
            <strong style={styles.fixtureName}>apore-lite</strong>
            <span style={styles.fixtureCommit}> — commit 17f4dfa4…</span>
          </p>
          <div style={styles.actionRow}>
            <button
              className="btn btn--ghost"
              disabled
              title="Run `python scripts/fetch_fixture.py` manually"
            >
              Fetch fixture
            </button>
            <span style={styles.mutedNote}>
              Run <code style={styles.code}>python scripts/fetch_fixture.py</code> to update.
            </span>
          </div>
        </div>
      </section>

      <section style={styles.section}>
        <h2 style={styles.sectionHeading}>About</h2>
        <div className="card" style={styles.card}>
          <p style={styles.aboutLine}>
            <span style={styles.aboutLabel}>Version</span>
            <span>0.1.0-prototype</span>
          </p>
          <p style={styles.aboutLine}>
            <span style={styles.aboutLabel}>Docs</span>
            <a
              href="https://github.com/apore-research/prototype#readme"
              target="_blank"
              rel="noreferrer"
              style={styles.link}
            >
              README
            </a>
          </p>
        </div>
      </section>
    </main>
  );
}

const styles = {
  section: {
    marginTop: 'var(--spacing-xl)',
  },
  sectionHeading: {
    fontSize: 'var(--font-size-title-md)',
    fontWeight: 'var(--font-weight-semibold)' as const,
    color: 'var(--color-ink)',
    marginBottom: 'var(--spacing-sm)',
  },
  card: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 'var(--spacing-base)',
  },
  statusLine: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 'var(--spacing-xxs)',
    margin: 0,
    fontSize: 'var(--font-size-body-sm)',
    color: 'var(--color-ink)',
  },
  statusLabel: {
    fontWeight: 'var(--font-weight-medium)' as const,
    color: 'var(--color-body)',
  },
  field: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 'var(--spacing-xxs)',
  },
  fieldLabel: {
    fontSize: 'var(--font-size-body-sm)',
    fontWeight: 'var(--font-weight-medium)' as const,
    color: 'var(--color-body)',
  },
  hintText: {
    fontSize: 'var(--font-size-caption)',
    color: 'var(--color-muted)',
  },
  textInput: {
    height: '44px',
    padding: '0 var(--spacing-sm)',
    border: '1px solid var(--color-hairline)',
    borderRadius: 'var(--radius-md)',
    fontFamily: 'var(--font-mono)',
    fontSize: 'var(--font-size-body-sm)',
    color: 'var(--color-ink)',
    background: 'var(--color-canvas-soft)',
    outline: 'none',
    width: '100%',
    maxWidth: '480px',
    boxSizing: 'border-box' as const,
  },
  actionRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--spacing-sm)',
    flexWrap: 'wrap' as const,
  },
  errorText: {
    fontSize: 'var(--font-size-body-sm)',
    color: 'var(--color-semantic-error)',
  },
  fixtureStatus: {
    fontSize: 'var(--font-size-body-sm)',
    color: 'var(--color-body)',
    margin: 0,
  },
  fixtureName: {
    color: 'var(--color-ink)',
    fontWeight: 'var(--font-weight-semibold)' as const,
  },
  fixtureCommit: {
    fontFamily: 'var(--font-mono)',
    fontSize: 'var(--font-size-caption)',
    color: 'var(--color-muted)',
  },
  mutedNote: {
    fontSize: 'var(--font-size-caption)',
    color: 'var(--color-muted)',
  },
  code: {
    fontFamily: 'var(--font-mono)',
    fontSize: 'var(--font-size-code)',
    background: 'var(--color-hairline-soft)',
    padding: '1px 4px',
    borderRadius: 'var(--radius-xs)',
  },
  aboutLine: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--spacing-base)',
    fontSize: 'var(--font-size-body-sm)',
    color: 'var(--color-ink)',
    margin: 0,
  },
  aboutLabel: {
    color: 'var(--color-muted)',
    minWidth: '64px',
  },
  link: {
    color: 'var(--color-primary)',
    textDecoration: 'none',
  },
} as const;
