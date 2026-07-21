export type Theme = 'light' | 'dark';

export const THEME_KEY = 'apore.theme';
export const DEFAULT_THEME: Theme = 'dark';

export function getStoredTheme(): Theme {
  try {
    const raw = localStorage.getItem(THEME_KEY);
    if (raw === 'light' || raw === 'dark') return raw;
  } catch {
    // localStorage unavailable (private mode, SSR, etc.)
  }
  return DEFAULT_THEME;
}

export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
}

export function setTheme(theme: Theme): void {
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    // ignore write failures
  }
  applyTheme(theme);
}
