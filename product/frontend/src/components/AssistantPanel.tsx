// The assistant panel mirrors whichever workspace surface is active. In a full
// chat session the center stage is already the chat surface, so the panel hides.
export function AssistantPanel() {
  const showGraph = false;

  return (
    <aside className="assistant">
      <section className="assistant-thread">
        {showGraph ? <GraphProposals /> : <ScratchpadHandoff />}
      </section>

      <footer className="assistant-composer">
        <div className="composer-box">
          <button className="composer-icon">+</button>
          <input defaultValue="Send follow-up" />
          <span className="composer-mode">Auto</span>
          <button className="composer-icon">↵</button>
        </div>
      </footer>
    </aside>
  );
}

function ScratchpadHandoff() {
  return (
    <section className="assistant-panel">
      <article className="assistant-message is-user">
        <p>that scratchpad selection should be checked for the proof error</p>
      </article>

      <article className="assistant-prose">
        <p>I’ll inspect the selected region and send it into the tutor thread as an image attachment.</p>
        <p>
          <strong>Before:</strong> the scratchpad had no canonical chat handoff.
        </p>
        <p>
          <strong>Now:</strong> the selection becomes a normal chat message with bounds and a crop path.
        </p>
      </article>

      <article className="assistant-card">
        <div className="assistant-card-header">
          <span>Build · Scratchpad selection → tutor chat</span>
          <span>↻</span>
        </div>
        <div className="assistant-card-body">3 of 3 completed · image crop attached</div>
      </article>

      <article className="assistant-card">
        <div className="assistant-card-header">
          <span>scratchpad.json</span>
          <span>+42</span>
        </div>
        <div className="assistant-card-body assistant-diff">
          <span className="diff-line remove">- floatingPrompt.ownsHistory = true</span>
          <span className="diff-line add">+ floatingPrompt.target = "assistant_thread"</span>
          <span className="diff-line add">+ selection.attachments.push(crop)</span>
        </div>
      </article>

      <div className="assistant-review">
        <span>1 File</span>
        <button className="tool-button">Undo</button>
        <button className="tool-button is-active">Review</button>
      </div>
    </section>
  );
}

function GraphProposals() {
  return (
    <section className="assistant-panel">
      <article className="assistant-message is-user">
        <p>help me make this curriculum path more teachable</p>
      </article>

      <article className="assistant-prose">
        <p>I’ll review the graph as a curriculum designer and propose edits as graph operations.</p>
        <p>
          <strong>Goal:</strong> keep the path mostly linear, with leaf notes for examples and common
          mistakes.
        </p>
      </article>

      <article className="assistant-card">
        <div className="assistant-card-header">
          <span>Curriculum Builder · Agent proposal</span>
          <span>↻</span>
        </div>
        <div className="assistant-card-body">
          Split Set Operations into union, intersection, and difference. Keep Subsets before Power
          Sets. Add a leaf note for common notation mistakes.
        </div>
      </article>

      <article className="assistant-card">
        <div className="assistant-card-header">
          <span>graph.json</span>
          <span>+4 ops</span>
        </div>
        <div className="assistant-card-body assistant-diff">
          <span className="diff-line add">+ create_node: intersection</span>
          <span className="diff-line add">+ create_node: union</span>
          <span className="diff-line add">+ create_edge: sets → intersection</span>
          <span className="diff-line add">+ create_edge: sets → union</span>
        </div>
      </article>

      <div className="assistant-review">
        <span>Graph proposal</span>
        <button className="tool-button">Undo</button>
        <button className="tool-button is-active">Apply</button>
      </div>
    </section>
  );
}
