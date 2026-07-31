import type { MasteryBand } from '../../api/types';

export const BAND_LABEL: Record<MasteryBand, string> = {
  new: 'New',
  struggling: 'Struggling',
  learning: 'Learning',
  proficient: 'Proficient',
};

/**
 * Band color mapping mirrors the study concept picker (study.css): a calm
 * research-instrument scale, not a red/amber/green traffic light. Only
 * "proficient" earns a semantic hue; the rest read as neutral weight.
 */
export const BAND_COLOR_VAR: Record<MasteryBand, string> = {
  new: 'var(--color-muted-soft)',
  struggling: 'var(--color-body-strong)',
  learning: 'var(--color-muted)',
  proficient: 'var(--color-semantic-success)',
};

export function masteryText(displayPct: number | null): string {
  return displayPct == null ? 'New' : `${displayPct}%`;
}
