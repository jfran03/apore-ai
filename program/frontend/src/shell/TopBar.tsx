import { useEffect, useRef, useState } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { popover } from '../motion';
import { useActiveDomain } from './ActiveDomainContext';
import { SettingsPopover } from './SettingsPopover';
import { Sidebar } from './Sidebar';
import { useStudyFocus } from './StudyFocusContext';

const MENU_ITEMS = [
  { to: '/study', label: 'Study' },
  { to: '/setup', label: 'Setup' },
  { to: '/graph', label: 'Graph' },
] as const;

export function TopBar() {
  const { activeDomain } = useActiveDomain();
  const { focused, focusMode, onExitRequest } = useStudyFocus();
  const { pathname } = useLocation();
  const landing = pathname === '/';
  const [navOpen, setNavOpen] = useState(false);
  const navRef = useRef<HTMLDivElement>(null);
  const reduceMotion = useReducedMotion();
  const panelMotion = popover(reduceMotion);

  useEffect(() => {
    if (!navOpen) return;
    function onMouseDown(e: MouseEvent) {
      if (navRef.current && !navRef.current.contains(e.target as Node)) {
        setNavOpen(false);
      }
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') setNavOpen(false);
    }
    document.addEventListener('mousedown', onMouseDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onMouseDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [navOpen]);

  useEffect(() => {
    if (landing || focused) setNavOpen(false);
  }, [landing, focused]);

  // Scratchpad owns Exit in its immersive toolbar; hide the global focused bar.
  if (focusMode === 'scratchpad') {
    return null;
  }

  if (focused) {
    return (
      <header className="topbar topbar--focused">
        <div className="topbar__left">
          <button
            type="button"
            className="topbar__exit"
            onClick={() => onExitRequest?.()}
            aria-label="Exit session"
          >
            Exit session
          </button>
        </div>
      </header>
    );
  }

  return (
    <header className={`topbar${landing ? ' topbar--landing' : ''}`}>
      {!landing && (
        <div className="topbar__left nav-popover" ref={navRef}>
          <button
            type="button"
            className="topbar__hamburger"
            onClick={() => setNavOpen((v) => !v)}
            aria-label={navOpen ? 'Close navigation' : 'Open navigation'}
            aria-expanded={navOpen}
          >
            ☰
          </button>
          <AnimatePresence>
            {navOpen && (
              <motion.div
                className="nav-popover__panel"
                initial={panelMotion.initial}
                animate={panelMotion.animate}
                exit={panelMotion.exit}
                transition={panelMotion.transition}
              >
                <Sidebar onNavigate={() => setNavOpen(false)} />
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}
      {!landing && (
        <div className="topbar__center">
          <nav className="topbar__menu" aria-label="Main navigation">
            {MENU_ITEMS.map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `topbar__link${isActive ? ' topbar__link--active' : ''}`
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
          {activeDomain && pathname !== '/graph' && (
            <Link
              to="/graph"
              className="topbar__domain"
              title={activeDomain.id}
              aria-label={`Open graph for ${activeDomain.id}`}
            >
              {activeDomain.id}
            </Link>
          )}
        </div>
      )}
      <div className="topbar__right">
        <SettingsPopover />
      </div>
    </header>
  );
}
