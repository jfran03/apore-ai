import { useEffect, useState } from 'react';
import { DesktopTitlebar } from './components/DesktopTitlebar';
import { Sidebar } from './components/Sidebar';
import { Workspace } from './components/Workspace';
import { AssistantPanel } from './components/AssistantPanel';
import { SettingsModal } from './components/SettingsModal';
import { useBackend } from './hooks/useBackend';
import { useDomains } from './hooks/useDomains';
import { useDomainSessions } from './hooks/useDomainSessions';
import type { AppView } from './types';

export function App() {
  const backend = useBackend();
  const domainsState = useDomains(backend.status === 'online');
  const [view, setView] = useState<AppView>({ kind: 'create-domain' });
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [initialized, setInitialized] = useState(false);

  const activeDomainId = view.kind === 'domain' ? view.domainId : null;
  const sessionsState = useDomainSessions(activeDomainId);

  // First load: land on the first usable domain, else the create screen.
  useEffect(() => {
    if (initialized || domainsState.loading || backend.status !== 'online') return;
    const first = domainsState.domains.find((d) => d.status !== 'invalid');
    if (first) {
      setView({ kind: 'domain', domainId: first.id, tab: 'chat', sessionId: null });
    }
    setInitialized(true);
  }, [initialized, domainsState.loading, domainsState.domains, backend.status]);

  const isChatView = view.kind === 'domain' && view.tab === 'chat';

  return (
    <div className="page">
      <DesktopTitlebar
        status={backend.status}
        onRefresh={() => {
          backend.refresh();
          domainsState.refresh();
        }}
        onOpenSettings={() => setSettingsOpen(true)}
      />

      <div className={`app-shell${isChatView ? ' is-chat-view' : ''}`}>
        <Sidebar
          domains={domainsState.domains}
          sessions={sessionsState.sessions}
          view={view}
          onNavigate={setView}
        />
        <Workspace
          view={view}
          backend={backend}
          domains={domainsState.domains}
          onNavigate={setView}
          onDomainsChanged={domainsState.refresh}
          onSessionsChanged={sessionsState.refresh}
        />
        {!isChatView && <AssistantPanel />}
      </div>

      {settingsOpen && (
        <SettingsModal
          provider={backend.provider}
          onClose={() => setSettingsOpen(false)}
          onSaved={backend.refresh}
        />
      )}
    </div>
  );
}
