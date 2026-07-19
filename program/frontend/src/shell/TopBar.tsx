import { useEffect, useRef, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { useActiveDomain } from './ActiveDomainContext';
import { SettingsPopover } from './SettingsPopover';
import { Sidebar } from './Sidebar';

const MENU_ITEMS = [
  { to: '/study', label: 'Study' },
  { to: '/setup', label: 'Setup' },
  { to: '/runs', label: 'Runs' },
  { to: '/graph', label: 'Graph' },
] as const;

export function TopBar() {
  const { activeDomain } = useActiveDomain();
  const [navOpen, setNavOpen] = useState(false);
  const navRef = useRef<HTMLDivElement>(null);

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

  return (
    <header className="topbar">
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
        {navOpen && (
          <div className="nav-popover__panel">
            <Sidebar />
          </div>
        )}
      </div>
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
        {activeDomain && (
          <span className="topbar__domain" title={activeDomain.id}>
            {activeDomain.id}
          </span>
        )}
      </div>
      <div className="topbar__right">
        <SettingsPopover />
      </div>
    </header>
  );
}
