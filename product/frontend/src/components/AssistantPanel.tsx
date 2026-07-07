export function AssistantPanel() {
  return (
    <aside className="assistant">
      <section className="assistant-thread">
        <section className="assistant-panel">
          <div className="assistant-header">
            <span>Assistant</span>
          </div>
          <div className="assistant-prose">
            <p className="help">
              Contextual agents (curriculum builder, source compiler) ship in later milestones.
              Tutoring happens in the chat tab.
            </p>
          </div>
        </section>
      </section>
    </aside>
  );
}
