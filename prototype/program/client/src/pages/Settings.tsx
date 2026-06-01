import { useState, useEffect } from 'react';
import { getProviderConfig, setProviderConfig } from '../api/client';
import type { ProviderConfig } from '../api/types';

const PROVIDERS = ['anthropic', 'nim', 'stub'] as const;
type Provider = (typeof PROVIDERS)[number];

const DEFAULT_MODELS: Record<Provider, string> = {
  anthropic: 'claude-sonnet-4-5',
  nim: 'meta/llama-3.3-70b-instruct',
  stub: 'stub',
};

export function Settings() {
  const [provider, setProvider] = useState<Provider>('anthropic');
  const [model, setModel] = useState(DEFAULT_MODELS['anthropic']);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    getProviderConfig()
      .then((cfg: ProviderConfig) => {
        setProvider(cfg.provider as Provider);
        setModel(cfg.model);
      })
      .catch((err: unknown) => {
        setLoadError(err instanceof Error ? err.message : 'Failed to load config');
      });
  }, []);

  function handleProviderChange(next: Provider) {
    setProvider(next);
    setModel(DEFAULT_MODELS[next]);
  }

  async function handleSave() {
    setSaveStatus('saving');
    try {
      await setProviderConfig({ provider, model });
      setSaveStatus('saved');
      setTimeout(() => setSaveStatus('idle'), 2000);
    } catch {
      setSaveStatus('error');
    }
  }

  return (
    <main className="page">
      <h1 className="page__title">Settings</h1>

      {/* Provider & Model */}
      <section style={styles.section}>
        <h2 style={styles.sectionHeading}>Provider &amp; Model</h2>
        <div className="card" style={styles.card}>
          {loadError && (
            <p style={styles.errorText}>Could not load current config: {loadError}</p>
          )}

          <fieldset style={styles.fieldset}>
            <legend style={styles.legend}>Provider</legend>
            <div style={styles.radioGroup}>
              {PROVIDERS.map((p) => (
                <label key={p} style={styles.radioLabel}>
                  <input
                    type="radio"
                    name="provider"
                    value={p}
                    checked={provider === p}
                    onChange={() => handleProviderChange(p)}
                    style={styles.radioInput}
                  />
                  <span style={styles.radioText}>{p}</span>
                </label>
              ))}
            </div>
          </fieldset>

          <div style={styles.field}>
            <label htmlFor="model-input" style={styles.fieldLabel}>
              Model
            </label>
            <input
              id="model-input"
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              style={styles.textInput}
              spellCheck={false}
            />
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

      {/* Fixture */}
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

      {/* About */}
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
  fieldset: {
    border: 'none',
    margin: 0,
    padding: 0,
  },
  legend: {
    fontSize: 'var(--font-size-body-sm)',
    fontWeight: 'var(--font-weight-medium)' as const,
    color: 'var(--color-body)',
    marginBottom: 'var(--spacing-xs)',
  },
  radioGroup: {
    display: 'flex',
    gap: 'var(--spacing-base)',
    flexWrap: 'wrap' as const,
  },
  radioLabel: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--spacing-xs)',
    minHeight: '44px',
    cursor: 'pointer',
  },
  radioInput: {
    accentColor: 'var(--color-primary)',
    width: '16px',
    height: '16px',
    cursor: 'pointer',
  },
  radioText: {
    fontSize: 'var(--font-size-body-sm)',
    color: 'var(--color-ink)',
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
