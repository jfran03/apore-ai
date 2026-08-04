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
  ScratchpadAnnotation,
  ScratchpadCamera,
  ScratchpadExportBounds,
  ScratchpadScenePayload,
} from '../../api/types';
import { putScratchpadScene } from '../../api/client';
import type { GradeResult } from '../SignalCapture';
import type { ChatStatus } from '../TutorChatCard';
import { ScratchpadAnnotationPanel } from './ScratchpadAnnotationPanel';
import { ScratchpadPromptBar, type PromptBarMode, type PromptBarPosition } from './ScratchpadPromptBar';
import {
  ScratchpadQuestionPanel,
  SCRATCHPAD_TOOLBAR_HEIGHT,
} from './ScratchpadQuestionPanel';
import type { ScratchpadCanvasHandle } from './ScratchpadCanvas';
import { exportKonvaSelection } from './scratchpadKonva';
import {
  createHistory,
  historyReducer,
  nodeBounds,
  sceneToScreen,
  selectedExportBounds,
  type SceneRect,
  type ScratchpadTool,
} from './scratchpadModel';

const ScratchpadCanvas = lazy(async () => {
  const module = await import('./ScratchpadCanvas');
  return { default: module.ScratchpadCanvas };
});

const DEFAULT_CAMERA: ScratchpadCamera = { x: 0, y: 0, scale: 1 };
const ANCHOR_WIDTH = 420;
const ANCHOR_HEIGHT = 52;
const SUBMIT_CONFIRM_WIDTH = 360;
const SUBMIT_CONFIRM_HEIGHT = 280;
const RESPONSE_PANEL_WIDTH = 360;
const RESPONSE_PANEL_HEIGHT = 180;
const MARKER_WIDTH = 88;
const MARKER_HEIGHT = 36;
const BOTTOM_SAFE = 120;
const QUESTION_PREVIEW_ID = 'scratchpad-question-preview';
const EMPTY_REPLY = 'No reply was returned for this selection.';

export interface ScratchpadAskResult {
  tutorMessage: string;
  feedbackRegions: FeedbackRegion[];
}

interface ActiveAskRequest {
  id: string;
  nodeIds: string[];
  imageDataUri: string;
  prompt: string;
  error: string | null;
  position: PromptBarPosition;
}

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
  onAskSelection: (
    imageDataUri: string,
    prompt: string,
  ) => ScratchpadAskResult | Promise<ScratchpadAskResult>;
  onSubmitSelection: (imageDataUri: string) => void | Promise<void>;
  onSubmitRating: (rating: 'easy' | 'ok' | 'hard') => void | Promise<void>;
  onContinueToNext: () => void | Promise<void>;
  onSkip: () => void | Promise<void>;
  skipPrompt?: boolean;
  onSubmitSkipReason?: (reason: string) => void | Promise<void>;
  onRevealComplete: () => void;
  clearSceneToken: number;
  submitError?: string | null;
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

