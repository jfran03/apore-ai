import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

interface StudyFocusContextValue {
  focused: boolean;
  setFocused: (focused: boolean) => void;
  onExitRequest: (() => void) | null;
  setOnExitRequest: (handler: (() => void) | null) => void;
}

const StudyFocusContext = createContext<StudyFocusContextValue | null>(null);

export function StudyFocusProvider({ children }: { children: ReactNode }) {
  const [focused, setFocused] = useState(false);
  const [onExitRequest, setOnExitRequestState] = useState<(() => void) | null>(null);

  const setOnExitRequest = useCallback((handler: (() => void) | null) => {
    setOnExitRequestState(() => handler);
  }, []);

  const value = useMemo(
    () => ({ focused, setFocused, onExitRequest, setOnExitRequest }),
    [focused, onExitRequest, setOnExitRequest],
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
