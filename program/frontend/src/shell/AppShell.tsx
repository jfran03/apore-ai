import { Outlet, useLocation } from 'react-router-dom';
import { ApiKeyGate } from './ApiKeyGate';
import { StudyFocusProvider, useStudyFocus } from './StudyFocusContext';
import { TopBar } from './TopBar';
import '../styles/shell.css';

function ShellFrame() {
  const { pathname } = useLocation();
  const { focusMode } = useStudyFocus();
  const landing = pathname === '/';
  const scratchpadFocused = focusMode === 'scratchpad';

  return (
    <div
      className={[
        'shell',
        landing ? 'shell--landing' : '',
        scratchpadFocused ? 'shell--scratchpad-focused' : '',
      ]
        .filter(Boolean)
        .join(' ')}
    >
      <TopBar />
      <div className="shell__body">
        <div className="shell__content">
          <Outlet />
        </div>
      </div>
      <ApiKeyGate />
    </div>
  );
}

export function AppShell() {
  return (
    <StudyFocusProvider>
      <ShellFrame />
    </StudyFocusProvider>
  );
}
