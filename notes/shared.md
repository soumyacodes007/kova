# Shared board

Everyone reads this file at the start of every session and updates it when a gate, contract, handoff or blocker changes. Newest entries go at the top of each table.

## Gate status

| Phase | Owner | Status | Done-when check passed? (date, by) |
| --- | --- | --- | --- |
| 1 Setup and environments | B | not started | |
| 2 Challenges and drawings | A | not started | |
| 3 Evaluator and sandbox | A | not started | |
| 4 Miner and signed jobs | C | not started | |
| 5 Validator rounds and storage | B | not started | |
| 6 Chain integration | B | not started | |
| 7 Families, audits, robustness | A | not started | |
| 8 API, CLI and terminal demo | C | not started | |
| **Backend gate** (`make demo` end to end) | all | **closed** | |
| 9 Arena on the real API | C | blocked by gate | |
| 10 Trust pages | C (+A, B) | blocked by gate | |
| 11 Ship | all | blocked by gate | |

Status values: `not started` · `in progress` · `blocked` · `done`

## Contracts (`src/cadrecover/protocol/`)

| Contract | Owner | Version | Consumers | Notes |
| --- | --- | --- | --- | --- |
| Public challenge record | A | — | C (miner), B (validator) | PRD §Mechanism "Each challenge has two records" |
| Private challenge record | A | — | B (validator), A (evaluator) | never served to miners |
| Job request and result envelope | C | — | B (validator) | signed with `bt.http_auth`; 202 + polling |
| Evaluation record (per set and total) | A | — | B (aggregation), C (API) | per-set V, C, G, D; Q |
| Weight batch and receipt | B | — | C (API, pages) | commit, reveal and incentive as separate states |

Change log (newest first): `date · contract · old → new version · what changed · who must update`

## Handoffs

| Date | From → to | What | Where / how to use |
| --- | --- | --- | --- |

## Requests (change in a file you don't own)

| Date | From → owner | File | Request | Status |
| --- | --- | --- | --- | --- |

## Blockers

| Date | Agent | Blocked on | Waiting for | Resolved? |
| --- | --- | --- | --- | --- |

## Decisions

| Date | Decision | Why | Affects |
| --- | --- | --- | --- |
| 2026-10-29 | Scoring v2.1: score every parameter set (s₀ + 3 hidden edits, equal weight); a missing or misplaced critical feature zeroes the set; hidden edits must be discriminative (feature shift > 5× tolerance, reference self-IoU < 0.85); floor starts at 50 | The old formula paid a constant model ~70 | A (evaluator), B (aggregation floor), C (API and pages show per-set results) |

## Open questions (from REVIEW.md)

- Rewrite positioning against Backflip's "2D Drawing to CAD" (REVIEW #2). Owner: whoever writes the README and pitch in Phase 11.
- Held-out or feature-composed family to stop template solvers (REVIEW #3). Owner: A, Phase 7.
- Audit pass rule for non-deterministic LLM engines, e.g. within 10 points on 3 hidden tasks (REVIEW #5). Owner: A, Phase 7.
- draftwright is AGPL; keep it out of anything shipped to customers (REVIEW #6). Owner: A.
