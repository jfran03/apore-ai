import { NavLink } from 'react-router-dom';
import { useActiveDomain } from './ActiveDomainContext';

const MENU_ITEMS = [
  { to: '/study', label: 'Study' },
  { to: '/questions', label: 'Questions' },
  { to: '/runs', label: 'Runs' },
  { to: '/graph', label: 'Graph' },
] as const;

interface TopBarProps {
  collapsed: boolean;
  onToggleSidebar: () => void;
}

export function TopBar({ collapsed, onToggleSidebar }: TopBarProps) {
  const { activeDomainId } = useActiveDomain();
  return (
    <header className="topbar">
      <div className="topbar__left">
        <button
          type="button"
          className="topbar__hamburger"
          onClick={onToggleSidebar}
          aria-label={collapsed ? 'Open sidebar' : 'Close sidebar'}
          aria-expanded={!collapsed}
        >
          ☰
        </button>
        <span className="topbar__domain">{activeDomainId ?? '—'}</span>
      </div>
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
      <div className="topbar__right">{/* Settings cog lands here in Task 8 */}</div>
    </header>
  );
}
