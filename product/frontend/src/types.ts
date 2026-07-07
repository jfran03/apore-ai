export type DomainTab = 'chat' | 'sources' | 'graph' | 'scratchpad';

export type AppView =
  | { kind: 'create-domain' }
  | { kind: 'domain'; domainId: string; tab: DomainTab; sessionId: string | null };

export const TAB_LABELS: Record<DomainTab, string> = {
  chat: 'Tutor Chat',
  sources: 'Sources',
  graph: 'Curriculum Graph',
  scratchpad: 'Scratchpad',
};
