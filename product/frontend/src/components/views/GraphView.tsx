export function GraphView() {
  return (
    <section className="view">
      <div className="screen-intro">
        <div>
          <p className="eyebrow">Adaptive curriculum</p>
          <h1>Curriculum map</h1>
          <p>
            Nodes are movable curriculum cards. Edges mean prerequisite dependency. The curriculum
            builder agent proposes edits, then the user accepts them.
          </p>
        </div>
        <button className="button-primary">Consult curriculum agent</button>
      </div>

      <section className="graph-layout">
        <article className="panel" style={{ overflow: 'hidden' }}>
          <header className="graph-toolbar">
            <button className="tool-button">Add node</button>
            <button className="tool-button">Connect</button>
            <button className="tool-button">Auto layout</button>
            <button className="tool-button">Open markdown</button>
          </header>

          <section className="graph-canvas">
            <span className="edge" style={{ left: 192, top: 164, width: 170, transform: 'rotate(8deg)' }} />
            <span className="edge" style={{ left: 386, top: 184, width: 160, transform: 'rotate(11deg)' }} />
            <span className="edge" style={{ left: 386, top: 184, width: 150, transform: 'rotate(48deg)' }} />

            <article className="concept-node root" style={{ left: 48, top: 112 }}>
              <h3>Discrete Mathematics</h3>
              <p>Root scope for proof-based computer science.</p>
              <div className="node-meta">
                <span className="pill">root</span>
              </div>
            </article>

            <article className="concept-node" style={{ left: 364, top: 138 }}>
              <h3>Sets</h3>
              <p>Collections, membership, equality, empty set.</p>
              <div className="node-meta">
                <span className="pill">concept</span>
                <span className="pill">ready</span>
              </div>
            </article>

            <article className="concept-node" style={{ left: 620, top: 174 }}>
              <h3>Subsets</h3>
              <p>Every element of A is contained in B.</p>
              <div className="node-meta">
                <span className="pill">dependent</span>
              </div>
            </article>

            <article className="concept-node" style={{ left: 578, top: 356 }}>
              <h3>Set Operations</h3>
              <p>Union, intersection, difference, complement.</p>
              <div className="node-meta">
                <span className="pill">split suggested</span>
              </div>
            </article>
          </section>
        </article>
      </section>
    </section>
  );
}
