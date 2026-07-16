import { Link } from 'react-router-dom';
import { useActiveDomain } from './ActiveDomainContext';

export function Sidebar() {
  const { catalog, catalogError, activeDomainId, setActiveDomainId } = useActiveDomain();

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
            </li>
          ))}
        </ul>
      </div>
      <div className="sidebar__footer">
        <Link to="/setup" className="sidebar__footer-link">
          Setup
        </Link>
      </div>
    </aside>
  );
}
