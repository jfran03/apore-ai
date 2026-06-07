import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  createChapter,
  createDomain,
  fetchFixture,
  getKnowledgeCatalog,
  setStoredKnowledgeSource,
  stubCompileChapter,
  uploadSources,
  getStoredKnowledgeSource,
} from '../api/client';
import type { KnowledgeCatalog } from '../api/types';
import '../styles/setup.css';

export function Setup() {
  const [catalog, setCatalog] = useState<KnowledgeCatalog | null>(null);
  const [knowledgeSource, setKnowledgeSource] = useState(getStoredKnowledgeSource());
  const [domainId, setDomainId] = useState('my-course');
  const [chapterId, setChapterId] = useState('01-intro');
  const [selectedDomain, setSelectedDomain] = useState('my-course');
  const [selectedChapter, setSelectedChapter] = useState('01-intro');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const data = await getKnowledgeCatalog();
    setCatalog(data);
  }, []);

  useEffect(() => {
    refresh().catch((err) => setError(err instanceof Error ? err.message : 'Failed to load catalog'));
  }, [refresh]);

  const aporeLite = catalog?.fixtures.find((f) => f.name === 'apore-lite');

  const activeChapter = catalog?.domains
    .find((d) => d.id === selectedDomain)
    ?.chapters.find((c) => c.id === selectedChapter);

  const handleSaveSource = () => {
    setStoredKnowledgeSource(knowledgeSource);
    setMessage('Study sessions will use this knowledge source.');
    setError(null);
  };

  const handleFetchFixture = async () => {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const result = await fetchFixture('apore-lite');
      const source = result.knowledge_source ?? 'domain:discrete-math/01-set-theory';
      setKnowledgeSource(source);
      setStoredKnowledgeSource(source);

      const parts = [
        result.status === 'fetched' ? 'Synced discrete-math from apore-lite' : 'Sync complete',
        `@ ${result.commit.slice(0, 12)}`,
      ];
      if (result.chapter_ready) {
        parts.push(`— ${result.nodes} concepts ready for Study`);
        if (result.bootstrap_status === 'bootstrapped') {
          parts.push('(built concept graph from wiki)');
        }
      } else {
        parts.push('— warning: no wiki chapter found to build a graph');
      }
      setMessage(parts.join(' '));
      await refresh();
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Fetch failed';
      if (msg.includes('git') || msg.includes('not found')) {
        setError(`${msg} — install Git and ensure it is on your PATH, then try again.`);
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleCreateDomain = async () => {
    setLoading(true);
    setError(null);
    try {
      await createDomain(domainId);
      setSelectedDomain(domainId);
      setMessage(`Created domain "${domainId}"`);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Create domain failed');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateChapter = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await createChapter(selectedDomain, chapterId);
      setSelectedChapter(chapterId);
      setKnowledgeSource(res.knowledge_source);
      setMessage(`Created chapter "${chapterId}"`);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Create chapter failed');
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (files: FileList | null) => {
    if (!files?.length) return;
    setLoading(true);
    setError(null);
    try {
      const res = await uploadSources(selectedDomain, selectedChapter, Array.from(files));
      setMessage(`Uploaded: ${res.uploaded.join(', ')}`);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setLoading(false);
    }
  };

  const handleStubCompile = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await stubCompileChapter(selectedDomain, selectedChapter);
      setMessage(`Stub compile: ${res.nodes} concepts, ${res.wiki_files} wiki pages`);
      setKnowledgeSource(`domain:${selectedDomain}/${selectedChapter}`);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Compile failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="setup-page">
      <h1 className="setup-page__title">Setup</h1>
      <p className="setup-page__lead">
        Choose grounding material for the tutor, upload your sources, and compile a concept graph
        before starting a study session.
      </p>

      <section className="setup-section" aria-labelledby="setup-knowledge-heading">
        <h2 id="setup-knowledge-heading" className="setup-section__heading">
          Knowledge source for Study
        </h2>
        <p className="setup-meta">
          Optional default for the Study page. Domain and chapter are chosen when you start a
          session on Study — saving here only pre-fills those choices.
        </p>
        <div className="setup-radio" role="radiogroup" aria-label="Knowledge source">
          {catalog?.domains.map((d) =>
            d.chapters.map((c) => (
              <label key={c.knowledge_source}>
                <input
                  type="radio"
                  name="knowledge"
                  value={c.knowledge_source}
                  checked={knowledgeSource === c.knowledge_source}
                  onChange={() => {
                    setKnowledgeSource(c.knowledge_source);
                    setSelectedDomain(d.id);
                    setSelectedChapter(c.id);
                  }}
                />
                <span>
                  {d.id} / {c.id}
                  {c.has_concept_graph ? ' — graph ready' : ' — needs compile'}
                </span>
              </label>
            )),
          )}
        </div>
        <div className="setup-row">
          <button type="button" className="btn btn--primary" onClick={handleSaveSource} disabled={loading}>
            Save for Study
          </button>
          <Link to="/study" className="btn btn--secondary">
            Go to Study
          </Link>
        </div>
        <p className="setup-meta">Current: {getStoredKnowledgeSource()}</p>
      </section>

      <section className="setup-section" aria-labelledby="setup-fixture-heading">
        <h2 id="setup-fixture-heading" className="setup-section__heading">
          apore-lite fixture
        </h2>
        <p className="setup-meta">
          {aporeLite?.description ?? 'Discrete math reference corpus for testing.'}
          {aporeLite?.fetched ? ` Commit ${aporeLite.commit.slice(0, 12)}…` : ' Not fetched yet.'}
        </p>
        <button
          type="button"
          className="btn btn--primary"
          onClick={handleFetchFixture}
          disabled={loading}
        >
          {loading ? 'Fetching…' : 'Fetch apore-lite'}
        </button>
      </section>

      <section className="setup-section" aria-labelledby="setup-domain-heading">
        <h2 id="setup-domain-heading" className="setup-section__heading">
          Your chapter
        </h2>
        <div className="setup-row">
          <input
            className="setup-input"
            value={domainId}
            onChange={(e) => setDomainId(e.target.value)}
            placeholder="domain id"
            aria-label="Domain id"
          />
          <button type="button" className="btn btn--secondary" onClick={handleCreateDomain} disabled={loading}>
            Create domain
          </button>
        </div>
        <div className="setup-row">
          <input
            className="setup-input"
            value={chapterId}
            onChange={(e) => setChapterId(e.target.value)}
            placeholder="chapter id"
            aria-label="Chapter id"
          />
          <button type="button" className="btn btn--secondary" onClick={handleCreateChapter} disabled={loading}>
            Create chapter
          </button>
        </div>
        <p className="setup-meta">
          Working on: {selectedDomain} / {selectedChapter}
        </p>
        <div className="setup-row">
          <label className="btn btn--secondary">
            Upload sources
            <input
              type="file"
              multiple
              hidden
              onChange={(e) => handleUpload(e.target.files)}
            />
          </label>
          <button type="button" className="btn btn--primary" onClick={handleStubCompile} disabled={loading}>
            Stub compile
          </button>
        </div>
        {activeChapter && (
          <ul className="setup-checklist">
            <li data-ok={activeChapter.sources_present ? 'true' : 'false'}>
              Sources ({activeChapter.source_count} files)
            </li>
            <li data-ok={activeChapter.has_concept_graph ? 'true' : 'false'}>
              concept-graph.json
            </li>
            <li data-ok={activeChapter.wiki_count > 0 ? 'true' : 'false'}>
              wiki pages ({activeChapter.wiki_count})
            </li>
          </ul>
        )}
        {activeChapter?.source_files && activeChapter.source_files.length > 0 && (
          <ul className="setup-file-list">
            {activeChapter.source_files.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        )}
      </section>

      {message && <p className="setup-success">{message}</p>}
      {error && <p className="setup-error">{error}</p>}
    </main>
  );
}
