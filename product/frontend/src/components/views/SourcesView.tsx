import type { WorkspaceDomain } from '../../api/types';

interface SourcesViewProps {
  domain: WorkspaceDomain;
}

export function SourcesView({ domain }: SourcesViewProps) {
  return (
    <section className="view">
      <div className="screen-intro">
        <div>
          <p className="eyebrow">Sources</p>
          <h1>{domain.name} sources</h1>
          <p>
            Files in this domain's <span className="inline-code">sources/</span> folder. Source intake
            (files, websites, video transcription) ships in a later milestone.
          </p>
        </div>
      </div>

      <article className="panel empty-state">
        {domain.source_files.length === 0 ? (
          <p>No sources yet. This folder is empty on disk.</p>
        ) : (
          <ul>
            {domain.source_files.map((name) => (
              <li key={name}>
                <span className="inline-code">{name}</span>
              </li>
            ))}
          </ul>
        )}
      </article>
    </section>
  );
}
