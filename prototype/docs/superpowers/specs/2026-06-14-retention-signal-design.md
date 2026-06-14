# Retention Signal — Design Spec

**Date:** 2026-06-14
**Status:** Approved (brainstorm) → ready for implementation plan
**Scope:** `program/apore/runtime/{reward.py, state.py, core.py}` + tests

---

## 1. Problem

Every question is currently graded in isolation. The `Question Log` table records
history (`Q#`, `session`, `date`, `concept`, `correct`, …) but **nothing reads it
back**. There is no notion of *time*, *spacing*, or *retention*: answering a concept
wrong and then right five questions later produces the exact same mastery math as two
unrelated answers. The signal is memoryless.

This spec adds a **temporal (timeline) signal**, concept-level, that:

1. **Retention modeling (mastery):** mastery reflects spacing & forgetting — a correct
   retrieval after a gap is worth more than an immediate repeat, and mastery decays over
   real elapsed time without practice.
2. **Reward shaping (R):** the reward reacts to the learner's trajectory (recovering from
   a wrong answer, regressing after a gap), not just the latest event.

Out of scope (explicitly deferred): scheduling / what-to-ask-next, and analytics-only
visualization.

## 2. Decisions (from brainstorm)

| Decision | Choice |
|---|---|
| Granularity | **Concept-level** (mastery is already concept-keyed; any question on the concept proves retention) |
| Time axis | **Both**: ordinal spacing within a session + wall-clock days across sessions, weighted |
| Approach | **A** — spacing-aware mastery + a retention term in R (layered extension of existing functions; no state-schema migration) |
| Timeline source | The existing `Question Log` table (no new persisted state) |
| Determinism | Wall-clock (`now`) is **injected** as a parameter so `reward.py` stays pure and tests stay deterministic |

## 3. Architecture & data flow

The timeline source is the existing log. The first new piece is a reader; everything
else is a pure function.

```
finalize_turn (core.py)
  ├─ state.read_log_rows(path)                 # NEW: parse Question Log → ordered rows
  ├─ reward.build_retention_context(rows, concept_id, now)   # NEW: derive the gap
  ├─ reward.compute_reward(signals, retention=ctx)           # EXTENDED: + retention term
  └─ reward.mastery_step(current, correct, ctx)             # EXTENDED: decay + spacing gain
```

| Unit | Location | Responsibility | Purity |
|---|---|---|---|
| `read_log_rows(path)` | `state.py` | Parse the markdown log table → ordered `list[dict]` | I/O |
| `RetentionContext` | `reward.py` | `{ordinal_gap, days_gap, prior_correct, is_first_attempt}` | data |
| `build_retention_context(rows, concept_id, now)` | `reward.py` | Raw history → `RetentionContext` | pure |
| `retention_score(ctx)` | `reward.py` | Temporal term fed into R | pure |
| `compute_reward(signals, retention=None)` | `reward.py` | Add term; `None` ⇒ identical to today | pure |
| `decay_mastery(current, days_gap)` | `reward.py` | Forgetting decay | pure |
| `mastery_step(current, correct, ctx)` | `reward.py` | Decay + spacing-aware gain/penalty (extracted from inline `core.py` logic) | pure |

`core.finalize_turn` gains a `now` parameter (default `today`) so wall-clock is injectable.

## 4. Timeline derivation — `build_retention_context(rows, concept_id, now)`

Pure function over the log rows (in ask-order) for the current concept:

- **`ordinal_gap`** = number of logged questions since this concept last appeared
  (`5` in the headline example). `None` on first-ever attempt.
- **`days_gap`** = `now` − date of last attempt on this concept (day granularity, since
  the log stores dates). `0` within a sitting.
- **`prior_correct`** = was the most recent prior attempt on this concept correct?
- **`is_first_attempt`** = no prior rows for this concept ⇒ retention contributes 0.

Fully deterministic given `rows` + `now`.

## 5. Formulas

### Tunable constants
| Const | Value | Meaning |
|---|---|---|
| `ORD_REF` | 5 | ordinal gap that counts as "full" spacing |
| `DAYS_REF` | 7 | wall-clock gap that counts as "full" spacing |
| `HALF_LIFE_DAYS` | 14 | mastery halves after this long with no practice |
| `W_RET` | 0.15 | weight of the retention term in R |
| `BASE_GAIN` / `BASE_PENALTY` | 0.15 / 0.10 | today's mastery step (preserved at zero spacing) |
| `GAIN_SPACING` | 1.0 | correct-after-gap gain scales up to 2× |
| `FORGIVE` | 0.5 | wrong-after-gap penalty shrinks up to ½ |

### Spacing strength (shared driver)
```
s = clamp(ordinal_gap / ORD_REF  +  days_gap / DAYS_REF,  0, 1)
```
Within a sitting `days_gap=0`, so ordinal drives it. Across days, the clock drives it.

### Retention term — `retention_score(ctx) ∈ [−1, 1]`
```
first attempt              →  0
correct & prior wrong      →  +s        (recovery — the headline)
correct & prior correct    →  +0.5·s    (reinforcement)
wrong   & prior correct    →  −s        (regression/forgetting)
wrong   & prior wrong      →  −0.5·s    (still struggling)
```
By construction: sign-correct, monotonic in `s`, zero on first attempt, bounded.

