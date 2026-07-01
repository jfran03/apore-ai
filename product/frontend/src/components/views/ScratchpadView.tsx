export function ScratchpadView() {
  return (
    <section className="view">
      <div className="screen-intro">
        <div>
          <p className="eyebrow">Scratchpad + Vision</p>
          <h1>Drawable workspace</h1>
          <p>tldraw owns the canvas. Apore owns layer semantics, selection capture, AI vision, and the assistant handoff.</p>
        </div>
        <button className="button-secondary">Show scratchpad.json</button>
      </div>

      <article className="scratchpad panel">
        <header className="scratch-toolbar">
          <button className="tool-button is-active">Select</button>
          <button className="tool-button">Pen</button>
          <button className="tool-button">Eraser</button>
          <div className="swatches">
            <span className="swatch" style={{ background: 'var(--ink)' }} />
            <span className="swatch" style={{ background: '#e25d7d' }} />
            <span className="swatch" style={{ background: '#9fbbe0' }} />
            <span className="swatch" style={{ background: '#4eb28e' }} />
            <span className="swatch" style={{ background: 'rgba(192, 133, 50, 0.35)' }} />
          </div>
          <button className="tool-button">Clear</button>
          <button className="tool-button">Ask about full canvas</button>
          <button className="tool-button is-active">Show AI layer</button>
        </header>

        <section className="scratch-stage">
          <span className="stroke black" style={{ left: 120, top: 112, width: 260, height: 4, transform: 'rotate(6deg)' }} />
          <span className="stroke black" style={{ left: 134, top: 160, width: 180, height: 4, transform: 'rotate(-2deg)' }} />
          <span className="stroke red" style={{ left: 170, top: 232, width: 210, height: 4, transform: 'rotate(13deg)' }} />
          <span className="stroke blue" style={{ left: 440, top: 248, width: 160, height: 4, transform: 'rotate(-20deg)' }} />
          <span className="stroke yellow" style={{ left: 196, top: 188, width: 220, height: 24, transform: 'rotate(0deg)' }} />

          <div className="selection-box" />

          <div className="floating-prompt">
            <textarea defaultValue="Where did this proof step go wrong?" />
            <div className="floating-actions">
              <button className="button-secondary">Speak</button>
              <button className="button-primary">Send to tutor</button>
            </div>
          </div>

          <div className="ai-annotation" style={{ left: 222, top: 325, width: 240 }}>
            AI layer: this step assumes the implication you are trying to prove.
          </div>
        </section>
      </article>
    </section>
  );
}
