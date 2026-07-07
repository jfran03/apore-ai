import { TAB_LABELS, type AppView } from '../types';
import type { BackendState } from '../hooks/useBackend';
import type { WorkspaceDomain } from '../api/types';
import { CreateDomainView } from './views/CreateDomainView';
import { SourcesView } from './views/SourcesView';
import { ChatView } from './views/ChatView';
import { ScratchpadView } from './views/ScratchpadView';
import { GraphView } from './views/GraphView';

interface WorkspaceProps {
  view: AppView;
  backend: BackendState;
  domains: WorkspaceDomain[];
  onNavigate: (view: AppView) => void;
  onDomainsChanged: () => void;
  onSessionsChanged: () => void;
}

export function Workspace({
  view,
  backend,
  domains,
  onNavigate,
  onDomainsChanged,
  onSessionsChanged,
}: WorkspaceProps) {
  const domain =
    view.kind === 'domain' ? domains.find((d) => d.id === view.domainId) ?? null : null;
  const title =
    view.kind === 'create-domain'
      ? 'New Learning Domain'
      : `${domain?.name ?? view.domainId} - ${TAB_LABELS[view.tab]}`;

  return (
    <main className="workspace">
      <div className="tab-bar">
        <button className="tab is-active">{title}</button>
      </div>

      <section className="stage">
        {view.kind === 'create-domain' && (
          <CreateDomainView
            backend={backend}
            onCreated={(created) => {
              onDomainsChanged();
              onNavigate({ kind: 'domain', domainId: created.id, tab: 'chat', sessionId: null });
            }}
            onCancel={
              domains.length > 0
                ? () =>
                    onNavigate({
                      kind: 'domain',
                      domainId: domains[0].id,
                      tab: 'chat',
                      sessionId: null,
                    })
                : null
            }
          />
        )}
        {view.kind === 'domain' && domain && view.tab === 'chat' && (
          <ChatView
            domain={domain}
            sessionId={view.sessionId}
            backend={backend}
            onSessionCreated={(sessionId) => {
              onSessionsChanged();
              onNavigate({ ...view, sessionId });
            }}
          />
        )}
        {view.kind === 'domain' && domain && view.tab === 'sources' && (
          <SourcesView domain={domain} />
        )}
        {view.kind === 'domain' && domain && view.tab === 'scratchpad' && <ScratchpadView />}
        {view.kind === 'domain' && domain && view.tab === 'graph' && <GraphView domain={domain} />}
      </section>
    </main>
  );
}
