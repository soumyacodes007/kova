# Agent C: miner, API and frontend (phases 4, 8, then 9–11)

Owns: `miner/`, `api/`, `cli.py`, `apps/web/`, `fixtures/public/`, and the `protocol/` job and result envelopes. Rules: [AGENTS.md](../AGENTS.md).

For each phase: tick items only with evidence (a command plus its result). List what's not done as clearly as what's done.

---

## Day 1: protocol drafts

**Status:** done (2026-10-29)

- [x] Job request and result envelope schemas in `protocol/jobs.py`:
  - `JobRequest`: idempotent `job_id`, PublicChallenge, `drawing_url`, deadline
  - `JobAccepted`, `JobStatus`
  - `JobResult`: source capped at 64 KB, `source_sha256` validated against the source, entry point, model ID and strategy version recorded but never trusted

**Done:** evidence in `tests/services/test_protocol.py`: `test_job_result_hash_must_match_source`, `test_job_request_round_trips` (in the 10 passed).
**Not done / gaps:** HTTP signing isn't in these bodies, by design: `bt.http_auth` headers carry it (Phase 4).
**Decisions:** the signature lives in transport headers, not in the envelope. A valid signature proves the sender, not correctness.
**Interfaces changed:** created v0.1.0.
**Blockers:** none. **Ready for Phase 4:** use `fixtures/public/sample_plate/` as the practice task (`cli.py` already has `challenge new/show`, added by A; command list below).

---

## Phase 4: Miner and signed jobs

**Status:** done with **mock strategies** (2026-10-29); real VLM strategies wait for an API key · **Done when:** a signed job returns build123d code that scores above the floor (50).

- [x] **FastAPI miner** (`miner/server.py`, `cadrecover miner run`):
  - `POST /v1/jobs` → 202, idempotent by `job_id` (a retry never re-runs the model)
  - `GET /v1/jobs/{id}`, `GET /v1/health`
  - every request is verified with `bt.http_auth.verify`: receiver binding, freshness, signature, replay via `InMemoryNonceStore`
  - optional validator allowlist (403)
  - the drawing's sha256 is checked against the challenge record
  - **responses are signed with the miner hotkey** (`POST /v1/results/{job_id}` payload bound to the validator), and the validator verifies them in `validator/client.py`
- [~] **Strategies:** per the user (2026-10-29), **mock/scripted for now**:
  - `mock-oracle` (reads perfectly) and `mock-noisy` (seeded misreads: thickness ±1 mm 35% of the time, hole +0.5 mm 15%). Both are labelled `mock`, need `CADRECOVER_DEV_ORACLE=1`, and only work on the validator's machine.
  - `claude-vision` is a slot that raises a clear error until it's implemented.
  - **Not done:** real strategies 1 (direct vision-to-CAD), 2 (extract-then-build) and 3 (render-and-repair).
- [x] **Diagnostic miners**, labelled `diagnostic`:
  - `diag-constant` (expect 25)
  - `diag-proportional` (expect 25)
  - `diag-wrong-holes` (expect 0)
  - `diag-crash` (forbidden import; expect 0)
- [x] **Recorded per job:** `model_id`, `strategy_version` (`<strategy>/<version>`) and `duration_s` in JobResult. Budget isn't tracked; mocks have no cost.

**Done-when evidence:**
- Round `run_47c501d8e4`: the real `mock-oracle` miner process (port 8101, wallet miner1) received a signed job, returned build123d source in a signed result, and the validator's sandboxed rebuild scored **Q 100 (100/100/100/100), above the floor of 50**.
- Tests: `tests/services/test_miner_protocol.py` **8 passed**:
  - round trip with a verified signed result
  - an idempotent retry runs the model once
  - a hash mismatch fails the job
  - **unsigned, tampered, wrong-receiver and replay → 401**
  - another validator can't read someone else's job → 404
  - the allowlist → 403

**Not done / gaps:**
- **No real vision strategy.** It needs `ANTHROPIC_API_KEY`. Then implement `ClaudeVision` (read the claude-api docs first): send the drawing PNG, the public record and the edit rules; return `DRAWN` + `build_part(overrides)` source; render-and-repair loop for strategy 3.
- **Job state is in memory**, so a miner restart forgets in-flight jobs. The validator treats that as a timeout.
- **Mocks read ground truth.** They prove the loop, not miner skill. Never run them on testnet.

**Decisions:**
- **Mock strategies are gated:** they need `CADRECOVER_DEV_ORACLE=1` and a local private record, and they're labelled `mock` in `/v1/health` and the leaderboard labels.
- **Results are signed over the response body** as a `POST /v1/results/{job_id}` payload bound to the validator. That reuses `http_auth` without a custom scheme.

**Interfaces changed:** none beyond protocol 0.2.0 (A).
**Blockers:** the vision-model API key (user is sorting it out).

---

## Phase 8: API, CLI and terminal demo

**Status:** done · **Done when (BACKEND GATE):** `make demo` runs a full round, a weight submission and an audit end to end, visible in the terminal alone.

