import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { TopBar } from './TopBar';
import { Sidebar } from './Sidebar';
import '../styles/shell.css';

const SIDEBAR_COLLAPSED_KEY = 'apore.sidebar_collapsed';

export function AppShell() {
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === '1',
  );

  const toggleSidebar = () => {
    setCollapsed((prev) => {
      localStorage.setItem(SIDEBAR_COLLAPSED_KEY, prev ? '0' : '1');
      return !prev;
    });
  };

  return (
    <div className="shell">
      <TopBar collapsed={collapsed} onToggleSidebar={toggleSidebar} />
      <div className="shell__body">
        {!collapsed && <Sidebar />}
        <div className="shell__content">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
