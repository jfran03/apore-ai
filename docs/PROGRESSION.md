# Concept-Based Progression

Design proposal for pivoting Apore's learner-facing progression from a
per-session difficulty scalar to a **per-concept mastery estimate**, derived
from the existing append-only question logs via Bayesian Knowledge Tracing
(BKT). No runtime or frontend code changes in this document; it is the
architecture contract for a later implementation pass.

**Decisions locked for this proposal:**

| Decision | Choice |
|----------|--------|
| Mastery model | BKT (per-concept `P(L)`) |
| Forgetting / time decay | None (`P(F) = 0`); deferred |
| Persistence | **Option A**: derive on read from session question logs (no new stored state) |
| Learner-facing surface | Inline mastery **percentage** in the study-session concept picker only |
| `/graph` or `/progress` dashboard | Out of scope (separate ownership) |
| Global RL difficulty scalar | Unchanged; remains the RQ1 convergence signal |

---

## 1. Current state and the problem

### 1.1 What the runtime tracks today

Each study session is a UUID markdown file under
`program/backend/sessions/{id}.md` (created by `POST /sessions`, I/O in
[`apore/runtime/state.py`](program/backend/apore/runtime/state.py)). The file
holds two numeric layers:

1. **Scalar** (`## Scalar`) — one float in `[0.1, 0.9]`, initial `0.5`. Updated
   after every graded question by the RL reward in
   [`apore/runtime/reward.py`](program/backend/apore/runtime/reward.py):

   ```
   R = 0.4·rating + 0.3·correct + 0.2·hint + 0.1·implicit   (clamped [-1, 1])
   new_difficulty = clamp(scalar + α · R, 0.1, 0.9)         (α = 0.1)
   ```

2. **Mastery** (`## Mastery`) — a `concept_id: float` map. Updated in
   [`apore/runtime/core.py`](program/backend/apore/runtime/core.py)
   `finalize_turn` with a crude heuristic: `+0.15` if `correct == yes`,
   `-0.10` if `correct == no`, clamped to `[0, 1]`. Concept selection in
   [`apore/knowledge/chapter.py`](program/backend/apore/knowledge/chapter.py)
   `select_next_concept()` treats mastery `≥ 0.7` as "covered."

Both layers are **session-scoped in the API**: every `POST /sessions` starts
from scalar `0.5` and an empty mastery map. There is no cross-session learner
profile in the live path (the sim harness can optionally share one file; the
API does not).

### 1.2 What already persists (and is underused)

Every graded question appends a self-describing row to `## Question Log`:

```
| Q# | session | date | question_id | concept | question_type |
| intended_difficulty | explicit_rating | correct | hints | turns |
| hedging | reward_R | new_difficulty |
```

These rows survive across sessions on disk. The "reset" is only in-memory /
per-session scalar+mastery, **not** the historical evidence. That evidence is
exactly what a knowledge-tracing model needs: an ordered sequence of
correct/incorrect observations per concept, plus optional richer signals
(hints, turns, hedging, rating).

Concepts themselves are already first-class. Each chapter's
`concept-graph.json` defines nodes (`id`, `label`, `depth`, `source_file`),
`prerequisite_of` edges, and a `teaching_order` DAG. The study UI and question
bank already key on these IDs.

### 1.3 What the learner sees today

During a session, the UI shows question index (`N of M`) and the session
**difficulty** scalar ([`ScalarBadge`](program/frontend/src/components/ScalarBadge.tsx)).
`SessionStateResponse.mastery` is typed in the frontend but **never rendered**.
The `/graph` route is a placeholder. Starting a session, the concept picker
lists labels and bank counts ("5 questions") with no indication of past
performance.

**Gap:** the learner cannot tell which concepts they are good or bad at across
sessions. The researcher cannot read a durable per-concept estimate without
manually aggregating logs.

### 1.4 Goals of this pivot

1. Make **per-concept mastery** the learner-facing progression signal
   ("what am I / aren't I good at?").
2. Compute that signal from evidence we already log (no new capture pipeline).
3. Keep the global RL **difficulty scalar** intact for RQ1 / question-type
   escalation.
4. Surface mastery with the smallest useful UI: a percentage beside each
   concept in the study-session picker.

---

## 2. Competitor and learning-science context (brief)

