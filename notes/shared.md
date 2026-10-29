# Shared board

Everyone reads this file at the start of every session and updates it when a gate, contract, handoff or blocker changes. Newest entries go at the top of each table.

## Gate status

| Phase | Owner | Status | Done-when check passed? (date, by) |
| --- | --- | --- | --- |
| 0 Protocol drafts (day 1) | A, B, C | done | 2026-10-29: 10 contract tests passed |
| 1 Setup and environments | B | done | 2026-10-29: `check-envs.sh` all 3 OK; heartbeat 23 → 33 producing |
| 2 Challenges and drawings | A | done | 2026-10-29: `cadrecover challenge new` → readable drawing, coverage ok, lint 1.0 |
| 3 Evaluator and sandbox | A | done | 2026-10-29: `cadrecover score` → honest 100 / constant 25 / proportional 25 / wrong holes 0 / crash 0 |
| 4 Miner and signed jobs | C | done (mock strategies) | 2026-10-29: live signed job → mock-oracle Q 100; real VLM strategies wait for an API key |
| 5 Validator rounds and storage | B | done (static discovery) | 2026-10-29: 5-miner round in 3 m 12 s; leaderboard and proposed weights in SQLite |
| 6 Chain integration | B | done (localnet) | 2026-10-29: weights `{2: 1.0}` set + read back at block 15596; commit 1584 → reveal 1595 on a fresh chain; testnet waits for test TAO |
| 7 Families, audits, robustness | A | done (flange; chuck/chamber stretch) | 2026-10-29: diagnostics earn 0 (25/0/0); honest audit PASS 100/100; swapped engine FAIL 25 vs 100 → weight revoked (block 29321) |
| 8 API, CLI and terminal demo | C | done | 2026-10-29: `DEMO_HEADLESS=1 make demo` from a clean state → EXIT=0 |
| **Backend gate** (`make demo` end to end) | all | **open** | 2026-10-29: round run_6b6a61efe4 done, weights committed 1584 → revealed 1595, audit uid 3 PASS (90.3 vs 100) |
| 9 Arena on the real API | C | not started | |
| 10 Trust pages | C (+A, B) | not started | |
| 11 Ship | all | not started | |

Status values: `not started` · `in progress` · `blocked` · `done`

## Contracts (`src/cadrecover/protocol/`)

| Contract | Owner | Version | Consumers | Notes |
| --- | --- | --- | --- | --- |
| Public challenge record | A | 0.1.0 | C (miner), B (validator) | `protocol/challenge.py` `PublicChallenge`: names + ranges, never values |
| Private challenge record | A | 0.1.0 | B (validator), A (evaluator) | `PrivateChallenge`; `sets[0]` = drawing, hidden edits appended in phase 3 |
| Job request and result envelope | C | 0.1.0 | B (validator) | `protocol/jobs.py`; signing via `bt.http_auth` headers |
| Evaluation record (per set and total) | A | 0.1.0 | B (aggregation), C (API) | `protocol/evaluation.py`; the formula is `task_quality()`, `QUALITY_FLOOR = 50` |
| Weight batch and receipt | B | 0.1.0 | C (API, pages) | `protocol/weights.py` |

| Read API (OpenAPI) | C | 0.1 | C (web) | `docs/api/openapi.json` → `apps/web/lib/api-types.ts`; regenerate with `scripts/export-openapi.py` |

Change log (newest first): `date · contract · old → new version · what changed · who must update`
- 2026-10-29 · read API · — → 0.1 · created · C (frontend builds on it)
- 2026-10-29 · challenge records + miner contract · 0.1.0 → **0.2.0** · `build_part(overrides)` gets `{}` at s₀ and only changed keys at edits; `ParameterSet.overrides` added · C (miners must embed what they read as defaults; done in `miner/templates.py`), B (nothing)
- 2026-10-29 · all contracts · — → 0.1.0 · created · —

## Handoffs

| Date | From → to | What | Where / how to use |
| --- | --- | --- | --- |
| 2026-10-29 | B, A, C → all | Backend gate open | `make demo` (tmux) / `DEMO_HEADLESS=1 make demo`; `make api` serves the read API on 127.0.0.1:8000 |
| 2026-10-29 | A → B | Auditor | `cadrecover.audit.auditor.run_audits()`; failed audits zero weight via `db.failed_audits()` |
| 2026-10-29 | A → B, C | Scoring entry point | `cadrecover.evaluation.score.score_source(challenge_id, source, job_id=, miner_hotkey=, glb_dir=)` → Evaluation; sandbox image `cadrecover-sandbox:build123d-0.13.0` (`docker build -t … images/cad-worker`) |
| 2026-10-29 | C → B | Miner servers + validator client | `cadrecover miner run`, `scripts/run-miners.sh` (5 local miners, writes `~/.cadrecover/miners.json`); `validator/client.py` dispatch/poll with signed results |
| 2026-10-29 | A → C | Practice challenge (retired, known seed) | `fixtures/public/sample_plate/` (challenge.json + drawing.png). Build your miner against it; never score it. |
| 2026-10-29 | A → B | Challenge creation for the scheduler | `cadrecover.challenges.pipeline.new_challenge(family="plate")` returns public facts; private record at `runtime/private/<id>/private.json` |
| 2026-10-29 | B → all | Envs, DB, paths | `make envs`, `make test`; `cadrecover.paths` (everything under `~/.cadrecover`); `cadrecover.storage.db.connect()` |

