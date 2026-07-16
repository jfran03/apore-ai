import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { listSessions } from '../api/client';
import type { SessionSummary } from '../api/types';
import { parseKnowledgeSource, useActiveDomain } from './ActiveDomainContext';

const VISIBLE_SESSIONS = 5;

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
  const { catalog, catalogError, activeDomainId, setActiveDomainId } = useActiveDomain();
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [sessionsError, setSessionsError] = useState<string | null>(null);

  useEffect(() => {
    listSessions()
      .then((res) => setSessions(res.sessions))
      .catch((err) =>
        setSessionsError(err instanceof Error ? err.message : 'Failed to load sessions'),
      );
  }, []);

  const grouped = useMemo(() => {
    const byDomain = new Map<string, SessionSummary[]>();
    const other: SessionSummary[] = [];
    for (const s of sessions) {
      const parsed = parseKnowledgeSource(s.knowledge_source);
      if (parsed) {
        const list = byDomain.get(parsed.domainId) ?? [];
        list.push(s);
        byDomain.set(parsed.domainId, list);
      } else {
        other.push(s);
      }
    }
    return { byDomain, other };
  }, [sessions]);

  return (
    <aside className="sidebar" aria-label="Learning domains">
      <div className="sidebar__top">
        <Link to="/study" className="sidebar__new-session">
          <span aria-hidden="true">⊕</span> New Session
        </Link>
      </div>
      <div className="sidebar__section">
        <p className="sidebar__section-title">Domains</p>
        {catalogError && <p className="sidebar__error">{catalogError}</p>}
        {sessionsError && <p className="sidebar__error">{sessionsError}</p>}
        <ul className="sidebar__domains">
          {catalog?.domains.map((d) => (
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
              <SessionRows sessions={grouped.byDomain.get(d.id) ?? []} />
            </li>
          ))}
        </ul>
        {grouped.other.length > 0 && (
          <>
            <p className="sidebar__section-title">Other</p>
            <SessionRows sessions={grouped.other} />
          </>
        )}
      </div>
      <div className="sidebar__footer">
        <Link to="/setup" className="sidebar__footer-link">
          Setup
        </Link>
      </div>
    </aside>
  );
}
