import { NavLink } from 'react-router-dom';

const NAV_ITEMS = [
  { to: '/setup', label: 'Setup' },
  { to: '/study', label: 'Study' },
  { to: '/settings', label: 'Settings' },
  { to: '/runs', label: 'Runs' },
  { to: '/graph', label: 'Graph' },
] as const;

export function Nav() {
  return (
    <nav className="nav" aria-label="Main navigation">
      <NavLink to="/" className="nav__brand">
        Apore
      </NavLink>
      <ul className="nav__links">
        {NAV_ITEMS.map(({ to, label }) => (
          <li key={to}>
            <NavLink
              to={to}
              className={({ isActive }) =>
                `nav__link${isActive ? ' nav__link--active' : ''}`
              }
            >
              {label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
