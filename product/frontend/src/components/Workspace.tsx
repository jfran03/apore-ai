import { VIEW_LABELS, type ViewId } from '../types';
import type { BackendState } from '../hooks/useBackend';
import { CreateDomainView } from './views/CreateDomainView';
import { SourcesView } from './views/SourcesView';
import { ChatView } from './views/ChatView';
import { ScratchpadView } from './views/ScratchpadView';
import { GraphView } from './views/GraphView';

interface WorkspaceProps {
  activeView: ViewId;
  backend: BackendState;
}

export function Workspace({ activeView, backend }: WorkspaceProps) {
  return (
    <main className="workspace">
      <div className="tab-bar">
        <button className="tab is-active">{VIEW_LABELS[activeView]}</button>
        <button className="tab">domain.json</button>
      </div>

      <section className="stage">
        {activeView === 'create' && <CreateDomainView backend={backend} />}
        {activeView === 'sources' && <SourcesView />}
        {activeView === 'chat' && <ChatView />}
        {activeView === 'scratchpad' && <ScratchpadView />}
        {activeView === 'graph' && <GraphView />}
      </section>
    </main>
  );
}
