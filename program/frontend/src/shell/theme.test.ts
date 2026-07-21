import { afterEach, describe, expect, it } from 'vitest';
import {
  DEFAULT_THEME,
  THEME_KEY,
  applyTheme,
  getStoredTheme,
  setTheme,
} from './theme';

afterEach(() => {
  localStorage.clear();
  delete document.documentElement.dataset.theme;
});

describe('theme', () => {
  it('defaults to dark when nothing is stored', () => {
    expect(getStoredTheme()).toBe(DEFAULT_THEME);
    expect(DEFAULT_THEME).toBe('dark');
  });

  it('reads a stored light preference', () => {
    localStorage.setItem(THEME_KEY, 'light');
    expect(getStoredTheme()).toBe('light');
  });

  it('ignores invalid stored values', () => {
    localStorage.setItem(THEME_KEY, 'sepia');
    expect(getStoredTheme()).toBe('dark');
  });

  it('setTheme persists and applies the attribute', () => {
    setTheme('light');
    expect(localStorage.getItem(THEME_KEY)).toBe('light');
    expect(document.documentElement.dataset.theme).toBe('light');

    setTheme('dark');
    expect(localStorage.getItem(THEME_KEY)).toBe('dark');
    expect(document.documentElement.dataset.theme).toBe('dark');
  });

  it('applyTheme sets the attribute without writing storage', () => {
    applyTheme('light');
    expect(document.documentElement.dataset.theme).toBe('light');
    expect(localStorage.getItem(THEME_KEY)).toBeNull();
  });
});
