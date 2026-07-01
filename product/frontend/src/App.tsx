import { useState } from 'react';
import { DesktopTitlebar } from './components/DesktopTitlebar';
import { Sidebar } from './components/Sidebar';
import { Workspace } from './components/Workspace';
import { AssistantPanel } from './components/AssistantPanel';
import { useBackend } from './hooks/useBackend';
import type { ViewId } from './types';

export function App() {
  const [activeView, setActiveView] = useState<ViewId>('create');
  const backend = useBackend();

  const isChatView = activeView === 'chat';

  return (
    <div className="page">
      <DesktopTitlebar status={backend.status} onRefresh={backend.refresh} />

      <div className={`app-shell${isChatView ? ' is-chat-view' : ''}`}>
        <Sidebar
          catalog={backend.catalog}
          activeView={activeView}
          onSelectView={setActiveView}
        />
        <Workspace activeView={activeView} backend={backend} />
        {!isChatView && <AssistantPanel activeView={activeView} />}
      </div>
    </div>
  );
}
