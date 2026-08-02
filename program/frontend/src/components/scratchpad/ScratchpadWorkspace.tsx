import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import type {
  FeedbackRegion,
  ScratchpadCamera,
  ScratchpadExportBounds,
  ScratchpadScenePayload,
} from '../../api/types';
import { putScratchpadScene } from '../../api/client';
import type { GradeResult } from '../SignalCapture';
import type { ChatStatus } from '../TutorChatCard';
import { ScratchpadPromptBar, type PromptBarPosition } from './ScratchpadPromptBar';
import {
  ScratchpadQuestionPanel,
  SCRATCHPAD_TOOLBAR_HEIGHT,
} from './ScratchpadQuestionPanel';
import type { ScratchpadCanvasHandle } from './ScratchpadCanvas';
import { exportKonvaSelection } from './scratchpadKonva';
import {
  createHistory,
  historyReducer,
  sceneToScreen,
  selectedExportBounds,
  type ScratchpadTool,
} from './scratchpadModel';

const ScratchpadCanvas = lazy(async () => {
  const module = await import('./ScratchpadCanvas');
  return { default: module.ScratchpadCanvas };
});

const DEFAULT_CAMERA: ScratchpadCamera = { x: 0, y: 0, scale: 1 };
const PROMPT_WIDTH = 420;
const PROMPT_HEIGHT = 52;
const BOTTOM_SAFE = 120;
const QUESTION_PREVIEW_ID = 'scratchpad-question-preview';

interface ScratchpadWorkspaceProps {
  sessionId: string;
  questionNumber: number;
  questionText: string;
  conceptLabel: string;
  maxQuestions: number;
  scalar: number;
  turnCount: number;
  initialScene: ScratchpadScenePayload | null;
  chatStatus: ChatStatus;
  pendingReveal: string | null;
  phase: 'dialogue' | 'rating' | 'reflection';
  graded: GradeResult | null;
  feedbackRegions: FeedbackRegion[];
  disabled: boolean;
  metaOpen: boolean;
  onMetaOpenChange: (open: boolean) => void;
  onExitSession: () => void;
  onAskSelection: (imageDataUri: string, prompt: string) => void | Promise<void>;
  onSubmitSelection: (imageDataUri: string) => void | Promise<void>;
  onSubmitRating: (rating: 'easy' | 'ok' | 'hard') => void | Promise<void>;
  onContinueToNext: () => void | Promise<void>;
  onSkip: () => void | Promise<void>;
  onRevealComplete: () => void;
  clearSceneToken: number;
}

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return (
    ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName) ||
    target.isContentEditable ||
    Boolean(target.closest('[contenteditable="true"]'))
  );
}

function cssColor(name: string, fallback: string): string {
  if (typeof document === 'undefined') return fallback;
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
}

function promptPosition(
  host: HTMLElement | null,
  bounds: ScratchpadExportBounds,
  camera: ScratchpadCamera,
  metaOpen: boolean,
  narrow: boolean,
): PromptBarPosition {
  const width = host?.clientWidth ?? 640;
  const height = host?.clientHeight ?? 480;
  if (narrow) {
    return {
      left: 12,
      top: Math.max(SCRATCHPAD_TOOLBAR_HEIGHT + 8, height - BOTTOM_SAFE - PROMPT_HEIGHT),
    };
  }
  const screen = sceneToScreen(
    { x: bounds.x + bounds.width, y: bounds.y + bounds.height / 2 },
    camera,
  );
  const rightReserve = metaOpen ? 296 : 16;
  return {
    left: Math.min(Math.max(64, screen.x + 12), Math.max(64, width - rightReserve - PROMPT_WIDTH)),
    top: Math.min(
      Math.max(SCRATCHPAD_TOOLBAR_HEIGHT + 8, screen.y - PROMPT_HEIGHT / 2),
      Math.max(SCRATCHPAD_TOOLBAR_HEIGHT + 8, height - BOTTOM_SAFE - PROMPT_HEIGHT),
    ),
  };
}

