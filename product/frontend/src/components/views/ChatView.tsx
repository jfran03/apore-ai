import type { WorkspaceDomain } from '../../api/types';
import type { BackendState } from '../../hooks/useBackend';

interface ChatViewProps {
  domain: WorkspaceDomain;
  sessionId: string | null;
  backend: BackendState;
  onSessionCreated: (sessionId: string) => void;
}

export function ChatView({
  domain: _domain,
  sessionId: _sessionId,
  backend: _backend,
  onSessionCreated: _onSessionCreated,
}: ChatViewProps) {
  void _domain;
  void _sessionId;
  void _backend;
  void _onSessionCreated;

  return (
    <section className="view">
      <section className="chat-layout panel">
        <article className="chat-transcript">
          <div className="chat-path">Math / Session History / Discrete Math Tutor Chat</div>

          <div className="prompt-card">
            I think the answer is 2 and 3, maybe also 4. Can you check my reasoning without giving it
            away?
          </div>

          <div className="assistant-block">
            <p>
              <strong>Before:</strong> You selected every element that appears in B.
            </p>
            <p>
              <strong>Now:</strong> Keep the rule tighter: intersection means the element must appear
              in both sets.
            </p>
            <ul>
              <li>
                <strong>Question:</strong> Does <span className="inline-code">4</span> belong to{' '}
                <span className="inline-code">A = {'{1, 2, 3}'}</span>?
              </li>
              <li>
                <strong>Source:</strong>{' '}
                <span className="inline-code">knowledge/nodes/intersection.md</span>
              </li>
              <li>
                <strong>Signal:</strong> hedging language detected around “maybe also 4”.
              </li>
            </ul>
            <p>This mirrors the calibrated tutoring pattern: the card stays, but the answer is not handed over.</p>
          </div>

          <div className="chat-actions">
            <span>thumbs up</span>
            <span>thumbs down</span>
            <span>copy</span>
          </div>

          <div className="run-card">
            <div className="run-card-header">
              <span>Build · Socratic turn on intersection</span>
              <span>↻</span>
            </div>
            <div className="run-card-body">
              <span className="run-spinner" />
              <span>3 of 3 completed · signals captured</span>
            </div>
          </div>

          <div className="assistant-block">
            <p>Worked for 25s.</p>
            <p>
              <strong>Session update:</strong>
            </p>
            <ol>
              <li>
                <span className="inline-code">sets</span> stayed stable.
              </li>
              <li>
                <span className="inline-code">intersection</span> received one weak-edge marker.
              </li>
              <li>
                Difficulty calibration remains near <span className="inline-code">0.51</span>.
              </li>
            </ol>
            <p>Try answering with only the shared elements, then rate whether the question felt easy, okay, or hard.</p>
          </div>
        </article>

        <div className="chat-composer-wrap">
          <div className="chat-composer">
            <button className="composer-icon">+</button>
            <input defaultValue="Send follow-up" />
            <span className="composer-mode">Auto</span>
            <button className="composer-icon">↵</button>
          </div>
        </div>
      </section>
    </section>
  );
}
