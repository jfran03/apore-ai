# Apore RL Numeric Config

Runtime-owned RL parameters. The runtime reads this file at session start.
The LLM does not need to read or reason about this file — it is for the
runtime's bookkeeping only.

---

## Reward weights

Used in: `R = 0.4·explicit_rating + 0.3·correct + 0.2·hint_score + 0.1·implicit_score`

```
explicit_rating : 0.4
correct         : 0.3
hint            : 0.2
implicit        : 0.1
```

Reward R is clamped to `[-1.0, 1.0]` after summation.

---

## Learning rate

```
alpha : 0.1
```

Used in: `new_difficulty = clamp(current_difficulty + alpha * R, low, high)`

---

## Difficulty bounds

```
low  : 0.1
high : 0.9
```

The per-learner scalar never falls below `low` or rises above `high`.

---

## Initial scalar

```
initial : 0.5
```

Overwritten by the calibration burst result before the adaptive loop begins.

---

## Signal scoring table

These are the raw signal values the LLM extracts. The runtime maps them to
floats using the table below before computing R.

### explicit_rating

| Rating | Score  |
|--------|--------|
| easy   | +1.0   |
| ok     |  0.0   |
| hard   | -1.0   |

### correct

| Value | Score  |
|-------|--------|
| yes   | +0.5   |
| no    | -0.5   |

### hint_score

| Hint count | Score  |
|------------|--------|
| 0          | +0.2   |
| 1–2        |  0.0   |
| 3+         | -0.2   |

### hedging_score (part of implicit)

| Hedging count | Score  |
|---------------|--------|
| 0             | +0.1   |
| 1–2           |  0.0   |
| 3+            | -0.1   |

### turn_score (part of implicit)

| Turn count | Score  |
|------------|--------|
| ≤ 3        | +0.1   |
| 4–6        |  0.0   |
| 7+         | -0.1   |

`implicit_score = hedging_score + turn_score`

---

## Inconsistency thresholds

Flag an explicit/implicit inconsistency when:
- `explicit_rating == "easy"` AND (`hint_count >= 4` OR `turn_count >= 10`)

Inconsistency flags are logged in `learner-state.md` alongside the row but do
not alter the reward calculation.