- [x] FastAPI read API and SSE with resumable event IDs; TypeScript types generated from OpenAPI (`src/cadrecover/api/`, `docs/api/openapi.json`, `apps/web/lib/api-types.ts`; regenerate with `scripts/export-openapi.py`, `--check` for staleness)
- [x] CLI: `doctor`, `task sample`, `score`, `miner run`, `validator run`, `status` (+ `events --follow`, `api serve`, `auditor run`)
- [x] Rich logs, 3-pane tmux layout, `make demo` starts everything (`DEMO_HEADLESS=1` for a scripted run; `make demo-down`)
- [x] Gate passed → marked in `shared.md` with evidence

**Done-when evidence:** from a clean state (DB and `chain.json` moved to `~/.cadrecover/backup-pre-gate-20261029-0911`, localnet container recreated): `DEMO_HEADLESS=1 make demo` → localnet blocks 12 → 21; bootstrap netuid 2, commit-reveal on; 5 engine images; 5 miners (axons + engine commitments); `doctor` all checks passed; 2 rounds (oracle 100, noisy 100, constant 25, wrong-holes 0, crash 0); weights `{2: 0.5, 3: 0.5}` committed at block 1584, revealed at 1595; audit uid 3 engine `73cf808a1f19` live 100.0 audit 90.3 (100, 88, 83) → PASS; `chain weights` block 2515 `{2: 0.5, 3: 0.5}`; `backend gate check: ok round run_6b6a61efe4 done | weights revealed | audits uid 3 pass` → `demo ok`, EXIT=0. Full log: `~/.cadrecover/runtime/logs/gate-demo.log`.

**Done:** API endpoints status, runs, run detail (per-set V/C/G/D/Q, failed checks, GLB/drawing URLs), leaderboard, miners, weights with every receipt, commitments, audits, public challenges, events + SSE stream (`Last-Event-ID` resume, keep-alives); read-only DB; CORS localhost:3000. Tests: `tests/services/test_api.py` (54: shapes, no private leak, 13 path-traversal attempts, SSE resume, OpenAPI freshness), `tests/services/test_cli.py`.

**Not done / gaps:**
- No endpoint for miner source or STEP download (Phase 11 needs STEP).
- Chain probe in `/v1/status` only for `local`.
- Miner logs are empty (server logs at warning); `events --follow` replaces them in the tmux pane.
- Audits take 3–10 min, so `make demo` is ~15 min end to end.
- Honest miners are mocks until claude-vision is wired.

**Decisions:** while a challenge is active the API withholds per-set values, failed-check text and reference GLBs (they leak answers); all shown once retired. Leaderboard `latest_batch_weight` is what the newest batch gave; use it for on-chain claims.
**Interfaces changed:** new read API (OpenAPI is the contract for the frontend).
**Blockers:** none.

---

## Phase 9: Arena on the real API *(only after the backend gate)*

**Status:** blocked by gate · **Done when:** a live round plays in the browser with no fixture data.

- [ ] Next.js shell, status bar, React Three Fiber viewer loading validator GLBs
- [ ] /arena/[runId]: drawing, miner strip, live events, per-set checks, ghost overlay, section view, failure focus
- [ ] Parameter slider: queue a rebuild on release; swap the model when the result arrives

**Done-when evidence:**
**Done:**
**Not done / gaps:**

---

## Phase 10: Trust pages *(with A and B)*

**Status:** blocked by gate · **Done when:** a judge can trace any score to its checks and its chain receipt.

- [ ] /leaderboard, /security (attack chart from measured numbers), /audits, /runs/[id]
- [ ] Block numbers on every weight set, commitment and audit; reproduce-score command

**Done-when evidence:**
**Done:**
**Not done / gaps:**

---

## Phase 11: Ship *(all)*

**Status:** blocked by gate · **Done when:** one live run, one recorded run, a real chain receipt and a downloadable STEP.

- [ ] Testnet run if registration is live; otherwise localnet with readback
- [ ] README, MINER.md, MECHANISM.md; positioning vs Backflip (REVIEW #2)
- [ ] Backup video of a real run; rehearse three times

**Done-when evidence:**
**Done:**
**Not done / gaps:**

---

## Session log (newest first)

| Date | Branch | What changed | Tests run | Next |
| --- | --- | --- | --- | --- |
| 2026-10-29 | b/phase-6-chain | Read API + SSE + TS types, doctor/status/task sample/events/api serve, rich logs, `make demo` | services 138 passed; gate run EXIT=0 | Wire claude-vision; Phase 9 arena on the real API |
| 2026-10-29 | c/phase-4-miner | Signed FastAPI miner, mock/diagnostic strategies, templates, `miner run`, `scripts/run-miners.sh` | services miner protocol 8 passed; live round Q 100 | Wire `ClaudeVision` when the API key arrives; Phase 8 after the Phase 6/7 gate |
| 2026-10-29 | a/phase-0-protocol | Job envelopes; `cli.py` created with B's and A's commands (C owns the file; see `shared.md` Requests) | 10 passed | Phase 4: FastAPI miner + strategy 1 against the sample fixture |