const toolItems: Array<{ tool: ScratchpadTool; label: string; shortcut: string }> = [
  { tool: 'select', label: 'Select', shortcut: 'V' },
  { tool: 'pen', label: 'Pen', shortcut: 'P' },
  { tool: 'rectangle', label: 'Rectangle', shortcut: 'R' },
  { tool: 'ellipse', label: 'Ellipse', shortcut: 'O' },
  { tool: 'text', label: 'Text', shortcut: 'T' },
  { tool: 'eraser', label: 'Object eraser', shortcut: 'E' },
  { tool: 'hand', label: 'Pan', shortcut: 'H' },
];

type ToolIconName = ScratchpadTool | 'undo' | 'redo';

function ToolIcon({ name }: { name: ToolIconName }) {
  let glyph: ReactNode;
  switch (name) {
    case 'select':
      glyph = <path d="M4 3.5 15.5 10l-5 1.4-2.8 4.5L4 3.5Z" />;
      break;
    case 'pen':
      glyph = (
        <>
          <path d="m5 14 1-4.2 6.8-6.8 3.2 3.2L9.2 13 5 14Z" />
          <path d="m11.8 4 3.2 3.2M4 16h12" />
        </>
      );
      break;
    case 'rectangle':
      glyph = <rect x="3.5" y="5" width="13" height="10" rx="1" />;
      break;
    case 'ellipse':
      glyph = <ellipse cx="10" cy="10" rx="6.5" ry="5" />;
      break;
    case 'text':
      glyph = <path d="M4 5h12M10 5v10M7 15h6" />;
      break;
    case 'eraser':
      glyph = (
        <>
          <path d="m5 13 6.8-8a1.4 1.4 0 0 1 2-.1l1.3 1.2a1.4 1.4 0 0 1 .1 2L9 15H6.8L5 13Z" />
          <path d="m9.5 7.7 4 3.5M9 15h7" />
        </>
      );
      break;
    case 'hand':
      glyph = <path d="M6.5 9V5.2a1.2 1.2 0 0 1 2.4 0V8m0-3.5a1.2 1.2 0 0 1 2.4 0V8m0-2.7a1.2 1.2 0 0 1 2.4 0v4.2m0-2.2a1.2 1.2 0 0 1 2.4 0v3.2c0 3.7-2.2 5.5-5.5 5.5H9.5c-1.5 0-2.8-.7-3.7-1.8l-2.1-2.7a1.3 1.3 0 0 1 2-1.7l.8.7" />;
      break;
    case 'undo':
      glyph = <path d="M7 6 3.5 9.5 7 13M4 9.5h7a5 5 0 0 1 5 5" />;
      break;
    case 'redo':
      glyph = <path d="m13 6 3.5 3.5L13 13m3-3.5H9a5 5 0 0 0-5 5" />;
      break;
  }
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {glyph}
    </svg>
  );
}

