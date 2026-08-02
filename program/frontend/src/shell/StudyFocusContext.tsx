import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

export type StudyFocusMode = 'chat' | 'scratchpad' | null;

interface StudyFocusContextValue {
  focused: boolean;
  focusMode: StudyFocusMode;
  setFocused: (focused: boolean, mode?: Exclude<StudyFocusMode, null>) => void;
  onExitRequest: (() => void) | null;
  setOnExitRequest: (handler: (() => void) | null) => void;
}

const StudyFocusContext = createContext<StudyFocusContextValue | null>(null);

export function StudyFocusProvider({ children }: { children: ReactNode }) {
  const [focusMode, setFocusMode] = useState<StudyFocusMode>(null);
  const [onExitRequest, setOnExitRequestState] = useState<(() => void) | null>(null);

  const setFocused = useCallback((focused: boolean, mode: Exclude<StudyFocusMode, null> = 'chat') => {
    setFocusMode(focused ? mode : null);
  }, []);

  const setOnExitRequest = useCallback((handler: (() => void) | null) => {
    setOnExitRequestState(() => handler);
  }, []);

  const value = useMemo(
    () => ({
      focused: focusMode != null,
      focusMode,
      setFocused,
      onExitRequest,
      setOnExitRequest,
    }),
    [focusMode, onExitRequest, setFocused, setOnExitRequest],
  );

  return (
    <StudyFocusContext.Provider value={value}>{children}</StudyFocusContext.Provider>
  );
}

export function useStudyFocus(): StudyFocusContextValue {
  const ctx = useContext(StudyFocusContext);
  if (!ctx) {
    throw new Error('useStudyFocus must be used within StudyFocusProvider');
  }
  return ctx;
}
