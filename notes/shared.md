# Shared board

Everyone reads this file at the start of every session and updates it when a gate, contract, handoff or blocker changes. Newest entries go at the top of each table.

## Gate status

| Phase | Owner | Status | Done-when check passed? (date, by) |
| --- | --- | --- | --- |
| 0 Protocol drafts (day 1) | A, B, C | done | 2026-10-29: 10 contract tests passed |
| 1 Setup and environments | B | done | 2026-10-29: `check-envs.sh` all 3 OK; heartbeat 23 → 33 producing |
| 2 Challenges and drawings | A | done | 2026-10-29: `cadrecover challenge new` → readable drawing, coverage ok, lint 1.0 |
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
| Public challenge record | A | 0.1.0 | C (miner), B (validator) | `protocol/challenge.py` `PublicChallenge`: names + ranges, never values |
| Private challenge record | A | 0.1.0 | B (validator), A (evaluator) | `PrivateChallenge`; `sets[0]` = drawing, hidden edits appended in phase 3 |
| Job request and result envelope | C | 0.1.0 | B (validator) | `protocol/jobs.py`; signing via `bt.http_auth` headers |
| Evaluation record (per set and total) | A | 0.1.0 | B (aggregation), C (API) | `protocol/evaluation.py`; the formula is `task_quality()`, `QUALITY_FLOOR = 50` |
| Weight batch and receipt | B | 0.1.0 | C (API, pages) | `protocol/weights.py` |

Change log (newest first): `date · contract · old → new version · what changed · who must update`
- 2026-10-29 · all contracts · — → 0.1.0 · created · —

## Handoffs

| Date | From → to | What | Where / how to use |
| --- | --- | --- | --- |
| 2026-10-29 | A → C | Practice challenge (retired, known seed) | `fixtures/public/sample_plate/` (challenge.json + drawing.png). Build your miner against it; never score it. |
| 2026-10-29 | A → B | Challenge creation for the scheduler | `cadrecover.challenges.pipeline.new_challenge(family="plate")` returns public facts; private record at `runtime/private/<id>/private.json` |
| 2026-10-29 | B → all | Envs, DB, paths | `make envs`, `make test`; `cadrecover.paths` (everything under `~/.cadrecover`); `cadrecover.storage.db.connect()` |

## Requests (change in a file you don't own)

| Date | From → owner | File | Request | Status |
| --- | --- | --- | --- | --- |
| 2026-10-29 | A, B → C | `src/cadrecover/cli.py` | Created the file with `setup wallets`, `chain heartbeat` (B) and `challenge new/show` (A) before Phase 8. C owns it from here; restyle freely, but keep the commands working. | done; logged |

## Blockers

| Date | Agent | Blocked on | Waiting for | Resolved? |
| --- | --- | --- | --- | --- |

## Decisions

| Date | Decision | Why | Affects |
| --- | --- | --- | --- |
| 2026-10-29 | Retire any challenge whose seed or values were exposed (`ch_51b40eea12677918`, `ch_df01e47027a76f04`) | Ground truth of an exposed challenge is reproducible | B (scheduler must only use `status = 'active'`) |
| 2026-10-29 | Publish only the drawing PNG; draftwright's SVG stays private | SVG geometry is machine-readable and would bypass reading the drawing | A, C |
| 2026-10-29 | Drawing coverage = draftwright's ledger all `placed` + every required value in a rendered label; otherwise resample with the next seed | Text in the SVG is converted to outlines, so it can't be searched | A |
| 2026-10-29 | Envs and runtime state in `~/.cadrecover` (WSL filesystem); drawing env on Python 3.13 / build123d 0.11; CAD env build123d 0.13 | SQLite WAL is unsafe on `/mnt/c`; draftwright's pins | all |
| 2026-10-29 | Scoring v2.1: score every parameter set (s₀ + 3 hidden edits, equal weight); a missing or misplaced critical feature zeroes the set; hidden edits must be discriminative (feature shift > 5× tolerance, reference self-IoU < 0.85); floor starts at 50 | The old formula paid a constant model ~70 | A (evaluator), B (aggregation floor), C (API and pages show per-set results) |

## Open questions (from REVIEW.md)

- Rewrite positioning against Backflip's "2D Drawing to CAD" (REVIEW #2). Owner: whoever writes the README and pitch in Phase 11.
- Held-out or feature-composed family to stop template solvers (REVIEW #3). Owner: A, Phase 7.
- Audit pass rule for non-deterministic LLM engines, e.g. within 10 points on 3 hidden tasks (REVIEW #5). Owner: A, Phase 7.
- draftwright is AGPL; keep it out of anything shipped to customers (REVIEW #6). Owner: A.