export function ScratchpadWorkspace({
  sessionId,
  questionNumber,
  questionText,
  conceptLabel,
  maxQuestions,
  scalar,
  turnCount,
  initialScene,
  chatStatus,
  pendingReveal,
  phase,
  graded,
  feedbackRegions,
  disabled,
  metaOpen,
  onMetaOpenChange,
  onExitSession,
  onAskSelection,
  onSubmitSelection,
  onSubmitRating,
  onContinueToNext,
  onSkip,
  onRevealComplete,
  clearSceneToken,
}: ScratchpadWorkspaceProps) {
  const initialNodes =
    initialScene?.question_number === questionNumber ? initialScene.nodes : [];
  const [history, dispatch] = useReducer(historyReducer, initialNodes, createHistory);
  const [camera, setCamera] = useState<ScratchpadCamera>(
    initialScene?.question_number === questionNumber
      ? initialScene.camera
      : DEFAULT_CAMERA,
  );
  const [exportBounds, setExportBounds] = useState<ScratchpadExportBounds | null>(
    initialScene?.question_number === questionNumber
      ? initialScene.last_export_bounds
      : null,
  );
  const [boundFeedbackRegions, setBoundFeedbackRegions] = useState<FeedbackRegion[]>(
    initialScene?.question_number === questionNumber
      ? initialScene.feedback_regions
      : feedbackRegions,
  );
  const [tool, setTool] = useState<ScratchpadTool>('pen');
  const [spacePan, setSpacePan] = useState(false);
  const [promptOpen, setPromptOpen] = useState(false);
  const [askPrompt, setAskPrompt] = useState('');
  const [pendingImage, setPendingImage] = useState<string | null>(null);
  const [selectionHint, setSelectionHint] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState(false);
  const [selectionCount, setSelectionCount] = useState(0);
  const [questionHovered, setQuestionHovered] = useState(false);
  const [questionFocused, setQuestionFocused] = useState(false);
  const [questionClickMode, setQuestionClickMode] = useState(false);
  const [questionClickOpen, setQuestionClickOpen] = useState(false);
  const [themeRevision, setThemeRevision] = useState(0);
  const [narrow, setNarrow] = useState(() =>
    typeof window !== 'undefined' && typeof window.matchMedia === 'function'
      ? window.matchMedia('(max-width: 959px)').matches
      : false,
  );
  const [position, setPosition] = useState<PromptBarPosition>({
    left: 72,
    top: SCRATCHPAD_TOOLBAR_HEIGHT + 16,
  });
  const hostRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<ScratchpadCanvasHandle | null>(null);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const saveInFlightRef = useRef<Promise<void> | null>(null);
  const lastSavedRef = useRef('');
  const latestPayloadRef = useRef<ScratchpadScenePayload | null>(null);
  const lastClearTokenRef = useRef(clearSceneToken);
  const busy = disabled || chatStatus !== 'idle';
  const questionPreviewOpen = questionClickMode
    ? questionClickOpen
    : questionHovered || questionFocused;
  const scenePayload = useMemo<ScratchpadScenePayload>(
    () => ({
      question_number: questionNumber,
      schema_version: 1,
      engine: 'apore-konva',
      nodes: history.present,
      camera,
      last_export_bounds: exportBounds,
      feedback_regions: boundFeedbackRegions,
    }),
    [boundFeedbackRegions, camera, exportBounds, history.present, questionNumber],
  );
  latestPayloadRef.current = scenePayload;

  const flushLatest = useCallback(async (): Promise<boolean> => {
    while (true) {
      if (saveInFlightRef.current) {
        await saveInFlightRef.current;
        continue;
      }
      const payload = latestPayloadRef.current;
      if (!payload) return true;
      const serialized = JSON.stringify(payload);
      if (serialized === lastSavedRef.current) return true;
      let succeeded = false;
      const request = putScratchpadScene(sessionId, payload)
        .then(() => {
          lastSavedRef.current = serialized;
          setSaveError(false);
          succeeded = true;
        })
        .catch(() => {
          setSaveError(true);
        });
      saveInFlightRef.current = request;
      await request;
      saveInFlightRef.current = null;
      if (!succeeded) {
        if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
        saveTimerRef.current = setTimeout(() => void flushLatest(), 2000);
        return false;
      }
    }
  }, [sessionId]);

  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return;
    const media = window.matchMedia('(max-width: 959px)');
    const update = () => setNarrow(media.matches);
    update();
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);

  useEffect(() => {
    const observer = new MutationObserver(() => setThemeRevision((value) => value + 1));
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme'],
    });
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (chatStatus !== 'revealing' || !pendingReveal) return;
    const timer = window.setTimeout(onRevealComplete, 40);
    return () => window.clearTimeout(timer);
  }, [chatStatus, onRevealComplete, pendingReveal]);

  useEffect(() => {
    setQuestionHovered(false);
    setQuestionFocused(false);
    setQuestionClickMode(false);
    setQuestionClickOpen(false);
  }, [questionNumber]);

  useEffect(() => {
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => void flushLatest(), 800);
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    };
  }, [flushLatest, scenePayload]);

  useEffect(
    () => () => {
      const payload = latestPayloadRef.current;
      if (!payload) return;
      const serialized = JSON.stringify(payload);
      if (serialized !== lastSavedRef.current) {
        void flushLatest();
      }
    },
    [flushLatest],
  );

  useEffect(() => {
    if (clearSceneToken === lastClearTokenRef.current) return;
    lastClearTokenRef.current = clearSceneToken;
    dispatch({ type: 'hydrate', nodes: [] });
    setCamera(DEFAULT_CAMERA);
    setExportBounds(null);
    setBoundFeedbackRegions([]);
    setPromptOpen(false);
    setPendingImage(null);
    setSelectionHint(null);
    lastSavedRef.current = '';
  }, [clearSceneToken]);

  useEffect(() => {
    if (!initialScene || initialScene.question_number !== questionNumber) return;
    dispatch({ type: 'hydrate', nodes: initialScene.nodes });
    setCamera(initialScene.camera);
    setExportBounds(initialScene.last_export_bounds);
    setBoundFeedbackRegions(initialScene.feedback_regions);
    lastSavedRef.current = JSON.stringify(initialScene);
  }, [initialScene, questionNumber]);

  useEffect(() => {
    setBoundFeedbackRegions(feedbackRegions);
  }, [feedbackRegions]);

  const closePrompt = useCallback(() => {
    setPromptOpen(false);
    setAskPrompt('');
  }, []);

  const openPrompt = useCallback(() => {
    if (busy || phase !== 'dialogue') return;
    if (history.selectedIds.length === 0) {
      setSelectionHint('Select the work you want to send, then press /.');
      return;
    }
    setSelectionHint(null);
    setExportError(null);
    try {
      const result = exportKonvaSelection(
        history.present,
        history.selectedIds,
        cssColor('--color-canvas-soft', '#f3f2ec'),
      );
      if (!result) return;
      setPendingImage(result.imageDataUri);
      setBoundFeedbackRegions([]);
      setExportBounds(result.bounds);
      setSelectionCount(history.selectedIds.length);
      setPosition(promptPosition(hostRef.current, result.bounds, camera, metaOpen, narrow));
      setPromptOpen(true);
    } catch (error) {
      setExportError(error instanceof Error ? error.message : 'Failed to export selection');
    }
  }, [busy, camera, history.present, history.selectedIds, metaOpen, narrow, phase]);

  useEffect(() => {
    function keyDown(event: KeyboardEvent) {
      if (isEditableTarget(event.target)) return;
      if (event.key === ' ') {
        event.preventDefault();
        setSpacePan(true);
        return;
      }
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'z') {
        event.preventDefault();
        dispatch({ type: event.shiftKey ? 'redo' : 'undo' });
        return;
      }
      if (event.key === 'Delete' || event.key === 'Backspace') {
        if (history.selectedIds.length > 0) {
          event.preventDefault();
          dispatch({ type: 'delete', ids: history.selectedIds });
        }
        return;
      }
      if (event.key === '/' && !event.metaKey && !event.ctrlKey && !event.altKey) {
        event.preventDefault();
        openPrompt();
        return;
      }
      if (
        (event.key === '[' || event.key === ']') &&
        history.selectedIds.length > 0
      ) {
        event.preventDefault();
        dispatch({
          type: 'reorder',
          ids: history.selectedIds,
          position: event.key === ']' ? 'front' : 'back',
        });
        return;
      }
      const item = toolItems.find(
        ({ shortcut }) => shortcut.toLowerCase() === event.key.toLowerCase(),
      );
      if (item && !event.metaKey && !event.ctrlKey && !event.altKey) setTool(item.tool);
    }
    const keyUp = (event: KeyboardEvent) => {
      if (event.key === ' ') setSpacePan(false);
    };
    document.addEventListener('keydown', keyDown);
    document.addEventListener('keyup', keyUp);
    return () => {
      document.removeEventListener('keydown', keyDown);
      document.removeEventListener('keyup', keyUp);
    };
  }, [history.selectedIds, openPrompt]);

  useEffect(() => {
    if (!promptOpen || !exportBounds) return;
    setPosition(promptPosition(hostRef.current, exportBounds, camera, metaOpen, narrow));
  }, [camera, exportBounds, metaOpen, narrow, promptOpen]);

  const handleAsk = useCallback(async () => {
    if (!pendingImage) return;
    if (!(await flushLatest())) return;
    setPromptOpen(false);
    await onAskSelection(pendingImage, askPrompt.trim());
    setAskPrompt('');
  }, [askPrompt, flushLatest, onAskSelection, pendingImage]);

  const handleSubmit = useCallback(async () => {
    if (!pendingImage) return;
    if (!(await flushLatest())) return;
    setPromptOpen(false);
    await onSubmitSelection(pendingImage);
    setAskPrompt('');
  }, [flushLatest, onSubmitSelection, pendingImage]);

  const selectionActionPosition = useMemo(() => {
    const bounds = selectedExportBounds(history.present, history.selectedIds, 0);
    if (!bounds) return undefined;
    const point = sceneToScreen(
      { x: bounds.x + bounds.width, y: bounds.y },
      camera,
    );
    return {
      left: Math.max(64, Math.min(point.x + 12, (hostRef.current?.clientWidth ?? 800) - 220)),
      top: Math.max(SCRATCHPAD_TOOLBAR_HEIGHT + 8, point.y),
    };
  }, [camera, history.present, history.selectedIds]);
  const showOutcome = phase === 'rating' || phase === 'reflection';

  return (
    <div className="scratchpad-workspace" ref={hostRef} data-theme-revision={themeRevision}>
      <div className="scratchpad-toolbar" role="toolbar" aria-label="Scratchpad session">
        <button
          type="button"
          className="topbar__exit scratchpad-toolbar__exit"
          onClick={() => {
            void flushLatest().then((saved) => {
              if (saved) onExitSession();
            });
          }}
          aria-label="Exit session"
        >
          Exit
        </button>
        <button
          type="button"
          className="scratchpad-toolbar__question"
          aria-expanded={questionPreviewOpen}
          aria-controls={QUESTION_PREVIEW_ID}
          onMouseEnter={() => setQuestionHovered(true)}
          onMouseLeave={() => {
            setQuestionHovered(false);
            setQuestionClickMode(false);
          }}
          onFocus={() => setQuestionFocused(true)}
          onBlur={() => {
            setQuestionFocused(false);
            setQuestionClickMode(false);
          }}
          onClick={() => {
            if (questionHovered) return;
            setQuestionClickMode(true);
            setQuestionClickOpen((open) => !open);
          }}
        >
          Q{questionNumber}/{maxQuestions} · {conceptLabel}
        </button>
        <div className="scratchpad-toolbar__metrics" aria-label="Session state">
          <span>Difficulty <strong>{scalar.toFixed(2)}</strong></span>
          <span>Turns <strong>{turnCount}</strong></span>
        </div>
        {phase === 'dialogue' && (
          <button
            type="button"
            className="btn btn--ghost scratchpad-toolbar__skip"
            aria-label="Skip question"
            disabled={busy}
            onClick={() => {
              void flushLatest().then((saved) => {
                if (saved) void onSkip();
              });
            }}
          >
            Skip
          </button>
        )}
        <button
          type="button"
          className="btn btn--ghost scratchpad-toolbar__session"
          aria-expanded={metaOpen}
          aria-controls="scratchpad-meta-panel"
          onClick={() => onMetaOpenChange(!metaOpen)}
        >
          Session
        </button>
      </div>

      <div className="scratchpad-tool-dock" role="toolbar" aria-label="Drawing tools">
        {toolItems.map((item) => (
          <button
            key={item.tool}
            type="button"
            className={`scratchpad-tool-dock__button${tool === item.tool ? ' is-active' : ''}`}
            aria-pressed={tool === item.tool}
            title={`${item.label} (${item.shortcut})`}
            onClick={() => {
              setTool(item.tool);
              canvasRef.current?.focus();
            }}
          >
            <ToolIcon name={item.tool} />
            <span className="visually-hidden">{item.label}</span>
          </button>
        ))}
        <span className="scratchpad-tool-dock__divider" />
        <button
          type="button"
          className="scratchpad-tool-dock__button"
          title="Undo"
          disabled={history.past.length === 0}
          onClick={() => dispatch({ type: 'undo' })}
        >
          <ToolIcon name="undo" />
          <span className="visually-hidden">Undo</span>
        </button>
        <button
          type="button"
          className="scratchpad-tool-dock__button"
          title="Redo"
          disabled={history.future.length === 0}
          onClick={() => dispatch({ type: 'redo' })}
        >
          <ToolIcon name="redo" />
          <span className="visually-hidden">Redo</span>
        </button>
      </div>

      <div className="scratchpad-workspace__canvas">
        <Suspense fallback={<p className="scratchpad-workspace__loading">Loading canvas…</p>}>
          <ScratchpadCanvas
            ref={canvasRef}
            history={history}
            dispatch={dispatch}
            camera={camera}
            onCameraChange={setCamera}
            tool={spacePan ? 'hand' : tool}
            feedbackRegions={boundFeedbackRegions}
            exportBounds={exportBounds}
            disabled={busy}
          />
        </Suspense>
      </div>

      {history.selectedIds.length > 0 && phase === 'dialogue' && !promptOpen && (
        <button
          type="button"
          className="scratchpad-selection-action"
          style={selectionActionPosition}
          disabled={busy}
          onClick={openPrompt}
        >
          Ask or submit selection <kbd>/</kbd>
        </button>
      )}

      <ScratchpadQuestionPanel
        id={QUESTION_PREVIEW_ID}
        open={questionPreviewOpen}
        questionText={questionText}
        conceptLabel={conceptLabel}
        questionNumber={questionNumber}
        maxQuestions={maxQuestions}
      />

      {selectionHint && <p className="scratchpad-workspace__status" role="status">{selectionHint}</p>}
      {exportError && <p className="study-start__error scratchpad-workspace__export-error">{exportError}</p>}
      {saveError && <p className="scratchpad-workspace__save-status" role="status">Canvas not saved yet</p>}

      <ScratchpadPromptBar
        open={promptOpen}
        busy={busy}
        selectionCount={selectionCount}
        prompt={askPrompt}
        position={position}
        onPromptChange={setAskPrompt}
        onAsk={() => void handleAsk()}
        onSubmit={() => void handleSubmit()}
        onClose={closePrompt}
      />

      {showOutcome && (
        <div className="scratchpad-tutor-overlay" aria-live="polite">
          {phase === 'rating' && graded && (
            <div className="scratchpad-tutor-strip__rating">
              <p className="signal-capture__rating-prompt">How difficult was that?</p>
              <div className="signal-capture__group">
                {(['easy', 'ok', 'hard'] as const).map((rating) => (
                  <button
                    key={rating}
                    type="button"
                    className={`signal-capture__btn signal-capture__btn--${rating}`}
                    disabled={busy}
                    onClick={() => {
                      void flushLatest().then((saved) => {
                        if (saved) void onSubmitRating(rating);
                      });
                    }}
                  >
                    {rating}
                  </button>
                ))}
              </div>
            </div>
          )}
          {phase === 'reflection' && (
            <button
              type="button"
              className="btn btn--primary"
              disabled={busy}
              onClick={() => {
                void flushLatest().then((saved) => {
                  if (saved) void onContinueToNext();
                });
              }}
            >
              Continue to next question
            </button>
          )}
        </div>
      )}
    </div>
  );
}
