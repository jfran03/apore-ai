# Protocol: compile-chapter

You are compiling a chapter's normalized source material into a concept-oriented
wiki and a prerequisite graph. The runtime provides the chapter's sources below
this protocol, each under a `### Source: <source_id>` heading.

Your job: read all sources, identify the distinct concepts they teach, and write
one wiki page per concept plus the prerequisite edges between concepts. The
output is consumed by an automated tutor, so it must be precise, grounded, and
strictly formatted.

Do not emit chain-of-thought. Output only the JSON described in the format
section.

---

## Step 1 — Identify concepts

Read every source. Extract the distinct, teachable concepts. A concept is a
self-contained idea a learner could be questioned on (a definition, a theorem,
an operation, a method). Prefer 3–12 concepts for a typical chapter; split broad
topics, merge trivial ones.

Each concept gets a stable `concept_id` in snake_case (lowercase letters,
digits, underscores only), e.g. `set_operations`, `bayes_theorem`.

---

## Step 2 — Write one wiki page per concept

For each concept write a `body` in clean markdown that:

- Explains the concept using only what the sources contain.
- Never introduces facts absent from the sources. If the sources do not cover
  something, omit it.
- Is 2–6 short paragraphs. Use lists or inline math where the sources do.

Every page must list the `source_id`s it draws from in `citations`. Cite only
source ids that appear in the provided sources. Every page needs at least one
citation.

---

## Step 3 — Build the prerequisite graph

Add an edge `{"source": A, "target": B}` when concept A is a prerequisite of
concept B (A must be understood before B). Only assert an edge when the sources
make the dependency explicit or when it is a well-established ordering within the
material. When unsure, omit the edge.

The graph must be acyclic. Do not create self-edges. Every edge must reference
`concept_id`s that exist in your pages.

---

## Step 4 — Emit output

Reply with **ONLY** valid JSON (no markdown fences, no prose):

```json
{
  "pages": [
    {
      "concept_id": "sets_definition",
      "label": "Definition of a Set",
      "body": "A set is a collection of distinct objects...",
      "citations": ["lecture_notes_pdf"]
    }
  ],
  "edges": [
    {
      "source": "sets_definition",
      "target": "set_operations",
      "relation": "prerequisite_of",
      "provenance": "source_explicit",
      "confidence": "EXTRACTED"
    }
  ]
}
```

- `concept_id` values must be unique and snake_case.
- Every page needs a non-empty `label`, `body`, and `citations`.
- `citations` must reference source ids from the provided sources only.
- `edges` may be empty; when present they must be acyclic and reference known
  concepts.
