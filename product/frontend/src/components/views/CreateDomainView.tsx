import { useState } from 'react';
import { BackendOverview } from '../BackendOverview';
import type { BackendState } from '../../hooks/useBackend';

type StyleId = 'socratic' | 'case' | 'guided' | 'custom';

const TEACHING_PROMPTS: Record<StyleId, { meta: string; text: string }> = {
  socratic: {
    meta: 'socratic preset · editable',
    text: "Teach through Socratic questioning. Do not immediately give final answers. Ask the learner to state assumptions, identify the relevant definition, and test one step at a time. When the learner is stuck, provide a small hint grounded in the domain's compiled sources. Prefer productive struggle over direct explanation.",
  },
  case: {
    meta: 'case-based preset · editable',
    text: "Teach through concrete cases before abstraction. Present a short scenario, ask the learner to classify what is happening, then connect the case back to the general rule. Use counterexamples when helpful. Keep each case grounded in the domain's sources and ask the learner to explain the transfer.",
  },
  guided: {
    meta: 'guided discovery preset · editable',
    text: 'Guide the learner toward discovering the idea themselves. Break the concept into small observations, reveal hints gradually, and ask the learner to summarize each step before moving on. Prefer scaffolded prompts, partial examples, and reflective checks over direct exposition.',
  },
  custom: {
    meta: 'custom prompt · editable',
    text: 'Define how Apore should teach this domain. Include when it should ask questions, when it should explain, how it should use sources, and what kind of feedback style the learner prefers.',
  },
};

const STYLE_CARDS: { id: StyleId; title: string; blurb: string }[] = [
  { id: 'socratic', title: 'Socratic', blurb: 'Asks before answering. Good for productive struggle.' },
  { id: 'case', title: 'Case-Based', blurb: 'Teaches through scenarios, examples, cases, and application.' },
  { id: 'guided', title: 'Guided Discovery', blurb: 'Hints and nudges help the learner derive the idea.' },
  { id: 'custom', title: 'Custom', blurb: 'Bring your own teaching prompt for this domain.' },
];

export function CreateDomainView({ backend }: { backend: BackendState }) {
  const [style, setStyle] = useState<StyleId>('socratic');
  const [prompt, setPrompt] = useState(TEACHING_PROMPTS.socratic.text);

  const selectStyle = (id: StyleId) => {
    setStyle(id);
    setPrompt(TEACHING_PROMPTS[id].text);
  };

  return (
    <section className="view">
      <BackendOverview backend={backend} />

      <article className="domain-create panel">
        <div className="screen-intro">
          <div>
            <p className="eyebrow">Domain scaffold</p>
            <h1>Create learning domain</h1>
            <p>
              The desktop app creates a local folder-backed workspace. The name organizes the
              sidebar; the learning objective tells Apore what this domain should become teachable as.
            </p>
          </div>
          <button className="button-secondary">Preview manifest</button>
        </div>

        <form className="domain-form" onSubmit={(e) => e.preventDefault()}>
          <label className="field">
            <span className="label">Domain name</span>
            <input className="input" defaultValue="Math" />
            <p className="help">Organizational label in the left sidebar.</p>
          </label>

          <label className="field">
            <span className="label">Model</span>
            <select className="select">
              <option>claude-opus-4-8</option>
              <option>claude-sonnet-4</option>
              <option>gpt-4.1</option>
              <option>gemini-pro</option>
            </select>
            <p className="help">
              Recommended for proof-heavy math, law, long-context synthesis, and careful tutoring.
            </p>
          </label>

          <label className="field is-wide">
            <span className="label">What are you trying to learn?</span>
            <input
              className="input"
              defaultValue="I want to learn discrete mathematics for proof-based computer science."
            />
          </label>

          <div className="choice-grid">
            {STYLE_CARDS.map((card) => (
              <button
                key={card.id}
                type="button"
                className={`choice-card${style === card.id ? ' is-selected' : ''}`}
                onClick={() => selectStyle(card.id)}
              >
                <strong>{card.title}</strong>
                <span>{card.blurb}</span>
              </button>
            ))}
          </div>

          <label className="prompt-preview">
            <span className="prompt-preview-header">
              <span className="prompt-preview-title">Teaching prompt</span>
              <span className="prompt-preview-meta">{TEACHING_PROMPTS[style].meta}</span>
            </span>
            <textarea
              className="prompt-editor"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
            />
          </label>

          <div className="form-footer">
            <button type="button" className="button-secondary">
              Cancel
            </button>
            <button type="button" className="button-primary">
              Create domain
            </button>
          </div>
        </form>
      </article>
    </section>
  );
}
