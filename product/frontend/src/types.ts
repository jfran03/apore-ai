export type ViewId = 'create' | 'sources' | 'chat' | 'scratchpad' | 'graph';

export const VIEW_LABELS: Record<ViewId, string> = {
  create: 'New Learning Domain',
  sources: 'Add Sources',
  chat: 'Discrete Math Tutor Chat',
  scratchpad: 'Set Theory Scratchpad',
  graph: 'Curriculum Map',
};
