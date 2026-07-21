import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import {
  approveCompile,
  getChapterArtifact,
  startCompile,
} from '../../api/client';
import type { ChapterArtifactStatus } from '../../api/types';
import { DURATION, EASE_OUT } from '../../motion';
import { useActiveDomain } from '../../shell/ActiveDomainContext';
import { ChapterRail } from './ChapterRail';
import { SourcesPanel } from './SourcesPanel';
import { CompiledWikiPanel } from './CompiledWikiPanel';
import { QuestionBankPanel } from './QuestionBankPanel';

type Tab = 'sources' | 'wiki' | 'questions';

const ACTIVE_STAGES = ['normalizing', 'compiling', 'validating'];
const POLL_INTERVAL_MS = 1200;

const TABS: { id: Tab; label: string }[] = [
  { id: 'sources', label: 'Sources' },
  { id: 'wiki', label: 'Compiled wiki' },
  { id: 'questions', label: 'Question bank' },
];

export function DomainSetupWorkbench() {
  const { activeDomain, activeChapter, catalogLoading, refreshCatalog } = useActiveDomain();
  const [tab, setTab] = useState<Tab>('sources');
  const [artifact, setArtifact] = useState<ChapterArtifactStatus | null>(null);
  const pollRef = useRef<number | null>(null);
  const reduceMotion = useReducedMotion();

  const knowledgeSource = activeChapter?.knowledge_source ?? null;

  const stopPolling = useCallback(() => {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const refreshArtifact = useCallback(async () => {
    if (!knowledgeSource) return;
    try {
      const data = await getChapterArtifact(knowledgeSource);
      setArtifact(data);
      return data;
    } catch {
      setArtifact(null);
    }
  }, [knowledgeSource]);

  const startPolling = useCallback(() => {
    if (!knowledgeSource) return;
    stopPolling();
    pollRef.current = window.setInterval(async () => {
      const data = await refreshArtifact();
      if (data && !ACTIVE_STAGES.includes(data.compile.stage)) {
        stopPolling();
        refreshCatalog().catch(() => undefined);
      }
    }, POLL_INTERVAL_MS);
  }, [knowledgeSource, refreshArtifact, refreshCatalog, stopPolling]);

  useEffect(() => {
    setArtifact(null);
    stopPolling();
    if (!knowledgeSource) return;
    refreshArtifact().then((data) => {
      if (data && ACTIVE_STAGES.includes(data.compile.stage)) startPolling();
    });
    return () => stopPolling();
  }, [knowledgeSource, refreshArtifact, startPolling, stopPolling]);

  const handleCompile = useCallback(async () => {
    if (!knowledgeSource) return;
    await startCompile(knowledgeSource);
    setTab('wiki');
    await refreshArtifact();
    startPolling();
  }, [knowledgeSource, refreshArtifact, startPolling]);

  const handleApprove = useCallback(async () => {
    if (!knowledgeSource) return;
    const status = await approveCompile(knowledgeSource);
    setArtifact(status);
    await refreshCatalog().catch(() => undefined);
  }, [knowledgeSource, refreshCatalog]);

  const handleSourcesChanged = useCallback(async () => {
    await refreshArtifact();
    await refreshCatalog().catch(() => undefined);
  }, [refreshArtifact, refreshCatalog]);

  if (!catalogLoading && !activeDomain) {
    return (
      <div className="wb-empty wb-empty--page">
        <h2>No domain selected</h2>
        <p>Create a domain from the sidebar to begin setting up chapters.</p>
        <Link to="/study" className="btn btn--secondary">
          Go to Study
        </Link>
      </div>
    );
  }

  const canGenerate = Boolean(
    artifact?.is_approved && !artifact.is_stale && artifact.concept_count > 0,
  );
  let generateBlockedReason: string | null = null;
  if (!canGenerate) {
    if (!artifact?.is_approved) {
      generateBlockedReason = 'Approve a compiled wiki before generating questions.';
    } else if (artifact.is_stale) {
      generateBlockedReason = 'Sources changed since approval. Recompile and approve first.';
    } else {
      generateBlockedReason = 'Compile and approve a wiki with concepts before generating.';
    }
  }

  const tabTransition = {
    duration: reduceMotion ? 0 : DURATION.enter,
    ease: EASE_OUT,
  };

  return (
    <div className="wb">
      <ChapterRail />
      <div className="wb-main">
        {!activeChapter ? (
          <div className="wb-empty wb-empty--page">
            <h2>No chapter selected</h2>
            <p>Create a chapter with the + button in the chapter list to get started.</p>
          </div>
        ) : (
          <>
            <div className="wb-tabs" role="tablist" aria-label="Chapter workspace">
              {TABS.map((t) => (
                <button
                  key={t.id}
                  role="tab"
                  type="button"
                  aria-selected={tab === t.id}
                  className={`wb-tab${tab === t.id ? ' wb-tab--active' : ''}`}
                  onClick={() => setTab(t.id)}
                >
                  {t.label}
                </button>
              ))}
            </div>

            <div className="wb-tabpanel" role="tabpanel">
              <AnimatePresence mode="wait" initial={false}>
                {tab === 'sources' && knowledgeSource && (
                  <motion.div
                    key="sources"
                    initial={reduceMotion ? false : { opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={reduceMotion ? undefined : { opacity: 0, y: -4 }}
                    transition={tabTransition}
                  >
                    <SourcesPanel
                      knowledgeSource={knowledgeSource}
                      compileStage={artifact?.compile.stage ?? 'idle'}
                      onSourcesChanged={handleSourcesChanged}
                      onCompile={handleCompile}
                    />
                  </motion.div>
                )}
                {tab === 'wiki' && knowledgeSource && (
                  <motion.div
                    key="wiki"
                    initial={reduceMotion ? false : { opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={reduceMotion ? undefined : { opacity: 0, y: -4 }}
                    transition={tabTransition}
                  >
                    <CompiledWikiPanel
                      knowledgeSource={knowledgeSource}
                      artifact={artifact}
                      onApprove={handleApprove}
                      onRetryCompile={handleCompile}
                    />
                  </motion.div>
                )}
                {tab === 'questions' && knowledgeSource && (
                  <motion.div
                    key="questions"
                    initial={reduceMotion ? false : { opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={reduceMotion ? undefined : { opacity: 0, y: -4 }}
                    transition={tabTransition}
                  >
                    <QuestionBankPanel
                      knowledgeSource={knowledgeSource}
                      canGenerate={canGenerate}
                      generateBlockedReason={generateBlockedReason}
                      onGenerated={() => refreshCatalog().catch(() => undefined)}
                    />
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