| System | Unit of progress | How strength is estimated | Learner surface |
|--------|------------------|---------------------------|-----------------|
| **Duolingo** | Lexeme / skill | Half-life regression (recall decays over time); practice targets weak/decayed items | Strength meters; "Practice Weak Skills" |
| **Brilliant** | Concept along a Learning Path | Tracks mastered vs stuck; practice sets fill gaps | Path progress, XP/leagues (motivation, not mastery) |
| **Classical ITS** | Knowledge component | Bayesian Knowledge Tracing: latent `P(L)` updated per response | Mastery bars, "ready to move on" gates |

Apore already has a concept DAG and per-question correctness logs. That maps
cleanly to **BKT per concept**. Duolingo-style decay is valuable later but is
explicitly deferred (`P(F) = 0`). Brilliant-style path dashboards are owned
elsewhere (`/graph`); this proposal only needs the scalar that such a view
would later consume.

---

## 3. Proposed model: BKT per concept (no decay)

### 3.1 Latent state

For each concept `c` in a chapter's `concept-graph.json`, maintain a latent
mastery probability:

```
P(L_c) ∈ [0, 1]
```

Standard BKT parameters (global defaults for v1; optionally later per
`question_type`):

| Param | Symbol | Meaning | Proposed default |
|-------|--------|---------|------------------|
| Prior | `P(L₀)` | Probability concept is already known before any observation | `0.0` (cold start; UI shows "New" until first observation) |
| Learn | `P(T)` | Probability of transitioning unlearned → learned after an opportunity | `0.1` |
| Guess | `P(G)` | Probability of a correct answer despite non-mastery | `0.2` |
| Slip | `P(S)` | Probability of an incorrect answer despite mastery | `0.1` |
| Forget | `P(F)` | Probability of learned → unlearned between opportunities | **`0.0` (no decay)** |

Defaults are conventional ITS starting points, not fitted. The same logs that
drive inference are the training set for later EM / param fitting (see §4.4).

### 3.2 Observation and update

**Primary observation** for opportunity `t` on concept `c`: binary correctness
from the question log (`correct` ∈ `{yes, no}`).

Let `p = P(L_c)` before the observation, and `obs = 1` if correct else `0`.

**Emission (predict):**

```
P(correct | L)     = 1 − P(S)
P(correct | ¬L)    = P(G)
P(obs=1)           = p · (1 − P(S)) + (1 − p) · P(G)
```

**Posterior (Bayes):**

```
If obs = 1 (correct):
  p' = p · (1 − P(S)) / P(obs=1)

If obs = 0 (incorrect):
  p' = p · P(S) / (1 − P(obs=1))
```

**Transition (learn; no forget):**

```
P(L) ← p' + (1 − p') · P(T)
```

Replay this recurrence in chronological order over all observations for `c`.
The final `P(L)` is the concept's mastery estimate.

### 3.3 Optional signal modulation (v1.1, recommended but not required for ship)

The log already carries `hints`, `turns`, `hedging`, and `explicit_rating`.
Vanilla BKT ignores them. A lightweight extension treats them as **evidence
quality**, not a second latent:

| Condition | Modulation |
|-----------|------------|
| `correct=yes` and `hints ≥ 3` | Treat as weaker evidence of mastery: temporarily raise effective `P(S)` for this update (e.g. `min(0.4, P(S) + 0.15)`), so a heavily scaffolded correct answer pulls `P(L)` up less |
| `correct=no` and `explicit_rating=easy` | Already flagged as inconsistency in the tutor harness; do not invent a special BKT rule in v1 — log and leave |
| High `hedging` / long `turns` with `correct=yes` | Same direction as hints: softer positive update |

v1 can ship on binary `correct` alone. Modulation is a documented extension so
implementers do not discard the richer columns.

### 3.4 Mastery bands (learner-facing and selection)

Align with the existing `0.7` "covered" threshold in `select_next_concept`:

| Band | `P(L)` range | Display intent |
|------|--------------|----------------|
| New | `n_observed = 0` | Neutral "New" / "—" (not `0%`) |
| Struggling | `(0, 0.3)` | Needs practice |
| Learning | `[0.3, 0.7)` | In progress |
| Proficient | `≥ 0.7` | Covered for selection / weak-points filtering |

`weak_points` focus mode should consume derived BKT mastery (concepts with
`P(L) < 0.7` and `n_observed > 0`, falling back to uncovered / never-seen as
today).

### 3.5 Coexistence with the global difficulty scalar

These are **two different signals**:

| Signal | Scope | Role | Learner-facing? |
|--------|-------|------|-----------------|
| **Difficulty scalar** | Per session (today); conceptually per learner | Question-type escalation (`recall` / `apply` / `synthesis` via `type_for_scalar`); RQ1 convergence target | Yes (session `ScalarBadge`), but not "what I'm good at" |
| **Concept mastery `P(L)`** | Per concept, cross-session | Concept selection, weak points, learner self-awareness | Yes (picker percentage) |

