import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { MotionConfig } from 'framer-motion';
import { AppShell } from './shell/AppShell';
import { ActiveDomainProvider } from './shell/ActiveDomainContext';
import { Home } from './pages/Home';
import { Study } from './pages/Study';
import { Setup } from './pages/Setup';
import { Settings } from './pages/Settings';
import { Questions } from './pages/Questions';
import { SessionTranscriptPage } from './pages/SessionTranscript';
import './styles/global.css';
import './styles/components.css';

export function App() {
  return (
    <MotionConfig reducedMotion="user">
      <BrowserRouter>
        <ActiveDomainProvider>
          <Routes>
            <Route element={<AppShell />}>
              <Route path="/" element={<Home />} />
              <Route path="/setup" element={<Setup />} />
              <Route path="/questions" element={<Questions />} />
              <Route path="/study" element={<Study />} />
              <Route path="/sessions/:id" element={<SessionTranscriptPage />} />
              <Route path="/settings" element={<Settings />} />
              <Route
                path="/runs"
                element={<PlaceholderPage title="Runs" note="Run history — coming soon." />}
              />
              <Route
                path="/graph"
                element={<PlaceholderPage title="Graph" note="Knowledge graph — coming soon." />}
              />
            </Route>
          </Routes>
        </ActiveDomainProvider>
      </BrowserRouter>
    </MotionConfig>
  );
}

function PlaceholderPage({ title, note }: { title: string; note: string }) {
  return (
    <main className="page">
      <h1 className="page__title">{title}</h1>
      <p className="page__subtitle">{note}</p>
    </main>
  );
}
