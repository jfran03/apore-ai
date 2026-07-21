import { Outlet, useLocation } from 'react-router-dom';
import { ApiKeyGate } from './ApiKeyGate';
import { StudyFocusProvider } from './StudyFocusContext';
import { TopBar } from './TopBar';
import '../styles/shell.css';

export function AppShell() {
  const { pathname } = useLocation();
  const landing = pathname === '/';

  return (
    <StudyFocusProvider>
      <div className={`shell${landing ? ' shell--landing' : ''}`}>
        <TopBar />
        <div className="shell__body">
          <div className="shell__content">
            <Outlet />
          </div>
        </div>
        <ApiKeyGate />
      </div>
    </StudyFocusProvider>
  );
}
