# Protocol: extract-signals

You are extracting learner signals from a completed question–answer exchange.
The runtime has appended the full dialogue transcript below this protocol block.

Your sole output is a JSON object. No prose. No markdown fences. No explanation.

---

## What to extract

Read the transcript from start to finish. Extract:

### explicit_rating
The learner's self-declared difficulty rating for this question, **only if stated in the transcript text**.
- Look for phrases like "that was easy," "easy," "ok," "okay," "hard,"
  "that was difficult," or a direct response to "How did you find that question?"
- Map to one of: `"easy"`, `"ok"`, `"hard"`.
- If the learner did **not** state a rating in the transcript (e.g. they used UI
  buttons elsewhere), use `"ok"` as a placeholder. The runtime replaces this with
  the learner's button choice on a later step.

### correct
Whether the learner's final answer is substantively correct.

**Multi-turn Socratic exchange** (Teacher turns present in the transcript):
- `"yes"` if the Teacher explicitly confirmed correctness.
- `"no"` if the Teacher closed without confirming, the learner gave up, or
  the exchange ended with an incorrect answer.
- Ambiguous closures (Teacher redirected without confirming) → `"no"`.

**Single-shot exchange** (only the posed question and one learner answer, no Teacher
hints or confirmations in the transcript):
- Judge the learner's answer against the question and the grounding context.
- `"yes"` if the answer is substantively correct for the concept being tested.
- `"no"` if incorrect, incomplete in a way that fails the question, or empty.

### hint_count
Count every Teacher turn that provided a hint, structural prompt, or leading
question intended to move the learner toward the answer.
- Do NOT count: the original question, confirmations ("Yes, exactly"), or
  simple restatements of the question without new scaffolding.
- Each hint is one count, regardless of length.
- For a single-shot exchange with no Teacher hints, use `0`.

### turn_count
Count every learner turn from the question being posed to (and including)
the learner's final response before the exchange closed.
- A "turn" is one learner message, regardless of length.
- For a single learner answer with no prior learner turns, use `1`.

### hedging_count
Count every distinct hedging phrase in the learner's turns across the full
exchange.
- Hedging phrases include: "I think," "maybe," "I'm not sure," "could be,"
  "possibly," "I guess," "perhaps," "I believe," "not certain," "might be,"
  and close variants.
- Count per occurrence, not per turn: a learner message with two hedging
  phrases counts as two.
- Do not penalise confidence for domain-appropriate qualifiers (e.g., "by
  definition" or "the textbook states").

---

## Inconsistency check (LLM-side hints only)

After extracting all fields, check:

- If `explicit_rating == "easy"` AND (`hint_count >= 4` OR `turn_count >= 10`):
  add `"inconsistency": true` and a `"flag_reason"` string (one sentence
  describing the discrepancy).

The runtime may apply the same rule again after the learner submits their
difficulty rating via the UI.

---

## Output schema

Emit exactly this JSON, with no surrounding text:

```
{"explicit_rating": "easy|ok|hard", "correct": "yes|no", "hint_count": N, "turn_count": N, "hedging_count": N}
```

With inconsistency flag (only when triggered):

```
{"explicit_rating": "easy", "correct": "yes", "hint_count": 5, "turn_count": 12, "hedging_count": 1, "inconsistency": true, "flag_reason": "Learner rated easy but required 5 hints and 12 turns."}
```

---

## Hard rules

- Emit ONLY valid JSON. The runtime parses this with `json.loads()`. Any
  deviation — a leading sentence, a trailing note, a markdown fence — will
  cause a parse error and log an extraction failure.
- Do not compute reward R. Do not compute new difficulty. Do not reference
  `alpha` or weight values. Those are runtime-only.
- If the transcript is empty or malformed, emit:
  `{"explicit_rating": "ok", "correct": "no", "hint_count": 0, "turn_count": 0, "hedging_count": 0}`

---

## Note for context assembly

**Column mapping:** The runtime maps the JSON field names to question log
columns as follows: `hint_count` → `hints`, `turn_count` → `turns`,
`hedging_count` → `hedging`. Emit the JSON field names exactly as specified
above; the runtime handles the rename on write.

**Descoped signals:** `response_length` and `learner_question_asking`
(FR-4.1) are deferred to Phase 3. Do not attempt to extract or emit them.