The POMDP / reward loop in PRD §7 is unchanged. BKT does **not** replace `R`
or `α`. A future option (out of scope) is per-concept ability / difficulty;
do not conflate that with mastery here.

The in-session `## Mastery` increment map (`+0.15` / `-0.1`) becomes
**redundant** once derive-on-read BKT is live. Implementation may stop writing
it, or keep writing it temporarily for backward compatibility with any
consumers of the session markdown; selection and UI must read BKT-derived
values, not the legacy map.

---

## 4. Derive on read (Option A)

### 4.1 Principle

Mastery is a **pure function** of the append-only question logs. No
`learner-state.md` write-back, no migration of historical sessions, no risk of
stored `P(L)` drifting from the log. Changing BKT defaults and re-deriving
retrospectively is free.

This is closer to the PRD's "folder structure is the architecture / logs are
the source of truth" ethos than an incremental store (Option B), and matches
prototype scale (dozens to low thousands of rows).

### 4.2 Algorithm

```
Input:  knowledge_source  (e.g. "domain:discrete-math/01-set-theory")
        concept_ids       (from concept-graph.json teaching_order / nodes)
        BKT params

1. Enumerate program/backend/sessions/*.md
   (skip non-session files such as _bank_gen.md)

2. For each file:
     meta = read_session_meta(path)          # state.py
     if meta.knowledge_source != knowledge_source: continue
     rows = parse_question_log(path)         # reuse header split ~state.py L334

3. Flatten rows; drop rows where correct ∉ {"yes","no"}
   (skip blank / skipped / malformed)

4. Group by concept; within each group sort by (date, Q#) ascending

5. For each concept_id in the chapter graph:
     if no rows:  { p_mastery: null, band: "new", n_observed: 0 }
     else:        replay §3.2 → { p_mastery, band, n_observed }

6. Return map keyed by concept_id
```

**Scoping rules:**

- Match `knowledge_source` **exactly**. Never mix `_pytest` fixtures with
  `discrete-math`.
- Concept IDs unknown to the current graph (renamed / deleted nodes) may be
  omitted from the response or returned under an `orphans` field; the picker
  only displays graph concepts.
- Empty sessions (header only, no data rows) contribute nothing.

### 4.3 Optional caching

At prototype scale, full scan on each `GET` is acceptable. If needed:

- In-memory cache keyed by `knowledge_source`, invalidated when any matching
  session file's mtime changes or when `finalize_turn` appends a log row for
  that source.
- Do **not** write a durable cache file in v1; that reintroduces Option B
  drift.

### 4.4 Param fitting later

The same aggregated `(concept, ordered correct/incorrect sequence)` data is
the training set for EM / pyBKT-style fitting of `P(L₀)`, `P(T)`, `P(G)`,
`P(S)`. Document that fitted params would live in a small plaintext config
(e.g. beside `AGENT.md` or in chapter metadata), still with derive-on-read
inference. Fitting is Phase 3+ research work, not required to ship the
percentage UI.

### 4.5 Relationship to PRD §8.1 `learner-state.md`

PRD §8.1 describes a per-chapter `learner-state.md` holding scalar + mastery +
question log. The runtime evolved to **per-session UUID files** that already
embed those sections. Under Option A:

- The **question log** (distributed across session files, scoped by
  `knowledge_source`) is the durable store.
- The **per-node mastery map** is a **derived view**, not a separately
  persisted block.
- A single rolled-up `learner-state.md` is **not required** for this design.
  If a later milestone wants one for human inspection, it should be a
  generated artifact (export), not the source of truth.

---

## 5. API surface

### 5.1 New endpoint

```
GET /learner/mastery?knowledge_source=domain:{domain_id}/{chapter_id}
```

**Response (sketch):**

```json
{
  "knowledge_source": "domain:discrete-math/01-set-theory",
  "params": {
    "p_L0": 0.0,
    "p_T": 0.1,
    "p_G": 0.2,
    "p_S": 0.1,
    "p_F": 0.0
  },
  "concepts": {
    "what_is_a_set": {
      "p_mastery": 0.82,
      "band": "proficient",
      "n_observed": 7,
      "display_pct": 82
    },
    "venn_diagrams": {
      "p_mastery": null,
      "band": "new",
      "n_observed": 0,
      "display_pct": null
    }
  }
}
```

