import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { createDomain, listSessions } from '../api/client';
import type { SessionSummary } from '../api/types';
import { parseKnowledgeSource, useActiveDomain } from './ActiveDomainContext';

const VISIBLE_SESSIONS = 5;

function NewDomainAction() {
  const { setActiveDomainId, refreshCatalog } = useActiveDomain();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [domainId, setDomainId] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCreate = async () => {
    const id = domainId.trim();
    if (!id) return;
    setBusy(true);
    setError(null);
    try {
      await createDomain(id);
      await refreshCatalog();
      setActiveDomainId(id);
      setDomainId('');
      setOpen(false);
      navigate('/setup');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create domain');
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <button
        type="button"
        className="sidebar__new-session"
        onClick={() => setOpen(true)}
      >
        <span aria-hidden="true">⊕</span> New Domain
      </button>
    );
  }

  return (
    <form
      className="sidebar__new-domain"
      onSubmit={(e) => {
        e.preventDefault();
        handleCreate();
      }}
    >
      <input
        className="sidebar__new-domain-input"
        value={domainId}
        autoFocus
        placeholder="domain-id"
        disabled={busy}
        onChange={(e) => setDomainId(e.target.value)}
        aria-label="New domain id"
      />
      <div className="sidebar__new-domain-actions">
        <button type="submit" className="btn btn--primary" disabled={busy || !domainId.trim()}>
          Create
        </button>
        <button
          type="button"
          className="btn btn--ghost"
          disabled={busy}
          onClick={() => {
            setOpen(false);
            setError(null);
          }}
        >
          Cancel
        </button>
      </div>
      {error && <p className="sidebar__new-domain-error">{error}</p>}
    </form>
  );
}

export function formatRelativeAge(iso: string): string {
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return '';
  const seconds = Math.max(0, (Date.now() - then) / 1000);
  const days = seconds / 86400;
  if (days < 1) {
    const hours = Math.floor(seconds / 3600);
    return hours < 1 ? 'now' : `${hours}h`;
  }
  if (days < 30) return `${Math.floor(days)}d`;
  return `${Math.floor(days / 30)}mo`;
}

function DomainsSkeleton() {
  return (
    <div className="sidebar__skeleton" aria-busy="true" aria-hidden="true">
      {[0, 1, 2].map((group) => (
        <div key={group} className="sidebar__skeleton-group">
          <div className="sidebar__skeleton-domain" />
          <div className="sidebar__skeleton-sessions">
            {[0, 1, 2].map((row) => (
              <div key={row} className="sidebar__skeleton-session">
                <span className="sidebar__skeleton-bone sidebar__skeleton-bone--title" />
                <span className="sidebar__skeleton-bone sidebar__skeleton-bone--age" />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function SessionRows({ sessions }: { sessions: SessionSummary[] }) {
  const [showAll, setShowAll] = useState(false);
  const visible = showAll ? sessions : sessions.slice(0, VISIBLE_SESSIONS);

  return (
    <ul className="sidebar__sessions">
      {visible.map((s) => {
        const chapterId = parseKnowledgeSource(s.knowledge_source)?.chapterId;
        return (
          <li key={s.session_id}>
            <Link to={`/sessions/${s.session_id}`} className="sidebar__session">
              <span className="sidebar__session-title" title={s.title}>
                {s.title}
              </span>
              {chapterId && <span className="sidebar__session-chapter">{chapterId}</span>}
              <span className="sidebar__session-age">{formatRelativeAge(s.created_at)}</span>
            </Link>
          </li>
        );
      })}
      {!showAll && sessions.length > VISIBLE_SESSIONS && (
        <li>
          <button
            type="button"
            className="sidebar__more"
            onClick={() => setShowAll(true)}
          >
            More…
          </button>
        </li>
      )}
    </ul>
  );
}

export function Sidebar() {
  const { catalog, activeDomainId, setActiveDomainId } = useActiveDomain();
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [sessionsLoaded, setSessionsLoaded] = useState(false);

  useEffect(() => {
    listSessions()
      .then((res) => {
        setSessions(res.sessions);
        setSessionsLoaded(true);
      })
      .catch(() => {
        // Keep the skeleton until a successful load; do not surface errors here.
      });
  }, []);

  const grouped = useMemo(() => {
    const byDomain = new Map<string, SessionSummary[]>();
    for (const s of sessions) {
      const parsed = parseKnowledgeSource(s.knowledge_source);
      if (parsed) {
        const list = byDomain.get(parsed.domainId) ?? [];
        list.push(s);
        byDomain.set(parsed.domainId, list);
      }
    }
    return byDomain;
  }, [sessions]);

  const ready = catalog !== null && sessionsLoaded;

  return (
    <aside className="sidebar" aria-label="Learning domains">
      <div className="sidebar__top">
        <NewDomainAction />
      </div>
      <div className="sidebar__section">
        <p className="sidebar__section-title">Domains</p>
        {ready ? (
          <ul className="sidebar__domains">
            {catalog.domains.map((d) => (
              <li key={d.id}>
                <button
                  type="button"
                  className={`sidebar__domain${
                    d.id === activeDomainId ? ' sidebar__domain--active' : ''
                  }`}
                  onClick={() => setActiveDomainId(d.id)}
                >
                  {d.id}
                </button>
                <SessionRows sessions={grouped.get(d.id) ?? []} />
              </li>
            ))}
          </ul>
        ) : (
          <DomainsSkeleton />
        )}
      </div>
    </aside>
  );
}
