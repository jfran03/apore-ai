# Provider Swap Test — PRD Success Criterion 5

**Date:** 2026-06-01
**Status:** Verified at code level (stub providers)

## What was tested

Two simulated sessions run with identical seed, fixture, and concept sequence.
Session A used `provider="anthropic"`, Session B used `provider="nim"`.

Both sessions ran through `apore.runtime.core.run_question_cycle` — the same
code path used by both live providers. Each session answered 3 questions using
`StubProvider` (deterministic, no network) with the `set_theory_intro` concept.

## Results

| Metric | Anthropic (stub) | NIM (stub) | Match? |
|--------|-----------------|------------|--------|
| Log rows produced | 3 | 3 | yes |
| Reward Q1 | 0.17 | 0.17 | yes |
| Reward Q2 | 0.17 | 0.17 | yes |
| Reward Q3 | 0.17 | 0.17 | yes |
| Difficulty after Q1 | 0.517 | 0.517 | yes |
| Difficulty after Q2 | 0.534 | 0.534 | yes |
| Final difficulty scalar | 0.551 | 0.551 | yes |
| Provider field in metadata | anthropic | nim | (intentional) |

## Test coverage

Six assertions in `tests/runtime/test_provider_swap.py`:

1. `test_same_number_of_log_rows` — both sessions write 3 rows
2. `test_same_reward_values` — reward per question is identical
3. `test_same_final_difficulty_scalar` — final scalar is identical
4. `test_log_rows_have_required_columns` — all 13 required columns present in both state files
5. `test_only_metadata_provider_differs` — every field matches except `metadata["provider"]`
6. `test_scalar_path_identical` — difficulty scalar after each question matches

All 6 tests pass (`pytest tests/runtime/test_provider_swap.py -v`).

## How to run with live providers

1. Set `ANTHROPIC_API_KEY` environment variable
2. Set `NVIDIA_API_KEY` environment variable
3. Update `program/apore/fixtures/manifest.json` to pin the apore-lite fixture
4. Run `python scripts/fetch_fixture.py` to fetch the fixture
5. Run a session: `POST /sessions` with `{"provider": "anthropic", "model": "claude-haiku-4-5-20251001", "fixture": "apore-lite"}`
6. Repeat with `{"provider": "nim", "model": "meta/llama-3.1-8b-instruct"}`
7. Compare the `learner-state.md` files — reward math and scalar updates are runtime-owned and identical

## Architecture guarantee

The provider swap works without code change because:

- `apore.runtime.core.run_question_cycle` calls `provider.invoke(system, messages, model, config)` — same interface for both adapters
- Reward computation (`compute_reward`) and difficulty update (`update_difficulty`) run in the runtime, never in the LLM
- Signal extraction parses JSON from the LLM response — the JSON schema is identical regardless of provider
- `learner-state.md` column structure is fixed; only the `metadata.provider` field differs
