import type { ProviderConfig } from '../api/types';

interface SettingsModalProps {
  provider: ProviderConfig | null;
  onClose: () => void;
  onSaved: () => void;
}

export function SettingsModal(_props: SettingsModalProps) {
  return null;
}
