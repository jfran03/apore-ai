# Protocol: generate-question-bank

You are authoring questions for a chapter question bank. The runtime will select
from this bank later — do not tailor wording to a single session.

Context blocks below include grounding per concept. For each concept you are
assigned, write **exactly two** questions per type: recall, apply, synthesis.

---

## Difficulty bands (intended_difficulty on each question)

| type      | intended_difficulty range |
|-----------|---------------------------|
| recall    | 0.10 – 0.35               |
| apply     | 0.36 – 0.65               |
| synthesis | 0.66 – 0.90               |

Use two distinct values within each band when writing two questions of the same type.

---

## Question rules

- Answerable only from the grounding slice for that concept (and listed neighbors).
- Open questions only — not multiple-choice or true/false.
- 1–3 sentences per question; no hints embedded in the question text.
- Do not emit `depth` — concept depth is defined only in the concept graph.

---

## Output format

Reply with **ONLY** valid JSON (no markdown fences, no prose):

```json
{
  "questions": [
    {
      "id": "<concept_id>-<type>-01",
      "concept_id": "<node_id>",
      "type": "recall | apply | synthesis",
      "intended_difficulty": 0.25,
      "text": "<question text>"
    }
  ]
}
```

- `id` must be unique across the entire response.
- Use suffix `-01`, `-02` for the two questions per type per concept.
- Include all six questions per concept (2 × 3 types) in one array for that concept call.