Notes:

- `display_pct` is `round(p_mastery * 100)` when `n_observed > 0`, else `null`
  (UI renders "New").
- `band` is computed server-side so clients stay consistent.
- 400 if `knowledge_source` is missing or malformed; 404 if the chapter /
  domain does not exist.

### 5.2 `SessionStateResponse.mastery` semantics

Today: in-session increment map, resets each session.

**Proposed:** same field shape `Record<string, number>`, but values are
BKT-derived `P(L)` for concepts observed so far **including prior sessions**
for this `knowledge_source` (plus any updates from the current session's log
rows already written). Concepts with no observations may be omitted or sent
as absent (not `0.0`).

Callers that treated `0.0` as "unknown" must switch to "key absent / New."

### 5.3 Client fetch timing

On the study preamble (`Study.tsx` chat-config step), when loading the concept
list today the client already calls wiki preview + question bank. Add:

```
getLearnerMastery(knowledge_source)
```

in parallel. Merge `display_pct` / `band` onto each `ConceptOption`. Failure
of the mastery endpoint must not block starting a session; fall back to
omitting percentages (same as today).

---

## 6. Learner-facing UX (minimal)

**Scope:** one inline signal on the existing study-session concept picker.
No `/graph`, no `/progress` dashboard, no DAG overlay, no XP/streaks
(PRODUCT.md anti-references: Duolingo gamification).

Using the `impeccable` product register: precise, calm research instrument;
system state visible; Cursor Orange scarce; hairlines over shadows; JetBrains
Mono for numeric data.

### 6.1 Placement

In [`Study.tsx`](program/frontend/src/pages/Study.tsx) preamble, Concepts
section, each `.study-concepts__row` today is:

```
[checkbox]  Concept label                    N questions
```

**Proposed:**

```
[checkbox]  Concept label              72% · 5 questions
```

or, for never practiced:

```
[checkbox]  Concept label            New · 5 questions
```

Mastery sits **immediately left of** the existing `.study-concepts__count`,
still on the trailing side of the row. Do not displace the question-bank count;
researchers still need inventory awareness when selecting scope.

### 6.2 Visual treatment

| Element | Spec |
|---------|------|
| Mastery percentage | `{typography.code}` / `--font-mono` (JetBrains Mono), `{typography.caption}` size (~13px), tabular feel matching `.study-concepts__count` |
| Color when `proficient` (`≥ 70%`) | `{colors.semantic-success}` (`#1f8a65`) |
| Color when `learning` | `{colors.body}` (`#5a5852`) |
| Color when `struggling` | `{colors.semantic-error}` (`#cf2d56`) at reduced emphasis, or `{colors.ink}` with no fill; prefer ink + band only if error red feels alarmist in a picker. **Recommendation:** struggling = `{colors.ink}`, learning = `{colors.muted}`, proficient = `{colors.semantic-success}` |
| "New" | `{colors.muted-soft}`, same mono caption; literal text `New` (not `0%`, not `—` alone; "New" is clearer for empty evidence) |
| Separator | middle dot `·` in `{colors.muted-soft}` between mastery and count |
| No progress bars, rings, or fill tracks in the row | PRODUCT.md bans flashcard/progress-ring-as-primary-reading; the number is enough |
| No orange | Orange remains the Start Session CTA only |

Suggested BEM additions (implementation later):

```
.study-concepts__mastery
.study-concepts__mastery--new
.study-concepts__mastery--struggling
.study-concepts__mastery--learning
.study-concepts__mastery--proficient
```

### 6.3 Accessibility

- Row remains a single `<label>` hit target (≥44px).
- Expose mastery to AT via the visible text (e.g. `72% · 5 questions`) or an
  `aria-description` on the row: `"Mastery 72 percent, proficient"`.
- Do not rely on color alone for band; the percentage (or "New") carries meaning.
- Loading: omit mastery until the endpoint returns; do not flash `0%`.

### 6.4 Interaction with Weak points mode

No new control. When Focus is `Weak points`, selection logic already prefers
low mastery. The percentages make that mode legible: learners can see why a
concept is in scope. Optional later (out of scope): auto-check concepts with
`band ∈ {struggling, learning}` when Weak points is selected.

### 6.5 Explicit non-goals for this surface

- Compiled Wiki / Setup concept list (depth rows): **not** this pass.
- Graph page mastery overlay: **not** this pass.
- Session sidebar history showing mastery: **not** this pass.
- Animating percentage changes: unnecessary on the preamble (static snapshot
  at load).

