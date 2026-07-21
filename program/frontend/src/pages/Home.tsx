import { Navigate, useNavigate } from 'react-router-dom';
import {
  isOnboardingComplete,
  setOnboardingComplete,
} from '../api/client';
import { useActiveDomain } from '../shell/ActiveDomainContext';
import logoUrl from '../assets/logo-no-bg.png';
import '../styles/home.css';

function formatChapterLabel(chapterId: string): string {
  const match = chapterId.match(/^(\d+)/);
  if (match) return `chapter ${Number(match[1])}`;
  return chapterId.replace(/-/g, ' ');
}

export function Home() {
  const navigate = useNavigate();
  const {
    catalog,
    catalogError,
    catalogLoading,
    selectDomainChapter,
  } = useActiveDomain();

  if (isOnboardingComplete()) {
    return <Navigate to="/study" replace />;
  }

  function handleSelectChapter(domainId: string, chapterId: string) {
    selectDomainChapter(domainId, chapterId);
    setOnboardingComplete();
    navigate('/study');
  }

  return (
    <main className="home">
      <header className="home__hero">
        <img
          className="home__logo"
          src={logoUrl}
          alt=""
          width={56}
          height={56}
        />
        <div className="home__hero-copy">
          <h1 className="home__title">Welcome back</h1>
        </div>
      </header>

      {catalogLoading && (
        <div className="home__status" role="status">
          Loading domains…
        </div>
      )}

      {!catalogLoading && catalogError && (
        <div className="home__status home__status--error" role="alert">
          {catalogError}
        </div>
      )}

      {!catalogLoading && !catalogError && catalog && catalog.domains.length === 0 && (
        <div className="home__status" role="status">
          No domains yet. Create one from Setup after you open a chapter.
        </div>
      )}

      {!catalogLoading && !catalogError && catalog && catalog.domains.length > 0 && (
        <div className="home__domains">
          {catalog.domains.map((domain) => (
            <section key={domain.id} className="home__domain" aria-labelledby={`domain-${domain.id}`}>
              <h2 id={`domain-${domain.id}`} className="home__domain-title">
                {domain.id}
              </h2>
              {domain.chapters.length === 0 ? (
                <p className="home__empty-chapters">No chapters in this domain.</p>
              ) : (
                <ul className="home__chapters">
                  {domain.chapters.map((chapter) => (
                    <li key={chapter.id}>
                      <button
                        type="button"
                        className="home__chapter"
                        onClick={() => handleSelectChapter(domain.id, chapter.id)}
                      >
                        {formatChapterLabel(chapter.id)}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          ))}
        </div>
      )}
    </main>
  );
}
