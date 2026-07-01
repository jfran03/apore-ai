import { ConnectionStatusPill } from './ConnectionStatusPill';
import type { ConnectionStatus } from '../hooks/useBackend';

interface DesktopTitlebarProps {
  status: ConnectionStatus;
  onRefresh: () => void;
}

// Native window controls are wired through @tauri-apps/api when running inside
// the desktop shell; in a plain browser they degrade to no-ops.
async function windowAction(action: 'minimize' | 'toggleMaximize' | 'close') {
  try {
    const { getCurrentWindow } = await import('@tauri-apps/api/window');
    const win = getCurrentWindow();
    if (action === 'minimize') await win.minimize();
    else if (action === 'toggleMaximize') await win.toggleMaximize();
    else await win.close();
  } catch {
    // Not running under Tauri (e.g. browser dev) — ignore.
  }
}

export function DesktopTitlebar({ status, onRefresh }: DesktopTitlebarProps) {
  return (
    <header className="desktop-titlebar" data-tauri-drag-region>
      <div className="titlebar-left">
        <div className="brand">
          <span className="brand-mark">A</span>
          <span>Apore</span>
        </div>

        <div className="menu-bar" aria-label="Application menu">
          <span>File</span>
          <span>Edit</span>
          <span>View</span>
          <span>Help</span>
        </div>
      </div>

      <div className="titlebar-right top-actions">
        <ConnectionStatusPill status={status} onRefresh={onRefresh} />
        <div className="window-controls" aria-label="Window controls">
          <button
            className="window-button"
            aria-label="Minimize"
            onClick={() => windowAction('minimize')}
          >
            -
          </button>
          <button
            className="window-button"
            aria-label="Maximize"
            onClick={() => windowAction('toggleMaximize')}
          >
            □
          </button>
          <button
            className="window-button close"
            aria-label="Close"
            onClick={() => windowAction('close')}
          >
            ×
          </button>
        </div>
      </div>
    </header>
  );
}