---

## 7. PRD / DESIGN reconciliation

### 7.1 Proposed PRD edits (when implementing)

**§3 Out of scope (L49)** — today:

> GRPO fine-tuning / weight updates; IRT difficulty estimation; a knowledge-tracing model.

**Propose:** remove "a knowledge-tracing model" from Phase 2 non-goals; add a
Phase 2 in-scope bullet:

> Derive-on-read BKT per-concept mastery from session question logs; expose via
> API; show percentage in the study concept picker.

Keep IRT and GRPO as Phase 3+.

**§7 Reward & difficulty model** — add a short subsection:

> **Concept mastery (orthogonal):** per-concept `P(L)` via BKT over the
> question log; does not alter `R`, `α`, or the difficulty scalar. See
> `PROGRESSION.md`.

**§8.1 `learner-state.md`** — clarify:

> Question logs may live in per-session UUID files. Per-node mastery is a
> derived view over those logs (BKT), not a separately authored write-ahead
> map. A rolled-up `learner-state.md` is optional export, not the source of
> truth.

**Phase 3 list (L237)** — today lists "knowledge-tracing integration." Reframe
to: "fitted BKT parameters / forgetting (`P(F)`); IRT; learner-state overlay
on the graph viewer."

### 7.2 RQ1 interaction

RQ1 asks whether the difficulty estimate converges toward known ability.
BKT mastery is **not** that estimate. Implementing BKT:

- Does **not** change reward arithmetic or scalar updates.
- Must not feed back into the scalar in Phase 2 (would confound the
  convergence experiment).
- May improve concept selection quality; log which selection policy was used
  so runs remain attributable.

### 7.3 DESIGN.md

No new color tokens required. Reuse `semantic-success`, `ink`, `muted`,
`muted-soft`, mono caption. If a dedicated "warning / learning" semantic is
desired later, add it then; do not invent a third accent now.

PRODUCT.md principle "system state is always visible" is satisfied by placing
mastery on the concept rows the learner already uses to commit to a session.

---

## 8. Phased implementation rollout (after this doc is approved)

| Phase | Work | Verify |
|-------|------|--------|
| **P0** | `apore/runtime/bkt.py`: params, update step, replay helper; unit tests on synthetic sequences | Known sequences reach expected `P(L)` bands |
| **P1** | Log aggregation helper (scan sessions, filter `knowledge_source`, parse rows) reusing `state.py` | Aggregates fixture sessions correctly; ignores other domains |
| **P2** | `GET /learner/mastery` + schema; optionally remap `SessionStateResponse.mastery` | API contract tests; empty chapter → all `New` |
| **P3** | Frontend: fetch mastery in Study preamble; render `.study-concepts__mastery` | Visual check light/dark; a11y; failure soft-degrades |
| **P4** | Point `select_next_concept` / `weak_points` at derived mastery; deprecate in-session +0.15/−0.1 writes (or stop reading them) | Weak-points session prefers low-`P(L)` concepts |
| **P5** (later) | Signal modulation; EM param fit; optional `P(F)` decay; graph overlay (other owner) | Research / Phase 3 |

**Branch:** implementation should land on `feat/pomdp-tune` (or successor).

---

## 9. Open questions

1. **Prior `P(L₀)`:** `0.0` (show New until evidence) vs a small prior
   (e.g. `0.1`) that displays a low % immediately. Current recommendation:
   `0.0` + "New" for zero observations.
2. **Per-type params:** Should recall / apply / synthesis share one
   `(G, S, T)` or have separate params? v1: shared. v1.1: optional by
   `question_type` column already in the log.
3. **Multi-learner local app:** Session files today are single-tenant on disk.
   If the desktop app later supports profiles, scoping must add a
   `learner_id` (or profile directory). Out of scope for the prototype.
4. **Calibration burst rows:** Include Q1–3 burst observations in BKT replay?
   **Yes** — they are real correctness evidence on real concepts.
5. **Legacy `## Mastery` section:** Delete, freeze, or keep writing for
   markdown readers? Recommendation: stop *reading* it in runtime selection;
   stop *writing* once P4 ships; leave historical values in old files alone.

---

## 10. Summary

Apore already records everything BKT needs in per-session question logs.
Promote knowledge tracing from a Phase 3 non-goal into a derive-on-read
per-concept `P(L)`, leave the RL difficulty scalar alone for RQ1, and show a
calm mono percentage next to each concept when the learner starts a session.
That is the smallest change that answers "what am I good at?" without building
the graph dashboard someone else owns.
