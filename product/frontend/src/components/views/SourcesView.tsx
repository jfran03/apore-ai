export function SourcesView() {
  return (
    <section className="view">
      <div className="screen-intro">
        <div>
          <p className="eyebrow">GroundedWiki</p>
          <h1>Add materials</h1>
          <p>
            After a domain is scaffolded on disk, the first CTA is adding sources. The Tauri shell
            opens files locally while the Python backend extracts, transcribes, and compiles through
            localhost.
          </p>
        </div>
        <button className="button-primary">Add sources</button>
      </div>

      <article className="source-modal panel">
        <div className="modal-header">
          <div>
            <p className="eyebrow">Source intake</p>
            <h2>Add sources to Math</h2>
          </div>
          <button className="button-secondary">Close</button>
        </div>

        <div className="modal-body">
          <section className="source-search">
            <span className="search-label">Paste a website or YouTube/video link</span>
            <div className="search-row">
              <span className="pill">Website</span>
              <span className="pill">YouTube</span>
              <input className="input" defaultValue="https://www.youtube.com/watch?v=set-theory-lecture" />
              <button className="button-ink">Import</button>
            </div>
          </section>

          <section className="dropzone">
            <h3>or drop your files</h3>
            <p>PDF, images, docs, audio, video, text, websites, and copied text.</p>
            <div className="source-actions">
              <button className="button-secondary">Upload files</button>
              <button className="button-secondary">Websites</button>
              <button className="button-secondary">Copied text</button>
              <button className="button-secondary">Audio / video</button>
            </div>
          </section>

          <section className="source-status" aria-label="Processing stages">
            <span className="timeline-pill thinking">Queued</span>
            <span className="timeline-pill read">Extracting</span>
            <span className="timeline-pill grep">Transcribing</span>
            <span className="timeline-pill edit">Compiling</span>
            <span className="timeline-pill done">Ready</span>
          </section>

          <pre className="code-card">{`sources/
  index.json
  raw/
    lecture-01.pdf
    sets-video.mp4
  transcripts/
    sets-video.md
  extracted/
    lecture-01.md
    sets-video.md`}</pre>
        </div>
      </article>
    </section>
  );
}
