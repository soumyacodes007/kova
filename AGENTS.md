# AGENTS.md: how the three coding agents work on CADRecover

Three coding agents (A, B, C) build CADRecover in parallel, following [PRD.md](PRD.md) phase by phase. Every agent leaves written notes, so any agent (or a human) can see what is done, what isn't, and why.

**Read this file first, every session.**

## Who owns what

| Agent | Phases | Owns (may edit freely) |
| --- | --- | --- |
| **A: Mechanism** | 2 Challenges and drawings · 3 Evaluator and sandbox · 7 Families, audits, robustness | `src/cadrecover/challenges/` `evaluation/` `execution/` `audit/` · `images/cad-worker/` `images/drawing-worker/` · their tests |
| **B: Chain and validator** | 1 Setup and environments · 5 Validator rounds and storage · 6 Chain integration | `src/cadrecover/validator/` `chain/` `storage/` · `compose.yaml` `Makefile` `pyproject.toml` `uv.lock` · their tests |
| **C: Miner, API and frontend** | 4 Miner and signed jobs · 8 API, CLI and terminal demo · 9–11 Frontend (leads, after the backend gate) | `src/cadrecover/miner/` `api/` `cli.py` · `apps/web/` `fixtures/public/` · their tests |

**Shared** (edit only by recording it in `notes/shared.md` → Contracts first):
- `src/cadrecover/protocol/`: public and private challenge records, job and result envelopes, evaluation records, protocol version
- `docs/`
- `PRD.md` and `REVIEW.md`

Need a change in a file you don't own? Add a row to **Requests** in `notes/shared.md`. If it's a one-line unblock, you may make it yourself, but log it there.

## Order and dependencies

```
Phase 1 (B) ──► everything
Phase 2 (A) ──► Phase 3 (A) ──► Phase 7 (A)
                    │                ▲
Phase 4 (C) ◄── sample challenge from A (handoff)
Phase 5 (B) ◄── 2 + 3 (A) and 4 (C)   (build against stubs until they land)
Phase 6 (B) ◄── 1; needs 5's scores to finish; 7's audits need 6's commitments
Phase 8 (C) ◄── 5's event log; `cadrecover score` wraps A's evaluator
BACKEND GATE (Phase 8 done-when: `make demo` runs round + weights + audit end to end)
Phases 9–11 (C leads; A and B support the trust pages) ◄── backend gate only
```

- **Day 1 priorities:** B does Phase 1. A drafts the challenge and evaluation schemas in `protocol/`. C drafts the job and result envelopes. Then A hands C one sample public challenge (a PNG plus JSON), so the miner can start.
- **No frontend work before the backend gate passes.** It's marked in `notes/shared.md`.
- **Phase 7 family order:** flange, then wafer chuck, then vacuum chamber. The wafer chuck and the chamber are stretch goals (see REVIEW.md #4).

## Every session

1. `git pull`. Read: `AGENTS.md`, your phase in `PRD.md`, `REVIEW.md`, `notes/shared.md`, your own `notes/agent-X.md`, and the notes of any agent you depend on.
2. Pick the next unchecked item in **your** notes file, in phase order. If it's blocked, write the blocker in `notes/shared.md` → Blockers and take the next unblocked item.
3. Work on a branch: `a/phase-3-iou`, `b/phase-6-weights`, `c/phase-4-miner`.
4. Before merging to `main`: run the tests, rebase on `main`, and keep `main` green. Commit messages start with your agent tag: `[A] phase 3: hidden edit sampler`.
5. **Before you stop**, update your notes file: tick items, add evidence, record decisions, and add a session-log line. Update `notes/shared.md` if a gate, contract or handoff changed.

## Notes rules (what keeps three agents honest)

- **A box is ticked only with evidence:** the command you ran and what it printed (or a test name and its result). "Should work" is not done.
- **A phase is `done` only when the PRD's "Done when" check passes,** and you ran it. Paste the command and result under the phase.
- **Write down what is *not* done just as clearly as what is:** known gaps, skipped cases, TODOs, flaky tests.
- **Record every decision that changes behaviour** (in your file and in `shared.md` → Decisions): what, why, and who it affects.
- **Interface change?** Bump the version in `protocol/`, log it in `shared.md` → Contracts, and name the agents who must update.
- **Don't edit another agent's notes file.** Reply in `shared.md` instead.

## Non-negotiables (from the PRD)

- **Scoring (PRD v2.1):**
  - every parameter set is scored: the drawing's values plus 3 hidden edits, averaged equally
  - a missing or misplaced critical feature zeroes that set
  - hidden edits must be discriminative: a feature moves more than 5× tolerance, and the reference's self-overlap is below 0.85
  - the self-test must reproduce **100 / 75 / 25 / 0**
  - the floor starts at 50
  - never weaken a check or a test to make something pass
- **Never run miner code in the validator or API process.** Sandbox rules are in PRD §Validator.
- **Ground truth, wallets, keys and `.env` never go in git.** Runtime secrets and private challenge records live in `runtime/` (gitignored).
- **Networks:** `local` or `test` only. Never mainnet.
- **No invented data on live routes.** Fixtures are labelled and only used by tests and replays.
- **Run on Linux or WSL.** bittensor v11 has no native Windows support.

## Files

- `notes/shared.md`: gate status, contracts, handoffs, requests, blockers, decisions, open questions
- `notes/agent-a.md`, `notes/agent-b.md`, `notes/agent-c.md`: each agent's phase checklist, evidence and session log
