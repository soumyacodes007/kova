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

**Status:** not started · **Done when:** a signed job returns build123d code that scores above the floor (50).

- [ ] FastAPI miner: POST /v1/jobs (202), GET /v1/jobs/{id}, GET /v1/health; `bt.http_auth` sign and verify; idempotent assignments
- [ ] Strategy 1: direct vision-to-CAD; then strategy 2 (extract-then-build) and strategy 3 (render-and-repair)
- [ ] Diagnostic miners: constant output (expect Q 25), wrong holes (expect 0), crash or forbidden import (expect 0), each labelled
- [ ] Record model ID, strategy version, duration and budget per job

**Done-when evidence:**
**Done:**
**Not done / gaps:**
**Decisions:**
**Interfaces changed:**
**Blockers:**

---

## Phase 8: API, CLI and terminal demo

**Status:** not started · **Done when (BACKEND GATE):** `make demo` runs a full round, a weight submission and an audit end to end, visible in the terminal alone.

- [ ] FastAPI read API and SSE with resumable event IDs; TypeScript types generated from OpenAPI
- [ ] CLI: `doctor`, `task sample`, `score` (wraps A's evaluator), `miner run`, `validator run`, `status`
- [ ] Rich logs, 3-pane tmux layout, `make demo` starts everything
- [ ] Gate passed → mark it in `shared.md` with evidence

**Done-when evidence:**
**Done:**
**Not done / gaps:**
**Decisions:**
**Interfaces changed:**
**Blockers:**

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
| 2026-10-29 | a/phase-0-protocol | Job envelopes; `cli.py` created with B's and A's commands (C owns the file; see `shared.md` Requests) | 10 passed | Phase 4: FastAPI miner + strategy 1 against the sample fixture |
