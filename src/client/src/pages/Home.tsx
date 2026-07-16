import { Link } from 'react-router-dom';

export function Home() {
  return (
    <main className="page">
      <h1 className="page__title">Apore</h1>
      <p className="page__subtitle">AI-powered tutoring prototype</p>
      <div style={{ marginTop: 'var(--spacing-xl)', display: 'flex', gap: 'var(--spacing-sm)' }}>
        <Link to="/study" className="btn btn--primary">
          Start studying
        </Link>
        <Link to="/settings" className="btn btn--ghost">
          Settings
        </Link>
      </div>
    </main>
  );
}
