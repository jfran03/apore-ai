import type { HistoryRecord } from '../QuestionHistoryCard';
import { QuestionHistoryCard } from '../QuestionHistoryCard';
import { ScalarBadge } from '../ScalarBadge';
import { MasteryDeltaList, type MasteryDeltaItem } from '../MasteryDeltaList';

interface ScratchpadMetaDrawerProps {
  open: boolean;
  conceptLabel: string;
  questionCount: number;
  maxQuestions: number;
  scalar: number;
  masteryItems: MasteryDeltaItem[];
  history: HistoryRecord[];
}

export function ScratchpadMetaDrawer({
  open,
  conceptLabel,
  questionCount,
  maxQuestions,
  scalar,
  masteryItems,
  history,
}: ScratchpadMetaDrawerProps) {
  return (
    <aside
      id="scratchpad-meta-panel"
      className={`scratchpad-meta__panel${open ? ' scratchpad-meta__panel--open' : ''}`}
      aria-label="Session details"
      hidden={!open}
    >
      <div className="study-sidebar-meta">
        <div className="study-sidebar-meta__row">
          <span className="study-sidebar-meta__key">Concept</span>
          <span className="study-sidebar-meta__val">{conceptLabel || '—'}</span>
        </div>
        <div className="study-sidebar-meta__row">
          <span className="study-sidebar-meta__key">Questions</span>
          <span className="study-sidebar-meta__val">
            {questionCount} / {maxQuestions}
          </span>
        </div>
      </div>
      <ScalarBadge scalar={scalar} label="Difficulty" />
      {masteryItems.length > 0 && (
        <MasteryDeltaList items={masteryItems} variant="live" />
      )}
      <QuestionHistoryCard records={history} />
    </aside>
  );
}
