import type { ConnectionStatus } from '../hooks/useBackend';

interface ConnectionStatusPillProps {
  status: ConnectionStatus;
  onRefresh: () => void;
}

const LABELS: Record<ConnectionStatus, string> = {
  checking: 'Connecting to backend…',
  online: 'Backend connected',
  offline: 'Backend offline',
};

export function ConnectionStatusPill({ status, onRefresh }: ConnectionStatusPillProps) {
  return (
    <button
      className="status-strip"
      onClick={onRefresh}
      title="Re-check the local backend connection"
      style={{ background: 'transparent', border: 0 }}
    >
      <span className={`status-dot is-${status}`} />
      <span>{LABELS[status]}</span>
    </button>
  );
}
