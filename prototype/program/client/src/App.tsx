import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Nav } from './components/Nav';
import { Home } from './pages/Home';
import { Study } from './pages/Study';
import { Settings } from './pages/Settings';
import './styles/global.css';
import './styles/components.css';

export function App() {
  return (
    <BrowserRouter>
      <Nav />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/study" element={<Study />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/runs" element={<PlaceholderPage title="Runs" note="Run history — coming soon." />} />
        <Route path="/graph" element={<PlaceholderPage title="Graph" note="Knowledge graph — coming soon." />} />
      </Routes>
    </BrowserRouter>
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
