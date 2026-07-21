import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { deleteDomain, renameDomain } from '../api/client';
import type { SessionSummary } from '../api/types';
import { CreateDomainModal } from './CreateDomainModal';
import { parseKnowledgeSource, useActiveDomain } from './ActiveDomainContext';

const VISIBLE_SESSIONS = 5;

function NewDomainAction() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        className="sidebar__new-session"
        onClick={() => setOpen(true)}
      >
        <span aria-hidden="true">⊕</span> New Domain
      </button>
      <CreateDomainModal open={open} onClose={() => setOpen(false)} />
    </>
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

function MoreIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
    >
      <circle cx="12" cy="5" r="1.75" />
      <circle cx="12" cy="12" r="1.75" />
      <circle cx="12" cy="19" r="1.75" />
    </svg>
  );
}

function DomainRow({
  domainId,
  active,
  sessions,
  onSelect,
  onSessionsChanged,
}: {
  domainId: string;
  active: boolean;
  sessions: SessionSummary[];
  onSelect: () => void;
  onSessionsChanged: () => Promise<void>;
}) {
  const { setActiveDomainId, refreshCatalog } = useActiveDomain();
  const [menuOpen, setMenuOpen] = useState(false);
  const [menuPos, setMenuPos] = useState<{ top: number; right: number } | null>(null);
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(domainId);
  const [pendingDelete, setPendingDelete] = useState(false);
  const [busy, setBusy] = useState(false);
  const [rowError, setRowError] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const renameInputRef = useRef<HTMLInputElement>(null);
  const deleteCancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (editing) renameInputRef.current?.focus();
  }, [editing]);

  useEffect(() => {
    if (!menuOpen) {
      setMenuPos(null);
      return;
    }
    const updatePos = () => {
      const rect = triggerRef.current?.getBoundingClientRect();
      if (!rect) return;
      setMenuPos({
        top: rect.bottom + 4,
        right: window.innerWidth - rect.right,
      });
    };
    updatePos();
    function onMouseDown(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') setMenuOpen(false);
    }
    document.addEventListener('mousedown', onMouseDown);
    document.addEventListener('keydown', onKeyDown);
    window.addEventListener('resize', updatePos);
    window.addEventListener('scroll', updatePos, true);
    return () => {
      document.removeEventListener('mousedown', onMouseDown);
      document.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('resize', updatePos);
      window.removeEventListener('scroll', updatePos, true);
    };
  }, [menuOpen]);

  useEffect(() => {
    if (!pendingDelete) return;
    deleteCancelRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !busy) {
        setPendingDelete(false);
        setDeleteError(null);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [pendingDelete, busy]);

  const startRename = () => {
    setMenuOpen(false);
    setEditing(true);
    setEditValue(domainId);
    setRowError(null);
  };

  const cancelRename = () => {
    setEditing(false);
    setEditValue(domainId);
    setRowError(null);
  };

  const handleRename = async () => {
    const nextId = editValue.trim();
    if (!nextId) return;
    if (nextId === domainId) {
      cancelRename();
      return;
    }
    setBusy(true);
    setRowError(null);
    try {
      await renameDomain(domainId, nextId);
      await refreshCatalog();
      await onSessionsChanged();
      setActiveDomainId(nextId);
      setEditing(false);
    } catch (err) {
      setRowError(err instanceof Error ? err.message : 'Could not rename domain');
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async () => {
    setBusy(true);
    setDeleteError(null);
    try {
      await deleteDomain(domainId);
      setPendingDelete(false);
      if (editing) cancelRename();
      await refreshCatalog();
      await onSessionsChanged();
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : 'Could not delete domain');
    } finally {
      setBusy(false);
    }
  };

  if (editing) {
    return (
      <li>
        <form
          className="sidebar__domain-rename"
          onSubmit={(e) => {
            e.preventDefault();
            handleRename();
          }}
        >
          <input
            ref={renameInputRef}
            className="sidebar__new-domain-input"
            value={editValue}
            disabled={busy}
            onChange={(e) => setEditValue(e.target.value)}
            aria-label={`Rename domain ${domainId}`}
          />
          <div className="sidebar__new-domain-actions">
            <button type="button" className="btn btn--ghost" disabled={busy} onClick={cancelRename}>
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn--primary"
              disabled={busy || !editValue.trim()}
            >
              Save
            </button>
          </div>
          {rowError && <p className="sidebar__new-domain-error">{rowError}</p>}
        </form>
        <SessionRows sessions={sessions} />
      </li>
    );
  }

  return (
    <li>
      <div className={`sidebar__domain-row${active ? ' sidebar__domain-row--active' : ''}`}>
        <button
          type="button"
          className={`sidebar__domain${active ? ' sidebar__domain--active' : ''}`}
          onClick={onSelect}
        >
          {domainId}
        </button>
        <div className="sidebar__domain-menu" ref={menuRef}>
          <button
            ref={triggerRef}
            type="button"
            className="sidebar__domain-menu-trigger"
            aria-label={`Domain actions for ${domainId}`}
            aria-expanded={menuOpen}
            aria-haspopup="menu"
            disabled={busy}
            onClick={() => setMenuOpen((v) => !v)}
          >
            <MoreIcon />
          </button>
          {menuOpen && menuPos && (
            <div
              className="sidebar__domain-menu-panel"
              role="menu"
              aria-label={`Actions for ${domainId}`}
              style={{ top: menuPos.top, right: menuPos.right }}
            >
              <button
                type="button"
                role="menuitem"
                className="sidebar__domain-menu-item"
                onClick={startRename}
              >
                Rename domain
              </button>
              <button
                type="button"
                role="menuitem"
                className="sidebar__domain-menu-item sidebar__domain-menu-item--danger"
                onClick={() => {
                  setMenuOpen(false);
                  setPendingDelete(true);
                  setDeleteError(null);
                }}
              >
                Delete domain
              </button>
            </div>
          )}
        </div>
      </div>
      <SessionRows sessions={sessions} />

      {pendingDelete && (
        <div
          className="sidebar__modal"
          role="presentation"
          onClick={(e) => {
            if (e.target === e.currentTarget && !busy) {
              setPendingDelete(false);
              setDeleteError(null);
            }
          }}
        >
          <div
            className="sidebar__modal-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby={`domain-delete-title-${domainId}`}
          >
            <h3 id={`domain-delete-title-${domainId}`} className="sidebar__modal-title">
              Delete domain?
            </h3>
            <p className="sidebar__modal-body">
              Deleting <strong>{domainId}</strong> permanently removes everything downstream:
              chapters, sources, compiled wiki, concept graphs, question banks, and all study
              sessions under this domain.
            </p>
            {deleteError && <p className="sidebar__modal-error">{deleteError}</p>}
            <div className="sidebar__modal-actions">
              <button
                ref={deleteCancelRef}
                type="button"
                className="btn btn--ghost"
                disabled={busy}
                onClick={() => {
                  setPendingDelete(false);
                  setDeleteError(null);
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn--danger"
                disabled={busy}
                onClick={handleDelete}
              >
                {busy ? 'Deleting…' : 'Delete domain'}
              </button>
            </div>
          </div>
        </div>
      )}
    </li>
  );
}

export function Sidebar() {
  const {
    catalog,
    activeDomainId,
    setActiveDomainId,
    sessions,
    sessionsLoaded,
    refreshSessions,
  } = useActiveDomain();

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
              <DomainRow
                key={d.id}
                domainId={d.id}
                active={d.id === activeDomainId}
                sessions={grouped.get(d.id) ?? []}
                onSelect={() => setActiveDomainId(d.id)}
                onSessionsChanged={refreshSessions}
              />
            ))}
          </ul>
        ) : (
          <DomainsSkeleton />
        )}
      </div>
    </aside>
  );
}
