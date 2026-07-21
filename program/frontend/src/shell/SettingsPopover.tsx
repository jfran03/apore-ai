import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { getProviderConfig, setProviderConfig } from '../api/client';
import type { ProviderConfig, ProviderConfigUpdate } from '../api/types';
import { popover } from '../motion';
import { getStoredTheme, setTheme, type Theme } from './theme';

export function SettingsPopover() {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const reduceMotion = useReducedMotion();
  const panelMotion = popover(reduceMotion);

  useEffect(() => {
    if (!open) return;
    function onMouseDown(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false);
    }
    document.addEventListener('mousedown', onMouseDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onMouseDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  return (
    <div className="settings" ref={containerRef}>
      <button
        type="button"
        className="topbar__iconbtn"
        aria-label="Settings"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        ⚙
      </button>
      <AnimatePresence>
        {open && <SettingsPanel motionProps={panelMotion} />}
      </AnimatePresence>
    </div>
  );
}

function SettingsPanel({
  motionProps,
}: {
  motionProps: ReturnType<typeof popover>;
}) {
  const [config, setConfig] = useState<ProviderConfig | null>(null);
  const [anthropicKey, setAnthropicKey] = useState('');
  const [nimKey, setNimKey] = useState('');
  const [model, setModel] = useState('');
  const [anthropicTouched, setAnthropicTouched] = useState(false);
  const [nimTouched, setNimTouched] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [loadError, setLoadError] = useState<string | null>(null);
  const [theme, setThemeState] = useState<Theme>(() => getStoredTheme());

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleThemeChange(next: Theme) {
    setThemeState(next);
    setTheme(next);
  }

  async function refresh() {
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
      await refresh();
      setSaveStatus('saved');
      setTimeout(() => setSaveStatus('idle'), 2000);
    } catch {
      setSaveStatus('error');
    }
  }

  const activeProviderLabel = config?.active_provider
    ? `${config.active_provider} (${config.active_model ?? 'default model'})`
    : 'No provider configured';

  return (
    <motion.div
      className="settings__panel"
      role="dialog"
      aria-label="Settings"
      initial={motionProps.initial}
      animate={motionProps.animate}
      exit={motionProps.exit}
      transition={motionProps.transition}
    >
      <div className="settings__theme">
        <span className="settings__label" id="settings-theme-label">
          Appearance
        </span>
        <label className="theme-switch">
          <span className="theme-switch__text">Light</span>
          <input
            type="checkbox"
            className="theme-switch__input"
            checked={theme === 'dark'}
            onChange={(e) => handleThemeChange(e.target.checked ? 'dark' : 'light')}
            aria-labelledby="settings-theme-label"
          />
          <span className="theme-switch__track" aria-hidden="true">
            <span className="theme-switch__thumb" />
          </span>
          <span className="theme-switch__text">Dark</span>
        </label>
      </div>

      {loadError && <p className="settings__error">Could not load config: {loadError}</p>}
      <p className="settings__status">
        Active provider: <strong>{activeProviderLabel}</strong>
      </p>

      <label className="settings__field">
        <span className="settings__label">Anthropic API key</span>
        <input
          type="password"
          className="settings__input"
          value={anthropicKey}
          onChange={(e) => {
            setAnthropicTouched(true);
            setAnthropicKey(e.target.value);
          }}
          placeholder="sk-ant-..."
          spellCheck={false}
          autoComplete="off"
        />
        <span className="settings__hint">
          {config?.anthropic_api_key_set
            ? `Configured (${config.anthropic_api_key_hint ?? 'hidden'})`
            : 'Not configured'}
        </span>
      </label>

      <label className="settings__field">
        <span className="settings__label">NVIDIA NIM API key</span>
        <input
          type="password"
          className="settings__input"
          value={nimKey}
          onChange={(e) => {
            setNimTouched(true);
            setNimKey(e.target.value);
          }}
          placeholder="nvapi-..."
          spellCheck={false}
          autoComplete="off"
        />
        <span className="settings__hint">
          {config?.nim_api_key_set
            ? `Configured (${config.nim_api_key_hint ?? 'hidden'})`
            : 'Not configured'}
        </span>
      </label>

      <label className="settings__field">
        <span className="settings__label">Model override (optional)</span>
        <input
          type="text"
          className="settings__input"
          value={model}
          onChange={(e) => setModel(e.target.value)}
          spellCheck={false}
        />
      </label>

      <div className="settings__actions">
        <button
          type="button"
          className="btn btn--primary"
          onClick={handleSave}
          disabled={saveStatus === 'saving'}
        >
          {saveStatus === 'saving' ? 'Saving…' : saveStatus === 'saved' ? 'Saved' : 'Save'}
        </button>
        {saveStatus === 'error' && (
          <span className="settings__error">Save failed — is the server running?</span>
        )}
      </div>
    </motion.div>
  );
}