function nextAnnotationId(): string {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `ann-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

/** Shared top-right selection anchor for action chip, composer, and replies. */
export function selectionAnchorPosition(
  host: HTMLElement | null,
  bounds: ScratchpadExportBounds | SceneRect,
  camera: ScratchpadCamera,
  metaOpen: boolean,
  narrow: boolean,
  panelWidth = ANCHOR_WIDTH,
  panelHeight = ANCHOR_HEIGHT,
): PromptBarPosition {
  const width = host && host.clientWidth > 0 ? host.clientWidth : 640;
  const height = host && host.clientHeight > 0 ? host.clientHeight : 480;
  const screen = sceneToScreen(
    { x: bounds.x + bounds.width, y: bounds.y },
    camera,
  );
  const gutter = narrow ? 12 : 64;
  const rightReserve = metaOpen ? (narrow ? 12 : 296) : 16;
  const maxLeft = Math.max(gutter, width - rightReserve - panelWidth);
  const minTop = SCRATCHPAD_TOOLBAR_HEIGHT + 8;
  const maxTop = Math.max(minTop, height - BOTTOM_SAFE - panelHeight);
  return {
    left: Math.min(Math.max(gutter, screen.x + 12), maxLeft),
    top: Math.min(Math.max(minTop, screen.y), maxTop),
  };
}

function pruneAnnotations(
  annotations: ScratchpadAnnotation[],
  presentIds: Set<string>,
): ScratchpadAnnotation[] {
  return annotations
    .map((annotation) => ({
      ...annotation,
      node_ids: annotation.node_ids.filter((id) => presentIds.has(id)),
    }))
    .filter((annotation) => annotation.node_ids.length > 0);
}

function highlightRectsForIds(
  nodes: ScratchpadScenePayload['nodes'],
  nodeIds: string[],
): SceneRect[] {
  const selected = new Set(nodeIds);
  return nodes.filter((node) => selected.has(node.id)).map(nodeBounds);
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
  skipPrompt = false,
  onSubmitSkipReason,
  onRevealComplete,
  clearSceneToken,
  submitError = null,
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
  const [annotations, setAnnotations] = useState<ScratchpadAnnotation[]>(
    initialScene?.question_number === questionNumber
      ? initialScene.annotations ?? []
      : [],
  );
  const [expandedAnnotationId, setExpandedAnnotationId] = useState<string | null>(null);
  const [activeAsk, setActiveAsk] = useState<ActiveAskRequest | null>(null);
  const [tool, setTool] = useState<ScratchpadTool>('pen');
  const [spacePan, setSpacePan] = useState(false);
  const [promptOpen, setPromptOpen] = useState(false);
  const [promptMode, setPromptMode] = useState<PromptBarMode>('ask');
  const [askPrompt, setAskPrompt] = useState('');
  const [skipReason, setSkipReason] = useState('');
  const [pendingImage, setPendingImage] = useState<string | null>(null);
  const [pendingNodeIds, setPendingNodeIds] = useState<string[]>([]);
  const [submittedNodeIds, setSubmittedNodeIds] = useState<string[]>([]);
  const [gradeExpanded, setGradeExpanded] = useState(true);
  const [selectionHint, setSelectionHint] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [localSubmitError, setLocalSubmitError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState(false);
  const [selectionCount, setSelectionCount] = useState(0);
  const [questionHovered, setQuestionHovered] = useState(false);
  const [questionFocused, setQuestionFocused] = useState(false);
  const [questionClickMode, setQuestionClickMode] = useState(true);
  const [questionClickOpen, setQuestionClickOpen] = useState(true);
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
  const asking = activeAsk !== null && activeAsk.error === null;
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
      annotations,
    }),
    [
      annotations,
      boundFeedbackRegions,
      camera,
      exportBounds,
      history.present,
      questionNumber,
    ],
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
    setQuestionClickMode(true);
    setQuestionClickOpen(true);
    setSkipReason('');
  }, [questionNumber]);

  useEffect(() => {
    if (!skipPrompt) setSkipReason('');
  }, [skipPrompt]);

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
    setAnnotations([]);
    setExpandedAnnotationId(null);
    setActiveAsk(null);
    setPromptOpen(false);
    setPromptMode('ask');
    setPendingImage(null);
    setPendingNodeIds([]);
    setSubmittedNodeIds([]);
    setGradeExpanded(true);
    setSelectionHint(null);
    setLocalSubmitError(null);
    lastSavedRef.current = '';
  }, [clearSceneToken]);

  useEffect(() => {
    if (!initialScene || initialScene.question_number !== questionNumber) return;
    dispatch({ type: 'hydrate', nodes: initialScene.nodes });
    setCamera(initialScene.camera);
    setExportBounds(initialScene.last_export_bounds);
    setBoundFeedbackRegions(initialScene.feedback_regions);
    setAnnotations(initialScene.annotations ?? []);
    setExpandedAnnotationId(null);
    setActiveAsk(null);
    lastSavedRef.current = JSON.stringify({
      ...initialScene,
      annotations: initialScene.annotations ?? [],
    });
  }, [initialScene, questionNumber]);

  useEffect(() => {
    setBoundFeedbackRegions(feedbackRegions);
  }, [feedbackRegions]);

  useEffect(() => {
    const presentIds = new Set(history.present.map((node) => node.id));
    setAnnotations((current) => {
      const next = pruneAnnotations(current, presentIds);
      return next.length === current.length &&
        next.every(
          (annotation, index) =>
            annotation.id === current[index]?.id &&
            annotation.node_ids.length === current[index]?.node_ids.length &&
            annotation.node_ids.every((id, i) => id === current[index]?.node_ids[i]),
        )
        ? current
        : next;
    });
    setActiveAsk((current) => {
      if (!current) return current;
      const nodeIds = current.nodeIds.filter((id) => presentIds.has(id));
      if (nodeIds.length === 0) return null;
      if (nodeIds.length === current.nodeIds.length) return current;
      return { ...current, nodeIds };
    });
    setSubmittedNodeIds((current) => {
      if (current.length === 0) return current;
      const next = current.filter((id) => presentIds.has(id));
      return next.length === current.length ? current : next;
    });
  }, [history.present]);

  useEffect(() => {
    setExpandedAnnotationId((current) => {
      if (!current) return current;
      return annotations.some((annotation) => annotation.id === current) ? current : null;
    });
  }, [annotations]);

  const closePrompt = useCallback(() => {
    if (promptMode === 'submitting') return;
    setPromptOpen(false);
    setPromptMode('ask');
    setAskPrompt('');
    setPendingNodeIds([]);
    setLocalSubmitError(null);
  }, [promptMode]);

  const prepareSelectionExport = useCallback(() => {
    if (busy || asking || phase !== 'dialogue' || skipPrompt) return null;
    if (history.selectedIds.length === 0) {
      setSelectionHint('Select the work you want to send, then choose Ask or Submit.');
      return null;
    }
    setSelectionHint(null);
    setExportError(null);
    try {
      const result = exportKonvaSelection(
        history.present,
        history.selectedIds,
        cssColor('--color-canvas-soft', '#f3f2ec'),
      );
      if (!result) return null;
      setPendingImage(result.imageDataUri);
      setPendingNodeIds([...history.selectedIds]);
      setBoundFeedbackRegions([]);
      setExportBounds(result.bounds);
      setSelectionCount(history.selectedIds.length);
      setExpandedAnnotationId(null);
      setLocalSubmitError(null);
      return result;
    } catch (error) {
      setExportError(error instanceof Error ? error.message : 'Failed to export selection');
      return null;
    }
  }, [asking, busy, history.present, history.selectedIds, phase, skipPrompt]);

  useEffect(() => {
    if (!skipPrompt) return;
    setPromptOpen(false);
    setPromptMode('ask');
    setAskPrompt('');
    setPendingNodeIds([]);
    setLocalSubmitError(null);
    setActiveAsk(null);
  }, [skipPrompt]);

  const openAsk = useCallback(() => {
    const result = prepareSelectionExport();
    if (!result) return;
    const anchorBounds =
      selectedExportBounds(history.present, history.selectedIds, 0) ?? result.bounds;
    setPosition(
      selectionAnchorPosition(hostRef.current, anchorBounds, camera, metaOpen, narrow),
    );
    setPromptMode('ask');
    setPromptOpen(true);
  }, [camera, history.present, history.selectedIds, metaOpen, narrow, prepareSelectionExport]);

  const openSubmit = useCallback(() => {
    const result = prepareSelectionExport();
    if (!result) return;
    const anchorBounds =
      selectedExportBounds(history.present, history.selectedIds, 0) ?? result.bounds;
    setPosition(
      selectionAnchorPosition(
        hostRef.current,
        anchorBounds,
        camera,
        metaOpen,
        narrow,
        SUBMIT_CONFIRM_WIDTH,
        SUBMIT_CONFIRM_HEIGHT,
      ),
    );
    setPromptMode('submit');
    setPromptOpen(true);
  }, [camera, history.present, history.selectedIds, metaOpen, narrow, prepareSelectionExport]);

  const openPrompt = openAsk;

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

  const selectionBounds = useMemo(
    () => selectedExportBounds(history.present, history.selectedIds, 0),
    [history.present, history.selectedIds],
  );

  const selectionActionPosition = useMemo(() => {
    if (!selectionBounds) return undefined;
    return selectionAnchorPosition(
      hostRef.current,
      selectionBounds,
      camera,
      metaOpen,
      narrow,
    );
  }, [camera, metaOpen, narrow, selectionBounds]);

  useEffect(() => {
    if (!promptOpen) return;
    const bounds =
      selectedExportBounds(history.present, pendingNodeIds, 0) ?? exportBounds;
    if (!bounds) return;
    const panelWidth = promptMode === 'ask' ? ANCHOR_WIDTH : SUBMIT_CONFIRM_WIDTH;
    const panelHeight = promptMode === 'ask' ? ANCHOR_HEIGHT : SUBMIT_CONFIRM_HEIGHT;
    setPosition(
      selectionAnchorPosition(
        hostRef.current,
        bounds,
        camera,
        metaOpen,
        narrow,
        panelWidth,
        panelHeight,
      ),
    );
  }, [
    camera,
    exportBounds,
    history.present,
    metaOpen,
    narrow,
    pendingNodeIds,
    promptMode,
    promptOpen,
  ]);

  useEffect(() => {
    if (promptMode === 'submitting' || promptMode === 'submit-error') {
      if (submitError) {
        setLocalSubmitError(submitError);
        setPromptMode('submit-error');
        setPromptOpen(true);
        return;
      }
      if (phase === 'rating' || phase === 'reflection') {
        setPromptOpen(false);
        setPromptMode('ask');
        setPendingImage(null);
        setPendingNodeIds([]);
        setLocalSubmitError(null);
        setGradeExpanded(true);
      }
    }
  }, [phase, promptMode, submitError]);

  useEffect(() => {
    if ((phase === 'rating' || phase === 'reflection') && graded) {
      setGradeExpanded(true);
    }
  }, [graded, phase]);

  const runAsk = useCallback(
    async (request: ActiveAskRequest) => {
      setActiveAsk({ ...request, error: null });
      setExpandedAnnotationId(null);
      try {
        const result = await onAskSelection(request.imageDataUri, request.prompt);
        const annotation: ScratchpadAnnotation = {
          id: request.id,
          node_ids: request.nodeIds,
          prompt: request.prompt,
          response: result.tutorMessage.trim() || EMPTY_REPLY,
          feedback_regions: result.feedbackRegions,
        };
        setAnnotations((current) => [
          ...current.filter((item) => item.id !== annotation.id),
          annotation,
        ]);
        setBoundFeedbackRegions(result.feedbackRegions);
        setActiveAsk(null);
        setExpandedAnnotationId(annotation.id);
      } catch (error) {
        setActiveAsk({
          ...request,
          error: error instanceof Error ? error.message : 'Failed to ask about selection',
        });
      }
    },
    [onAskSelection],
  );

  const handleAsk = useCallback(async () => {
    if (!pendingImage || pendingNodeIds.length === 0) return;
    if (!(await flushLatest())) return;
    const bounds =
      selectedExportBounds(history.present, pendingNodeIds, 0) ?? exportBounds;
    if (!bounds) return;
    const request: ActiveAskRequest = {
      id: nextAnnotationId(),
      nodeIds: pendingNodeIds,
      imageDataUri: pendingImage,
      prompt: askPrompt.trim(),
      error: null,
      position: selectionAnchorPosition(
        hostRef.current,
        bounds,
        camera,
        metaOpen,
        narrow,
        RESPONSE_PANEL_WIDTH,
        RESPONSE_PANEL_HEIGHT,
      ),
    };
    setPromptOpen(false);
    setAskPrompt('');
    setPendingImage(null);
    setPendingNodeIds([]);
    await runAsk(request);
  }, [
    askPrompt,
    camera,
    exportBounds,
    flushLatest,
    history.present,
    metaOpen,
    narrow,
    pendingImage,
    pendingNodeIds,
    runAsk,
  ]);

  const handleSubmit = useCallback(async () => {
    if (!pendingImage || pendingNodeIds.length === 0) return;
    const nodeIds = [...pendingNodeIds];
    setSubmittedNodeIds(nodeIds);
    setGradeExpanded(true);
    setPromptMode('submitting');
    setLocalSubmitError(null);
    // Close confirm and show Ask-like loading panel on the selection.
    setPromptOpen(false);
    if (!(await flushLatest())) {
      setLocalSubmitError('Canvas could not be saved. Retry when ready.');
      setPromptMode('submit-error');
      setPromptOpen(true);
      return;
    }
    try {
      await onSubmitSelection(pendingImage);
      // Grade reply opens when phase becomes rating/reflection.
    } catch (error) {
      setLocalSubmitError(
        error instanceof Error ? error.message : 'Failed to submit selected answer',
      );
      setPromptMode('submit-error');
      setPromptOpen(true);
    }
  }, [flushLatest, onSubmitSelection, pendingImage, pendingNodeIds]);

  const handleRetrySubmit = useCallback(() => {
    void handleSubmit();
  }, [handleSubmit]);

  const gradeAnchorBounds = useMemo(() => {
    if (submittedNodeIds.length > 0) {
      return selectedExportBounds(history.present, submittedNodeIds, 0) ?? exportBounds;
    }
    return exportBounds;
  }, [exportBounds, history.present, submittedNodeIds]);

  const gradePanelPosition = useMemo(() => {
    if (!gradeAnchorBounds) return null;
    return selectionAnchorPosition(
      hostRef.current,
      gradeAnchorBounds,
      camera,
      metaOpen,
      narrow,
      gradeExpanded ? RESPONSE_PANEL_WIDTH : MARKER_WIDTH,
      gradeExpanded ? RESPONSE_PANEL_HEIGHT : MARKER_HEIGHT,
    );
  }, [camera, gradeAnchorBounds, gradeExpanded, metaOpen, narrow]);

  const gradingInFlight =
    promptMode === 'submitting' &&
    phase === 'dialogue' &&
    submittedNodeIds.length > 0 &&
    gradePanelPosition !== null;

  const showGradeReply =
    (phase === 'rating' || phase === 'reflection') &&
    graded !== null &&
    gradePanelPosition !== null;

  const annotationHighlights = useMemo(() => {
    const rects: SceneRect[] = [];
    for (const annotation of annotations) {
      rects.push(...highlightRectsForIds(history.present, annotation.node_ids));
    }
    if (activeAsk) {
      rects.push(...highlightRectsForIds(history.present, activeAsk.nodeIds));
    }
    if (promptOpen && pendingNodeIds.length > 0) {
      rects.push(...highlightRectsForIds(history.present, pendingNodeIds));
    }
    if (submittedNodeIds.length > 0 && (gradingInFlight || showGradeReply)) {
      rects.push(...highlightRectsForIds(history.present, submittedNodeIds));
    }
    return rects;
  }, [
    activeAsk,
    annotations,
    gradingInFlight,
    history.present,
    pendingNodeIds,
    promptOpen,
    showGradeReply,
    submittedNodeIds,
  ]);

  const showOutcome = phase === 'rating' || phase === 'reflection';
  const showSkipPrompt = skipPrompt && phase === 'dialogue';
  const showSelectionAction =
    history.selectedIds.length > 0 &&
    phase === 'dialogue' &&
    !skipPrompt &&
    !promptOpen &&
    !activeAsk &&
    !gradingInFlight;
  const displaySubmitError = localSubmitError ?? submitError;
  const canSubmitSkipReason =
    !busy && showSkipPrompt && skipReason.trim().length > 0 && Boolean(onSubmitSkipReason);

  const submitSkipReason = useCallback(() => {
    if (!canSubmitSkipReason || !onSubmitSkipReason) return;
    const reason = skipReason.trim();
    setSkipReason('');
    void flushLatest().then((saved) => {
      if (saved) void onSubmitSkipReason(reason);
    });
  }, [canSubmitSkipReason, flushLatest, onSubmitSkipReason, skipReason]);

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
            disabled={busy || asking || skipPrompt}
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
            annotationHighlights={annotationHighlights}
            disabled={busy || asking || promptMode === 'submitting'}
          />
        </Suspense>
      </div>

      {showSelectionAction && (
        <div
          className="scratchpad-selection-actions"
          style={selectionActionPosition}
          data-testid="scratchpad-selection-action"
        >
          <button
            type="button"
            className="scratchpad-selection-action"
            disabled={busy}
            onClick={openAsk}
          >
            Ask about selection <kbd>/</kbd>
          </button>
          <button
            type="button"
            className="scratchpad-selection-action scratchpad-selection-action--submit"
            disabled={busy}
            onClick={openSubmit}
          >
            Submit as answer
          </button>
        </div>
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
        mode={promptMode}
        busy={busy || asking || promptMode === 'submitting'}
        selectionCount={selectionCount}
        prompt={askPrompt}
        previewDataUri={pendingImage}
        errorMessage={displaySubmitError}
        position={position}
        onPromptChange={setAskPrompt}
        onAsk={() => void handleAsk()}
        onConfirmSubmit={() => void handleSubmit()}
        onRetrySubmit={handleRetrySubmit}
        onClose={closePrompt}
      />

      {activeAsk && (
        <ScratchpadAnnotationPanel
          mode={activeAsk.error ? 'error' : 'loading'}
          position={activeAsk.position}
          prompt={activeAsk.prompt}
          error={activeAsk.error}
          busy={busy}
          onRetry={() => void runAsk(activeAsk)}
          onDismiss={() => setActiveAsk(null)}
        />
      )}

      {gradingInFlight && gradePanelPosition && (
        <ScratchpadAnnotationPanel
          mode="loading"
          kind="grade"
          position={gradePanelPosition}
          busy
        />
      )}

      {showGradeReply && graded && gradePanelPosition && (
        <ScratchpadAnnotationPanel
          mode={gradeExpanded ? 'response' : 'marker'}
          kind="grade"
          position={gradePanelPosition}
          response={graded.feedback ?? undefined}
          verdict={graded.correct === 'yes' ? 'correct' : 'incorrect'}
          verdictAssisted={graded.assisted === true}
          busy={busy}
          onExpand={() => setGradeExpanded(true)}
          onCollapse={() => setGradeExpanded(false)}
          onDismiss={() => setGradeExpanded(false)}
        />
      )}

      {annotations.map((annotation) => {
        const bounds = selectedExportBounds(history.present, annotation.node_ids, 0);
        if (!bounds) return null;
        const isExpanded = expandedAnnotationId === annotation.id;
        const panelPosition = selectionAnchorPosition(
          hostRef.current,
          bounds,
          camera,
          metaOpen,
          narrow,
          isExpanded ? RESPONSE_PANEL_WIDTH : MARKER_WIDTH,
          isExpanded ? RESPONSE_PANEL_HEIGHT : MARKER_HEIGHT,
        );
        return (
          <ScratchpadAnnotationPanel
            key={annotation.id}
            mode={isExpanded ? 'response' : 'marker'}
            position={panelPosition}
            prompt={annotation.prompt}
            response={annotation.response}
            onExpand={() => {
              setPromptOpen(false);
              setExpandedAnnotationId(annotation.id);
              if (annotation.feedback_regions.length > 0) {
                setBoundFeedbackRegions(annotation.feedback_regions);
              }
            }}
            onCollapse={() => setExpandedAnnotationId(null)}
            onDismiss={() => {
              setAnnotations((current) =>
                current.filter((item) => item.id !== annotation.id),
              );
              setExpandedAnnotationId((current) =>
                current === annotation.id ? null : current,
              );
            }}
          />
        );
      })}

      {showSkipPrompt && (
        <div className="scratchpad-tutor-overlay" aria-live="polite">
          <div className="scratchpad-tutor-strip__skip">
            <p className="signal-capture__rating-prompt">Why skip?</p>
            <div className="scratchpad-skip-reason">
              <input
                type="text"
                className="scratchpad-skip-reason__input"
                value={skipReason}
                placeholder="Briefly, why do you want to skip this question?"
                aria-label="Skip reason"
                disabled={busy}
                onChange={(event) => setSkipReason(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    event.preventDefault();
                    submitSkipReason();
                  }
                }}
              />
              <button
                type="button"
                className="btn btn--primary scratchpad-skip-reason__submit"
                disabled={!canSubmitSkipReason}
                onClick={submitSkipReason}
              >
                Continue
              </button>
            </div>
          </div>
        </div>
      )}

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
