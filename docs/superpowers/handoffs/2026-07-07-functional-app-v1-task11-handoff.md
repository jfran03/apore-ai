# Functional App v1 SDD Handoff After Task 11

Date: 2026-07-07
Branch: `feat/product-v1`
Current HEAD: `7f9afc4`
Plan: `docs/superpowers/plans/2026-07-06-functional-app-v1.md`
Ledger: `.superpowers/sdd/progress.md`
Process: `superpowers:subagent-driven-development`

## Current State

Tasks 1-11 are complete and reviewed. Backend Tasks 1-8 are complete. Frontend Tasks 9-11 are complete. Next task is Task 12: Chat state machine (pure) + Vitest.

Trust `.superpowers/sdd/progress.md` and `git log --oneline` over summaries if anything disagrees.

## Completed Tasks And Commits

- Task 1: `650c3e3..9129aa0` — domain workspace store, reviewed clean after human-approved path traversal hardening.
- Task 2: `9129aa0..d40ab92` — workspace knowledge resolution and seeding, reviewed clean after human-approved `store.chapters_dir()` path fix.
- Task 3: `c113c27` — per-session transcript/resume persistence, reviewed with human-approved `updated_at` sort decision.
- Task 4: `788f5a0` — behavior-preserving `session_flow.py` extraction, reviewed clean.
- Task 5: `9872af4` — `/domains` API with scan-based listing and testbed flag, reviewed clean.
- Task 6: `cbfd880` — domain-scoped session create/list/detail, reviewed clean.
- Task 7: `493eff4` — domain-scoped tutoring loop with transcripts and restart resume, reviewed clean.
- Task 8: `493eff4..b7041f2` — gated seed endpoint, reviewed clean after two fix rounds for method-based route disclosure.
- Task 9: `4fdc37e` — frontend API types and client functions, reviewed clean. Controller verified backend schema compatibility and `npm run build`.
- Task 10: `4fdc37e..4fb88c2` — navigation/shell/sidebar/hooks restructure, reviewed clean after one fix round for stale sidebar/session state. Controller verified `npm run build` and dev smoke for empty workspace-domain sidebar + New domain navigation.
- Task 11: `7f9afc4` — working `CreateDomainView` and deleted `BackendOverview`, reviewed clean. Controller verified `npm run build` and browser create-domain flow.

## Verification And Review Status

- Task 9: reviewer approved. Independent `npm run build` passed.
- Task 10: first reviewer found stale session/domain error state issues; fix commit `4fb88c2` closed them; re-review approved. Independent `npm run build` passed. Browser smoke verified app loaded, empty domain sidebar state appeared, and New domain navigated to create view.
- Task 11: reviewer approved with only controller verification caveat. Independent `npm run build` passed. Browser smoke against `http://127.0.0.1:5173` created `Task 11 UI Smoke Cursor` and navigated into `task-11-ui-smoke-cursor-8fdb`.

## Remaining Tasks

- Task 12: Chat state machine (pure) + Vitest.
  - Files: `product/frontend/package.json`, `product/frontend/src/chat/machine.ts`, `product/frontend/src/chat/machine.test.ts`.
  - Gate: `npx vitest run` plus `npm run build`.
- Task 13: `useTutorSession` + live `ChatView`.
- Task 14: Settings modal (BYOK).
- Task 15: Honest stubs.
- Task 16: E2E verification + README. Requires real manual/browser verification; do not leave this entirely to a subagent.

## Binding Decisions

- `store.load_domain()` rejects path traversal domain IDs. Human-approved.
- Workspace chapter resolution uses `store.chapters_dir()`. Human-approved.
- `sessionfile.list_sessions()` sorts newest-first by `updated_at`, not `created_at`. Human-approved.
- Gated seed endpoint route masking is generic in `app.py`, not per-verb enumeration.
- Plan conflict decision: testbed-only seed UI is allowed when `APORE_TESTBED=1`; outside testbed, no seed affordance.

## Open Concerns For Final Review

- Task 3: missing-session `load_session_file` and empty-domain `list_sessions` remain untested edge cases; code looked correct by inspection.
- Task 6: `POST /domains/{id}/sessions` tests still make one real fast-failing Anthropic network call per test due direct provider imports; not verified under network-isolated CI.
- Task 7: `active_concept_id` can be dropped if restart lands exactly on an idle boundary; this only weakens anti-repeat for one question. `sessionfile` writes are non-atomic. Reflection-phase restart path is untested.
- Task 11: smoke domains `task11-smoke-domain-44cb` and `task-11-ui-smoke-cursor-8fdb` were created in the existing backend data root. Treat them as test artifacts.
- Pre-existing dirty/untracked files remain in the working tree, including `product/frontend/src-tauri/Cargo.toml`, backend test domains, and many backend session markdown files. They predated this handoff work; do not revert or stage them unless explicitly instructed.

## Exact Next Action

Resume with Task 12. First extract the Task 12 brief to `.superpowers/sdd/task-12-brief.md`, then dispatch a fresh implementer subagent per `superpowers:subagent-driven-development`.

On Windows/PowerShell, this extraction command works from the repo root:

```powershell
$plan = 'docs/superpowers/plans/2026-07-06-functional-app-v1.md'; $outDir = '.superpowers/sdd'; $out = Join-Path $outDir 'task-12-brief.md'; Set-Content -Path (Join-Path $outDir '.gitignore') -Value '*' -Encoding utf8; $n = '12'; $infence = $false; $intask = $false; $lines = Get-Content -Path $plan; $result = New-Object System.Collections.Generic.List[string]; foreach ($line in $lines) { if ($line -match '^```') { $infence = -not $infence }; if (-not $infence -and $line -match '^#+\s+Task\s+([0-9]+)([^0-9]|$)') { $intask = ($Matches[1] -eq $n) }; if ($intask) { $result.Add($line) } }; if ($result.Count -eq 0) { Write-Error "task $n not found in $plan"; exit 3 }; Set-Content -Path $out -Value $result -Encoding utf8; Write-Output ('wrote {0}: {1} lines' -f $out, $result.Count)
```

Then dispatch Task 12 implementer with:

- Brief: `.superpowers/sdd/task-12-brief.md`
- Report: `.superpowers/sdd/task-12-report.md`
- Base commit: `7f9afc4`
- Expected commit message from plan: `feat(frontend): chat state machine reducer with vitest coverage`

## Ready-To-Paste Resume Prompt

```text
Continue Functional App v1 using superpowers:subagent-driven-development.

Read first:
- docs/superpowers/handoffs/2026-07-07-functional-app-v1-task11-handoff.md
- .superpowers/sdd/progress.md
- docs/superpowers/plans/2026-07-06-functional-app-v1.md

Current branch should be feat/product-v1 at HEAD 7f9afc4. Tasks 1-11 are complete and reviewed. Do not re-dispatch completed tasks. Respect binding decisions, especially: testbed-only seed UI is allowed when APORE_TESTBED=1, but there is no seed affordance outside testbed.

Resume at Task 12. Extract a Task 12 brief into .superpowers/sdd/task-12-brief.md, dispatch a fresh implementer subagent, run task-scoped review with a review package from base 7f9afc4 to the Task 12 head, fix any Critical/Important findings, then append the Task 12 ledger line. Continue SDD task-by-task afterward unless blocked.

Preserve unrelated dirty/untracked files. Do not revert or stage pre-existing generated backend domains/sessions or product/frontend/src-tauri/Cargo.toml.
```