## Requests (change in a file you don't own)

| Date | From → owner | File | Request | Status |
| --- | --- | --- | --- | --- |
| 2026-10-29 | A, B → C | `cli.py`, `miner/templates.py`, `miner/strategies.py`, `miner/engine.py` | B added chain/auditor commands; A added `flange_source`, family dispatch and the engine entrypoint; C restyled the CLI in Phase 8 | done; logged |
| 2026-10-29 | A, B → C | `src/cadrecover/cli.py` | Created the file with `setup wallets`, `chain heartbeat` (B) and `challenge new/show` (A) before Phase 8. C owns it from here; restyle freely, but keep the commands working. | done; logged |

## Blockers

| Date | Agent | Blocked on | Waiting for | Resolved? |
| --- | --- | --- | --- | --- |
| 2026-10-29 | B | Testnet registration | Test TAO for owner coldkey `5HHKrbRMDmxMU8sEstz6bXLWq7LA1kgKwa7QaDC7UQuW7LMg` (subnet cost τ1.0) | no |
| 2026-10-29 | C | Real `claude-vision` miner | User's Anthropic API key | no |

## Decisions

| Date | Decision | Why | Affects |
| --- | --- | --- | --- |
| 2026-10-29 | Held-out family (REVIEW #3) is **not solved**: the validator is open source, so no family in code is secret; the real fix is feature-composed generation or an owner-run closed generator (post-hackathon) | An honest framing beats a fake "held-out" claim | A (generator), C (pitch and /security wording) |
| 2026-10-29 | Audit pass rule: mean audit Q over 3 fresh hidden tasks ≥ live mean − 10 (one-sided); a fail zeroes weight until a clean audit; an audit-failed miner still holding chain weight is revoked with a validator self-weight | REVIEW #5; LLM engines don't reproduce exactly | A, B, C (/audits page) |
| 2026-10-29 | Critical check rejects extra holes/slots | A superset of guessed holes passed C before | A; all families |
| 2026-10-29 | Localnet only: bootstrap turns commit-reveal off when the drand beacon lags > 100 rounds; receipt state comes from chain events | Stalled beacon → commits expire unrevealed | B |
| 2026-10-29 | Miners bind 127.0.0.1 and advertise the LAN IP (the chain rejects loopback); a same-host validator maps it back | Nothing exposed beyond loopback | B, C |
| 2026-10-29 | Miners run **mock/scripted strategies** until a vision-model API key is set; mocks are gated (`CADRECOVER_DEV_ORACLE=1`), local only, labelled `mock` | User request; lets the whole loop run end to end today | C, demo framing (say plainly which miners are mocks) |
| 2026-10-29 | Critical positions are measured across the through-axis (not 3D) | A 1 mm thickness misread zeroed whole sets in rounds 2–3 | A; scores from rounds 1–3 predate the fix |
| 2026-10-29 | Protocol 0.2.0: `build_part` receives only overrides | Passing all values let a template score without reading the drawing | all |
| 2026-10-29 | Artifact server on 127.0.0.1:8790 | 8090 is taken on the Windows host (mirrored networking) | B, C |
| 2026-10-29 | Retire any challenge whose seed or values were exposed (`ch_51b40eea12677918`, `ch_df01e47027a76f04`) | Ground truth of an exposed challenge is reproducible | B (scheduler must only use `status = 'active'`) |
| 2026-10-29 | Publish only the drawing PNG; draftwright's SVG stays private | SVG geometry is machine-readable and would bypass reading the drawing | A, C |
| 2026-10-29 | Drawing coverage = draftwright's ledger all `placed` + every required value in a rendered label; otherwise resample with the next seed | Text in the SVG is converted to outlines, so it can't be searched | A |
| 2026-10-29 | Envs and runtime state in `~/.cadrecover` (WSL filesystem); drawing env on Python 3.13 / build123d 0.11; CAD env build123d 0.13 | SQLite WAL is unsafe on `/mnt/c`; draftwright's pins | all |
| 2026-10-29 | Scoring v2.1: score every parameter set (s₀ + 3 hidden edits, equal weight); a missing or misplaced critical feature zeroes the set; hidden edits must be discriminative (feature shift > 5× tolerance, reference self-IoU < 0.85); floor starts at 50 | The old formula paid a constant model ~70 | A (evaluator), B (aggregation floor), C (API and pages show per-set results) |

## Open questions (from REVIEW.md)

- Rewrite positioning against Backflip's "2D Drawing to CAD" (REVIEW #2). Owner: whoever writes the README and pitch in Phase 11.
- Held-out or feature-composed family (REVIEW #3): decided (see Decisions); generator not built. Owner: A.
- Audit pass rule (REVIEW #5): decided (see Decisions). A fixed model endpoint for auditing claude-vision is still open. Owner: A.
- draftwright is AGPL; keep it out of anything shipped to customers (REVIEW #6). Owner: A.
