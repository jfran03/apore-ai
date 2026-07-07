import { useState, type FormEvent } from 'react';
import { createDomain } from '../../api/client';
import type { WorkspaceDomain } from '../../api/types';
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

export function CreateDomainView({
  backend,
  onCreated,
  onCancel,
}: {
  backend: BackendState;
  onCreated: (domain: WorkspaceDomain) => void;
  onCancel: (() => void) | null;
}) {
  const [style, setStyle] = useState<StyleId>('socratic');
  const [prompt, setPrompt] = useState(TEACHING_PROMPTS.socratic.text);
  const [name, setName] = useState('');
  const [objective, setObjective] = useState('');
  const [model, setModel] = useState('auto');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectStyle = (id: StyleId) => {
    setStyle(id);
    setPrompt(TEACHING_PROMPTS[id].text);
  };

  const modelOptions = ['auto'];
  if (backend.provider?.active_model) modelOptions.push(backend.provider.active_model);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const created = await createDomain({
        name: name.trim(),
        objective: objective.trim(),
        teaching_style: style,
        teaching_prompt: prompt,
        model_preference: model,
      });
      onCreated(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }

  return (
    <section className="view">
      {backend.status === 'offline' && (
        <div className="alert is-error">
          Backend offline. Start it with{' '}
          <span className="inline-code">uvicorn apore.api.app:app --port 8000</span> from{' '}
          <span className="inline-code">product/backend</span>.
        </div>
      )}

      <article className="domain-create panel">
        <div className="screen-intro">
          <div>
            <p className="eyebrow">Domain scaffold</p>
            <h1>Create learning domain</h1>
            <p>
              Creates a self-contained folder under your Apore data directory. The name
              organizes the sidebar; the learning objective tells Apore what this domain
              should become teachable as.
            </p>
          </div>
        </div>

        <form className="domain-form" onSubmit={submit}>
          <label className="field">
            <span className="label">Domain name</span>
            <input
              className="input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Discrete Math"
            />
            <p className="help">Organizational label in the left sidebar.</p>
          </label>

          <label className="field">
            <span className="label">Model</span>
            <select className="select" value={model} onChange={(e) => setModel(e.target.value)}>
              {modelOptions.map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
            <p className="help">
              {backend.provider?.active_provider
                ? `Active provider: ${backend.provider.active_provider}`
                : 'No provider configured yet — add a key in Settings.'}
            </p>
          </label>

          <label className="field is-wide">
            <span className="label">What are you trying to learn?</span>
            <input
              className="input"
              value={objective}
              onChange={(e) => setObjective(e.target.value)}
              placeholder="I want to learn discrete mathematics for proof-based computer science."
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

          {error && <div className="alert is-error">{error}</div>}

          <div className="form-footer">
            {onCancel && (
              <button type="button" className="button-secondary" onClick={onCancel}>
                Cancel
              </button>
            )}
            <button
              type="submit"
              className="button-primary"
              disabled={!name.trim() || busy || backend.status !== 'online'}
            >
              {busy ? 'Creating…' : 'Create domain'}
            </button>
          </div>
        </form>
      </article>
    </section>
  );
}
