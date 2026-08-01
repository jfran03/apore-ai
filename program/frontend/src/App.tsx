import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { MotionConfig } from 'framer-motion';
import { AppShell } from './shell/AppShell';
import { ActiveDomainProvider } from './shell/ActiveDomainContext';
import { Home } from './pages/Home';
import { Study } from './pages/Study';
import { Setup } from './pages/Setup';
import { Graph } from './pages/Graph';
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
              <Route path="/questions" element={<Navigate to="/setup" replace />} />
              <Route path="/study" element={<Study />} />
              <Route path="/sessions/:id" element={<SessionTranscriptPage />} />
              <Route path="/runs" element={<Navigate to="/" replace />} />
              <Route path="/graph" element={<Graph />} />
            </Route>
          </Routes>
        </ActiveDomainProvider>
      </BrowserRouter>
    </MotionConfig>
  );
}
