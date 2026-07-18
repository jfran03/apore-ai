import { Outlet } from 'react-router-dom';
import { ApiKeyGate } from './ApiKeyGate';
import { TopBar } from './TopBar';
import '../styles/shell.css';

export function AppShell() {
  return (
    <div className="shell">
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
