import type { WorkspaceDomain } from '../../api/types';

interface GraphViewProps {
  domain: WorkspaceDomain;
}

export function GraphView({ domain }: GraphViewProps) {
  const ready = domain.chapters.filter((chapter) => chapter.has_concept_graph);

  return (
    <section className="view">
      <div className="screen-intro">
        <div>
          <p className="eyebrow">Adaptive curriculum</p>
          <h1>Curriculum map</h1>
          <p>
            Interactive graph editing ships in a later milestone. Compiled chapters in this domain
            today:
          </p>
        </div>
      </div>

      <article className="panel empty-state">
        {ready.length === 0 ? (
          <p>No compiled curriculum yet.</p>
        ) : (
          <ul>
            {ready.map((chapter) => (
              <li key={chapter.id}>
                <span className="inline-code">{chapter.id}</span> — concept graph
                {chapter.has_question_bank ? ' · question bank' : ''} · {chapter.wiki_count}{' '}
                wiki files
              </li>
            ))}
          </ul>
        )}
      </article>
    </section>
  );
}
