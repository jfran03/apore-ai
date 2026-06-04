# Protocol: generate-session-title

You are naming a study session for the learner's history. The runtime will store your
output as the session title.

## Input

You receive chapter context: domain id, chapter id, concept labels from the graph,
focus mode, and planned question count.

## Output

Emit **one line only** — a short title of 4–8 words that generalizes what is being
studied in this session.

- Describe the topic, not the session mechanics (avoid "10 question quiz").
- You may append a brief mode hint after an em dash when focus is weak-point review.
- No quotes, markdown, JSON, or trailing punctuation beyond what fits natural prose.
- Examples: `Set Theory Basics — Adaptive Practice`, `Introduction to Sets — Weak Areas Review`
