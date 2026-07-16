# Apore — Phase 2 Prototype PRD

**Project:** Apore AI (CMPP4010 Applied Research)
**Phase:** 2 — Prototype Development
**Deadline:** June 9, 2026
**Status:** Draft for redline
**Reference baseline:** [apore-lite](https://github.com/jfran03/apore-lite)

> This document supersedes the stale "flat wiki only" framing on the Phase 2 Notion page. The knowledgebase is now a graph-based representation (see §5). Open items are marked **[DECIDE]**.

---

## 1. Objective

Build the minimum working system that collects the interaction data needed to answer RQ1, and prove — on simulated students — that a learner's estimated difficulty converges toward a known target ability over a session. Phase 2 is **data-collection infrastructure**, not a learning-outcomes study. The RL *training* happens in Phase 3; Phase 2 stands up the reward-guided prompt controller and the logging that makes Phase 3 possible.

**Research questions this phase serves**

- **RQ1** — How effectively does an AI-assisted Socratic framework identify learner signals to improve RL-based practice-problem generation?
- **RQ2** — How does an RL-based generation system using those signals affect learner comprehension? *(RQ2 is largely Phase 3/4; Phase 2 only stands up the measurement plumbing.)*

---

## 2. Success criteria (Phase 2 exit)

1. A learner (real or simulated) can: provide a syllabus + content sources → system compiles a grounded knowledge graph → runs a Socratic quiz loop → captures explicit **and** implicit signals → updates a per-learner difficulty scalar per question.
2. The prerequisite graph for the discrete-math domain is constructed from trusted signals only (§5.4) and is viewable.
3. The same runtime drives an **unattended** session runner for simulated students.
4. **≥10 simulated-student sessions** show the difficulty estimate trending toward the configured target ability.
5. Swapping the LLM provider (Anthropic ↔ NVIDIA NIM) is a config change with **no architecture change** — demonstrated by at least one full session run on each.

---

## 3. Scope

### In scope
- Content ingestion (HTML, text, images, PDFs) and **syllabus** ingestion (incl. screenshots/LMS exports).
- graphify-based concept-node extraction at compile time.
- Prerequisite DAG construction from user-declared + source-explicit + source-ordinal signals.
- Graph **viewer** + **lightweight** structural editor.
- Socratic dialogue loop, wiki/graph-grounded, with citation enforcement.
- Explicit + implicit signal capture; reward computation; per-question difficulty update.
- 3-question calibration-burst cold-start.
- Provider-abstraction layer (Anthropic + NIM).
- Headless simulated-student session runner.
- Per-chapter `learner-state.md` logging at per-question granularity + per-node mastery.

### Out of scope (Phase 3+)
- GRPO fine-tuning / weight updates; IRT difficulty estimation; a knowledge-tracing model.
- Vector / GraphRAG retrieval (we use lightweight neighbor traversal, not embeddings).
- Multi-domain testing beyond discrete math; real human participants; full MathTutorBench run.
- Rich freeform graph editor; learner-state overlay visualization.
- Post-session factual-consistency audit; multi-tenant/deployment concerns (FERPA/PIPEDA).

---

## 4. Personas

- **Researcher / content setup** — creates the domain and chapter, uploads sources + syllabus, reviews and corrects the prerequisite graph, configures `AGENT.md`, runs evaluations. Declares structure; never edits live learner state.
- **Simulated student** — an LLM prompted with a fixed ability profile and misconception list (e.g. `ability: 0.4, misconceptions: ["confuses variables with constants"]`). Drives unattended sessions; ground-truth ability is known because we set it.
- **(Future) Learner** — the self-study end user. In the prototype, represented by the simulated student. The product vision has the learner provide their own syllabus + sources.

---

## 5. System architecture

### 5.1 Core principle — Interpretable Context Methodology (ICM)
The folder structure is the architecture; the LLM is the runtime; the pedagogical and RL logic live in plaintext markdown the model reads at session start. Swapping the model requires no architecture change because the intelligence is in the markdown, not the weights.

**Honesty boundary:** graphify (§5.5) is a real compile-time dependency (`pip install`), so "nothing to install" holds for the **session runtime only**, not for compilation. State this explicitly in the paper.

### 5.2 Layers
```
Polished UI ─┐
             ├─► Runtime core ──► Provider adapter ──► Anthropic | NVIDIA NIM
Headless ────┘   (orchestration)        │
session runner                          └─► Filesystem (markdown protocols, graph artifacts, learner-state.md)
```
Build the **runtime core once** and expose it two ways: to the UI and to the headless session runner. This keeps the polished UI from blocking the convergence runs (success criterion 4), since both ride the same core.

### 5.3 How the LLM "reads" the folder — Pattern A (context assembly)
An API call is stateless and has no filesystem. Therefore **the runtime is the file system; the LLM is pure text-in/text-out reasoning.** Each call, the runtime:
1. Loads `CLAUDE.md` → system prompt (harness behavior).
2. Loads the active protocol (`generate-question.md` or `extract-signals.md`).
3. Loads the relevant grounding context — the targeted concept node + its neighbors from the wiki/graph.
4. Loads current `learner-state.md`.
5. Sends the assembled prompt to the provider, parses the response, and **writes results back** to `learner-state.md`.

Agentic file-reading tools (Pattern B) are explicitly deferred — more provider-specific tool-calling surface than the timeline allows. The chapter graph is small enough that neighbor-based context assembly needs no vector retrieval.

**Division of labor (critical for cross-model reliability):** the **LLM does judgment** (rate hedging, count hints, assess correctness); the **runtime does bookkeeping** (the reward arithmetic and clamping, §7). This keeps the difficulty update deterministic and identical across providers, including weaker open models, and it tightens the ICM story rather than weakening it.

### 5.4 Knowledge representation — two graphs, two purposes
| Graph | Built by | Purpose | Editable? |
|-------|----------|---------|-----------|
| **Relatedness graph** | graphify default | Grounding/retrieval — neighbors for Socratic context | No (auto) |
| **Prerequisite DAG** | adapted extraction + user review | Traversal order + concept depth/difficulty | Yes (structural) |

Conflating these is the failure mode. graphify produces *relatedness* (associations, communities, "god nodes"), **not** prerequisite ordering, and connectedness ≠ difficulty. So we derive a separate prerequisite DAG.

**Prerequisite edges are created only from trusted signals — never inferred.** In priority:
1. **User-declared** — authoritative; overrides everything. Supplied via the learner's **syllabus** (the structural source). A novice cannot map dependencies they haven't learned, but their syllabus already encodes the *what and when*, authored by someone who can.
2. **Source-explicit** — an explicit statement linking concepts ("recall that…", "building on…"). Maps to graphify's `EXTRACTED` confidence tier.
3. **Source-ordinal** — the sequence/section structure of the syllabus and materials.

`INFERRED` / `AMBIGUOUS` edges are **dropped** from the prerequisite DAG. If the system is unsure, it omits the edge; the user adds it via the editor.

**Depth derivation:** depth = longest path from a root (topological rank) in the DAG. The user declares *edges*, not float scores; the depth number falls out of structure. Declaring "power sets builds on special sets" is more natural and more defensible than assigning "power sets = 0.8".

**Constraints:**
- The prerequisite graph must be a **DAG** — detect and break cycles before depth computation.
- Ordinal order is a **partial-order constraint** (nothing later is a prerequisite of something earlier) plus a sensible default chain. It is **not** strict linearity — real structure has parallel branches (e.g., Venn Diagrams and Set Operations may both depend on Special Sets without depending on each other). The user prunes/branches the default chain in the editor.

### 5.5 graphify integration (compile-time preprocessor)
[graphify](https://github.com/safishamsi/graphify) (`graphifyy` on PyPI, MIT) runs at compile time when sources are ingested; `--update` handles incremental re-ingestion. Pipeline: non-code sources are normalized to text (PDF text-extracted, video transcribed locally, images via vision, md/html read directly), grouped by directory, packed into token-budgeted chunks, and run through an LLM extraction prompt that emits nodes + edges as JSON with confidence tags.

**We reuse:** the ingest/normalization, directory-aware chunking, node ID convention (`{stem}_{entity}`), node schema, and the confidence model.
**We replace:** the relation taxonomy and the system prompt — see the adapted prerequisite-extraction prompt in **Appendix A** (fork the prompt; smallest surface area for a 12-day window).

graphify itself supports `--backend claude` and `--backend openai` (OpenAI-compatible), so even the compile step is provider-swappable and can point at NIM.

**Research framing:** KG construction is now off-the-shelf. The novelty is the RL difficulty-calibration loop + Socratic signal capture on a grounded prerequisite graph — **not** the graph construction. Scope the paper claim accordingly and attribute graphify (MIT).

---

## 6. Functional requirements

### FR-1 Knowledgebase
- **FR-1.1** Ingest content sources (HTML, text, images, PDF) into a chapter's `sources/`.
- **FR-1.2** Ingest a **syllabus** source (text, export, or screenshot) and extract an ordered topic → concept tree (order is explicit in the document → `EXTRACTED`-grade).
- **FR-1.3** Run adapted extraction (Appendix A) to produce concept **nodes** and candidate **prerequisite edges** tagged by provenance tier.
- **FR-1.4** Assemble the prerequisite DAG; validate acyclicity; compute topological depth per node.
- **FR-1.5** Persist graph artifacts as plaintext in the chapter folder (so the session runtime stays ICM-pure).
- **FR-1.6** Surface a wiki page (or graph-node content) per concept with `> Source:` citations; gap-surfacing behavior when a concept is absent.

### FR-2 Graph viewer / editor
- **FR-2.1** Render the prerequisite DAG for a domain/chapter (viewing leverages graphify's `graph.html`-style output; nearly free).
- **FR-2.2** Lightweight structural edit: add / remove / redirect a prerequisite edge → recompute depth → persist to chapter config.
- **FR-2.3** "Play with difficulty" edits the **structure** only. The per-learner difficulty scalar (§7) is **read-only** in the UI — editing it would corrupt RQ1 ground truth.
- **FR-2.4** The DAG is **frozen** per measured simulated-student run; structural edits are a setup-time activity.
- *(Phase 3: rich freeform editor; learner-state overlay.)*

### FR-3 Tutor loop
- **FR-3.1** `generate-question.md`: select the next concept by DAG traversal (only nodes whose prerequisites are covered); choose question type (recall → apply → synthesis) escalating as the scalar approaches the concept's depth ceiling; ground entirely in the concept's content; record concept, type, intended difficulty.
- **FR-3.2** Socratic mode (SocraticLM **Dean–Teacher–Student**): Dean sets constraints (no direct answers), Teacher runs dialogue, Student is the learner. Every hint cites a specific source/node. Each hint = one turn; log on exit.
- **FR-3.3** Citation/grounding constraint: never fill gaps from pre-training; surface gaps and refer to sources.

### FR-4 Signal capture + difficulty calibration
- **FR-4.1** After **every** question, capture explicit signals (difficulty rating easy/ok/hard, final correctness, hint count) and implicit signals (turns to resolution, hedging language, response length, learner question-asking).
- **FR-4.2** The LLM emits raw signal *scores*; the **runtime** computes reward `R` and the difficulty update deterministically (§7).
- **FR-4.3** Append one fully-populated row to the `learner-state.md` question log and update current difficulty + per-node mastery.
- **FR-4.4** Cross-validate explicit vs implicit signals; flag inconsistencies (e.g. rated "easy" but 6 hints / 15 turns) — protects RQ1 validity.

### FR-5 Cold-start — 3-question calibration burst
- **FR-5.1** Before the adaptive loop, select **3 concepts at low / mid / high topological depth** and serve one probe question each.
- **FR-5.2** Set the initial difficulty scalar from observed performance on the burst (not self-report). The DAG depth supplies the difficulty tags the burst requires — this is what unblocks pulling the burst into Phase 2.
- **FR-5.3** Accept the UX cost: the first 3 questions are non-adaptive.

### FR-6 Session runner (headless)
- **FR-6.1** Drive a full session unattended using a simulated-student LLM with a fixed ability profile + misconceptions.
- **FR-6.2** Reuse the runtime core (no separate logic path from the UI).
- **FR-6.3** Run ≥10 sessions; emit per-session difficulty trajectories for convergence analysis.
- **FR-6.4** Throttle calls to respect NIM's ~40 RPM limit (the tutor↔student loop makes ~2 calls/turn).

### FR-7 Provider abstraction
- **FR-7.1** One interface: `(system_prompt, messages, model) → text`, with two adapters.
- **FR-7.2** Anthropic adapter — Messages API (`system` is a top-level param). Primary.
- **FR-7.3** NIM adapter — OpenAI-compatible `/v1/chat/completions` at `https://integrate.api.nvidia.com/v1`, `nvapi-…` key (free hosted catalog; ~40 RPM). Used as the model-agnosticism swap-test.
- **FR-7.4** Provider + model selected by config; switching requires no other change.

---

## 7. Reward & difficulty model

Carried over from the Phase 2 design, with the arithmetic owned by the runtime.

- **Scalar:** per learner, clamped to `[0.1, 0.9]`. Initialized by the calibration burst (FR-5).
- **Update:** `new_difficulty = clamp(current_difficulty + α · R)`, `α = 0.1`.
- **Reward:** `R = 0.4·explicit_rating + 0.3·correct + 0.2·hint_score + 0.1·implicit_score`, clamped to `[-1, +1]`.
- **Signal scoring:** rating easy=+1 / ok=0 / hard=−1; correct yes=+0.5 / no=−0.5; hints 0=+0.2 / 1–2=0 / 3+=−0.2; hedging 0=+0.1 / 1–2=0 / 3+=−0.1; turns ≤3=+0.1 / 4–6=0 / 7+=−0.1.
- **POMDP framing:** State = (graph + dialogue history + difficulty state); Action = next question; Observation = learner response; Reward = composite above.

**Two difficulty dimensions:** (1) concept depth = topological position in the DAG; (2) question type (recall/apply/synthesis). Logged separately so Phase 3 can attribute changes to each.

---

## 8. Data contracts

### 8.1 `learner-state.md` (sole data store, per chapter)
- Initialization block (calibration-burst result → starting scalar).
- Current difficulty scalar.
- **Per-node mastery map** keyed to graph node IDs.
- **Question log** — one row per question: `Q# | session | date | concept | question type | intended difficulty | explicit rating | correct | hints | turns | hedging | reward R | new difficulty`.

### 8.2 Prerequisite graph artifact (plaintext, e.g. `concept-graph.json`)
- Nodes: `{ id, label, source_file, depth }`.
- Edges: `{ source, target, relation: "prerequisite_of", provenance: "user_declared|source_explicit|source_ordinal", source_location }`.
- Invariant: acyclic.

### 8.3 `CHAPTER.md` additions
- Topic → concept index derived from the syllabus.
- Pointer to the confirmed prerequisite graph artifact.

---

## 9. Non-functional requirements
- **NFR-1 Model-agnostic** — no provider-specific logic outside the adapter (FR-7).
- **NFR-2 Deterministic bookkeeping** — reward/difficulty math in the runtime, reproducible across models.
- **NFR-3 Reproducible runs** — fixed seeds/profiles for simulated students; frozen DAG per run.
- **NFR-4 ICM-pure session runtime** — the loop reads only plaintext artifacts; no code logic in the pedagogy path.
- **NFR-5 No ethics-board dependency** — simulated students + automated benchmarks only.
- **NFR-6 Rate-limit resilience** — throttle/backoff for NIM's 40 RPM.

---

## 10. Evaluation plan
- **Layer 1 — Pedagogical quality:** run Socratic responses through MathTutorBench's automated reward model (scaffolding, mistake detection, answer-withholding); comparable to published baselines. No humans. *(Full run is Phase 3+; Phase 2 wires the harness.)*
- **Layer 2 — Calibration accuracy (novel contribution):** simulated students with known ability; measure whether the difficulty estimate converges to true ability over N questions. ≥10 sessions for Phase 2.
- **Layer 3 — Domain generality:** run on the discrete-math domain to validate the plug-and-play architecture on learner-uploaded content.

**Reviewer framing:** simulated benchmarks validate the *mechanism* (calibration works); human studies would validate *outcomes* and are explicitly out of scope given timeline + ethics. Standard in the RL-tutoring literature (UCO, SocraticLM, Scarlatos 2025).

---

## 11. Risks & open issues
- **Prerequisite inference is harder than relatedness.** Mitigated by trusted-signal-only edges (§5.4) + human review; never `INFERRED`.
- **Ordinal ≠ strict prerequisite.** Default chain may over-connect; user prunes parallel branches.
- **Calibration burst** front-loads 3 non-adaptive questions and is only as good as the depth ordering — hence syllabus quality matters.
- **graphify/ICM tension** — compile-time install dents the "nothing to install" claim; bounded to compile, disclosed in paper.
- **Research validity** — freeze DAG during runs; flag explicit/implicit signal inconsistencies; weak open models may follow protocols less precisely (runtime-owned arithmetic mitigates).
- **[DECIDE]** Exact node granularity (one concept per syllabus item vs finer) for discrete-math chapter 1.
- **[DECIDE]** Where the graph viewer/editor lives in the UI information architecture.

---

## 12. Phase 3 handoff
GRPO fine-tuning (e.g. Qwen2.5-7B-Instruct), IRT cold-start, knowledge-tracing integration, rich graph editor, learner-state overlay demo, post-session factual-consistency audit, full MathTutorBench run, and any multi-domain expansion. The per-question logs and frozen-DAG runs produced in Phase 2 are the inputs.

---

## Appendix A — Adapted prerequisite-extraction prompt

Forked from graphify's `_EXTRACTION_SYSTEM`: same node schema and confidence discipline, directed prerequisite relation, trusted-signal-only rule.

```
You are a prerequisite-graph extraction agent for a tutoring system.
From the provided course materials and syllabus, extract CONCEPT NODES and
DIRECTED PREREQUISITE EDGES. Output ONLY valid JSON — no prose, no fences.

NODES — every distinct concept taught in the materials.
  id: lowercase [a-z0-9_], format {stem}_{concept}
  label: human-readable name
  source_file: relative path
  source_location: section/heading if available, else null

EDGES — a prerequisite edge {source} -> {target} means "{source} must be
understood before {target}." Emit an edge ONLY when justified by one of:
  - source_explicit: the text explicitly links them ("recall that...",
    "building on...", "as defined in section X"). Confidence EXTRACTED.
  - source_ordinal: the syllabus/section sequence places {source} before
    {target} within the same topic or an earlier topic. Confidence ORDINAL.
  Record provenance on every edge.

HARD RULES
  - NEVER create an edge from topical similarity, co-occurrence, or your own
    background knowledge. If a prerequisite is not declared or stated or
    implied by order, OMIT it — a human will add it later.
  - Direction matters: earlier/foundational -> later/dependent. Never the reverse.
  - Do not introduce cycles.

Output schema:
{"nodes":[{"id":"...","label":"...","source_file":"...","source_location":null}],
 "edges":[{"source":"node_id","target":"node_id","relation":"prerequisite_of",
           "provenance":"source_explicit|source_ordinal",
           "confidence":"EXTRACTED|ORDINAL","source_location":null}]}
```

*User-declared edges (provenance `user_declared`, authoritative) are merged in after this pass, from the syllabus structure and any manual edits in the graph editor.*

---

## Appendix B — Folder structure (updated)

```
apore/
├── CLAUDE.md                         ← harness (any LLM reads first)
├── AGENT.md                          ← RL config: reward weights, difficulty bounds, α
│
├── {domain}/
│   ├── DOMAIN.md                     ← scope, goal, tutor style, chapter index
│   └── chapters/
│       └── {N}-{chapter}/
│           ├── CHAPTER.md            ← compile status, topic index, graph pointer
│           ├── sources/              ← gitignored: content + syllabus
│           ├── wiki/                 ← compiled concept content (grounding)
│           ├── concept-graph.json    ← prerequisite DAG (nodes + depth + edges)
│           ├── graph.json            ← graphify relatedness graph (grounding neighbors)
│           └── progress/
│               ├── questions.md
│               ├── ratings.md
│               ├── feedback.md
│               └── learner-state.md  ← scalar + per-node mastery + per-question log
│
└── shared/
    └── protocols/
        ├── compile.md                ← wraps graphify + assembles DAG
        ├── build-graph.md            ← adapted extraction + DAG validation + depth
        ├── calibrate.md              ← 3-question burst cold-start
        ├── generate-question.md      ← graph-driven, difficulty-calibrated
        └── extract-signals.md        ← per-question reward (LLM scores, runtime math)
```

---

## Appendix C — Key references
- **graphify** — node extraction reused; relation model replaced. MIT. github.com/safishamsi/graphify
- **ICM** — Van Clief & McDermott (2026), arXiv:2603.16021 — model-agnostic architecture.
- **SocraticLM** (NeurIPS 2024) — Dean–Teacher–Student Socratic pattern.
- **MathTutorBench** (EMNLP 2025) — automated pedagogical benchmark. arXiv:2502.18940
- **UCO** (arXiv:2511.08873) — RL + ZPD with simulated students.
- **Can LLMs Simulate Real Students?** (2025) — arXiv:2507.08232 — validates the simulated-student approach.