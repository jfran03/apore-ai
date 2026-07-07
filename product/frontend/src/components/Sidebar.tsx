import type { WorkspaceDomain, WorkspaceSessionSummary } from '../api/types';
import type { AppView } from '../types';

interface SidebarProps {
  domains: WorkspaceDomain[];
  sessions: WorkspaceSessionSummary[];
  view: AppView;
  onNavigate: (view: AppView) => void;
}

export function Sidebar({ domains, sessions, view, onNavigate }: SidebarProps) {
  const activeDomainId = view.kind === 'domain' ? view.domainId : null;

  return (
    <aside className="sidebar">
      <div className="domain-list">
        {domains.length === 0 && (
          <p className="domain-meta" style={{ padding: '8px 4px' }}>
            No domains yet. Create your first learning domain to get started.
          </p>
        )}

        {domains.map((domain) => (
          <DomainCard
            key={domain.id}
            domain={domain}
            active={domain.id === activeDomainId}
            sessions={domain.id === activeDomainId ? sessions : []}
            view={view}
            onNavigate={onNavigate}
          />
        ))}

        <button
          className="button-secondary"
          onClick={() => onNavigate({ kind: 'create-domain' })}
        >
          New domain
        </button>
      </div>
    </aside>
  );
}

function DomainCard({
  domain,
  active,
  sessions,
  view,
  onNavigate,
}: {
  domain: WorkspaceDomain;
  active: boolean;
  sessions: WorkspaceSessionSummary[];
  view: AppView;
  onNavigate: (view: AppView) => void;
}) {
  if (domain.status === 'invalid') {
    return (
      <section className="domain-card">
        <div className="domain-row">
          <div>
            <div className="domain-name">{domain.id}</div>
            <div className="domain-meta">Invalid folder: {domain.reason}</div>
          </div>
        </div>
      </section>
    );
  }

  const activeSessionId =
    view.kind === 'domain' && view.domainId === domain.id ? view.sessionId : null;
  const activeTab = view.kind === 'domain' && view.domainId === domain.id ? view.tab : null;

  const open = (tab: 'chat' | 'sources' | 'graph' | 'scratchpad', sessionId: string | null = null) =>
    onNavigate({ kind: 'domain', domainId: domain.id, tab, sessionId });

  return (
    <section className={`domain-card${active ? ' is-active' : ''}`}>
      <button className="domain-row" onClick={() => open('chat')}>
        <div>
          <div className="domain-name">{domain.name}</div>
          <div className="domain-meta">
            {domain.status === 'empty'
              ? 'No curriculum compiled yet'
              : `${domain.chapters.length} chapter${domain.chapters.length === 1 ? '' : 's'}`}
          </div>
        </div>
      </button>

      {active && (
        <div className="tree">
          <div className="tree-row is-heading">
            <span>Session History</span>
            <span className="tree-count">{sessions.length}</span>
          </div>
          <button
            className={`tree-row${activeTab === 'chat' && activeSessionId === null ? ' is-active' : ''}`}
            onClick={() => open('chat')}
          >
            <span className="tree-icon">+</span>
            <span>New session</span>
            <span />
          </button>
          {sessions.map((session) => (
            <button
              key={session.session_id}
              className={`tree-row${activeSessionId === session.session_id ? ' is-active' : ''}`}
              onClick={() => open('chat', session.session_id)}
              disabled={session.status === 'invalid'}
            >
              <span className="tree-icon">C</span>
              <span>{session.title}</span>
              <span className="tree-count">
                {session.status === 'complete' ? 'done' : `${session.question_count}/${session.max_questions}`}
              </span>
            </button>
          ))}

          <button
            className={`tree-row${activeTab === 'sources' ? ' is-active' : ''}`}
            onClick={() => open('sources')}
          >
            <span className="tree-icon">S</span>
            <span>Sources</span>
            <span className="tree-count">{domain.source_files.length}</span>
          </button>
          <button
            className={`tree-row${activeTab === 'graph' ? ' is-active' : ''}`}
            onClick={() => open('graph')}
          >
            <span className="tree-icon">G</span>
            <span>Curriculum Graph</span>
            <span />
          </button>
          <button
            className={`tree-row${activeTab === 'scratchpad' ? ' is-active' : ''}`}
            onClick={() => open('scratchpad')}
          >
            <span className="tree-icon">P</span>
            <span>Scratchpad</span>
            <span />
          </button>
        </div>
      )}
    </section>
  );
}