### Reward (extended, backward-compatible)
```
R = 0.4·rating + 0.3·correct + 0.2·hint + 0.1·implicit + W_RET·retention_score
    → clamp(−1, 1)
```
`retention=None` or first attempt ⇒ last term is 0 ⇒ **bit-identical to today**.

### Forgetting decay — `decay_mastery(current, days_gap)`
```
decayed = current · exp(−ln(2)/HALF_LIFE_DAYS · days_gap)
```
Keyed on **days only** (5 questions in one sitting isn't forgetting). `days_gap=0 ⇒ ×1`.
Monotonic ↓ in days, bounded `[0, current]`.

### Spacing-aware mastery — `mastery_step(current, correct, ctx)`
```
m = decay_mastery(current, days_gap)          # forget first
correct →  gain    = BASE_GAIN    · (1 + GAIN_SPACING·s);  new = clamp(m + gain, 0, 1)
wrong   →  penalty = BASE_PENALTY · (1 − FORGIVE·s);       new = clamp(m − penalty, 0, 1)
```
At `s=0, days_gap=0` (every cold-start) this equals today's ±0.15/−0.10 exactly.

### Worked example — headline, single session
`wrong → [5 questions] → right` (`days_gap=0`, `ordinal_gap=5`, `s=1.0`, `prior_correct=no`):
- `retention_score = +1.0` → adds `0.15` to R (clean correct: R `0.19 → 0.34`).
- mastery: prior wrong floored at `0`; no decay; `gain = 0.15·(1+1) = 0.30` → mastery `0.30`.

Versus immediate `right → right` (`ordinal_gap=1`, `s=0.2`, reinforcement): R term `+0.015`,
`gain=0.18`. Recovery is rewarded far more in both R and mastery.

## 6. Verification strategy

Tests are written **first** (TDD); they are the definition of done. Four layers, strongest
isolation first. Benchmarking/sim is last and is *confirmation*, not proof.

### Layer 1 — Exact-value unit tests (isolation)
Every new function is pure → `f(known input) == hand-computed output`. No mocks/clock/I-O.
- `build_retention_context`: hand-built `rows` + fixed `now` → assert all four fields
  exactly (catches off-by-one in gap, date-direction bugs).
- `retention_score`: exact float for each of the 5 cases.
- `decay_mastery` / `mastery_step`: exact post-values for representative gaps.

### Layer 2 — Property / invariant tests (hold for all inputs)
Sweep inputs (or hypothesis-style ranges):
- **Bounds:** `compute_reward ∈ [−1,1]`, `mastery ∈ [0,1]` for any gap/history.
- **Monotonicity:** correct recovery ⇒ `retention_score` non-decreasing in `s`;
  wrong-after-correct ⇒ penalty magnitude non-increasing in `s`.
- **Sign correctness:** recovery > 0; regression < 0.
- **First-attempt neutrality:** `is_first_attempt ⇒ retention_score == 0`.

### Layer 3 — Backward-compatibility equivalence (regression proof)
- `compute_reward(signals, retention=None)` is bit-identical to today across the existing
  test matrix (existing `test_reward.py` values left untouched).
- A cold-start session (every question a first attempt) produces the same scalar
  trajectory and mastery as `main`.

### Layer 4 — Golden scenario tests (encode the pedagogical claim)
Relational assertions (survive tuning):
- **Spacing effect:** same pre-mastery + correct ⇒ `mastery_step(gap=5) > mastery_step(gap=1)`.
- **Recovery reward:** `retention_score(recovery, s) = s > 0.5s = retention_score(reinforce, s)`.
- **Forgetting:** decay reduces mastery across days; `days_gap=0` ⇒ no decay.
- **One integration test** through `finalize_turn` with the existing stub provider + a
  crafted log: run a recovery scenario end-to-end, assert the appended log row, the new
  scalar, and the new mastery.

### Confirmation (not proof)
Extend the simulated student with a retention profile and check the system tracks it via
the existing convergence harness. Classed as benchmarking.

## 7. Risks & constraints

- **Determinism:** wall-clock enters only via the injected `now`; all reward/mastery math
  is pure. Tests pass fixed `now`/gaps.
- **Sim/convergence drift:** if the sim revisits concepts, retention activates and may
  change convergence numbers. Verify and, if needed, update expected values — do not
  weaken the model to match a stale baseline.
- **Log as source of truth:** `read_log_rows` must tolerate the existing table format
  exactly; malformed/empty log ⇒ treat as first attempt (retention 0).
- **Date granularity:** the log stores dates (not timestamps), so `days_gap` is day-level.
  Acceptable for the forgetting model; finer granularity is a future change.

## 8. Future direction (not now)

Approach B (per-concept memory model: stored half-life + retrievability `exp(−Δt/halflife)`,
reward from prediction error) is the natural evolution once A is validated. It is a
state-schema migration and is deliberately deferred.
