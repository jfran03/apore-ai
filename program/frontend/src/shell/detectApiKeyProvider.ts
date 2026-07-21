import type { ProviderConfigUpdate } from '../api/types';

export type DetectedProvider = 'anthropic' | 'nim';

const ANTHROPIC_PREFIX = 'sk-ant-';
const NIM_PREFIX = 'nvapi-';

export function detectApiKeyProvider(rawKey: string): DetectedProvider | null {
  const key = rawKey.trim();
  if (key.startsWith(ANTHROPIC_PREFIX)) return 'anthropic';
  if (key.startsWith(NIM_PREFIX)) return 'nim';
  return null;
}

export function buildProviderConfigUpdate(rawKey: string): ProviderConfigUpdate | null {
  const provider = detectApiKeyProvider(rawKey);
  if (!provider) return null;
  const key = rawKey.trim();
  return provider === 'anthropic' ? { anthropic_api_key: key } : { nim_api_key: key };
}
