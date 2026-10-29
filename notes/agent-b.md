# Agent B: chain and validator (phases 1, 5, 6)

Owns: `validator/`, `chain/`, `storage/`, `compose.yaml`, `Makefile`, `pyproject.toml`, `uv.lock`, and the `protocol/` weight batch and receipt schemas. Rules: [AGENTS.md](../AGENTS.md).

For each phase: tick items only with evidence (a command plus its result). List what's not done as clearly as what's done.

---

## Phase 1: Setup and environments (unblocks everyone; do first)

**Status:** not started · **Done when:** every environment imports its libraries and the local chain produces blocks.

- [ ] WSL or Linux, uv, Python 3.12; three locked environments (services, drawing worker, CAD worker), with exact versions pinned
- [ ] Docker Compose skeleton
- [ ] SQLite (WAL) schema: runs, assignments, submissions, evaluations (per set), events, weight batches, receipts, audits
- [ ] Local subtensor running; wallets for the owner, the validator and each miner, kept out of git
- [ ] `runtime/` folder for private challenge records and secrets (gitignored)

**Done-when evidence:**
**Done:**
**Not done / gaps:**
**Decisions:**
**Interfaces changed:**
**Blockers:**

---

## Phase 5: Validator rounds and storage

**Status:** not started · **Done when:** a full round with 5 miners completes and the leaderboard numbers are in SQLite.

- [ ] Scheduler: create a challenge (A's generator), discover miners from the metagraph, dispatch, poll, enforce the deadline
- [ ] Rebuild and evaluate every submission (A's evaluator); matched batches; rolling aggregation
- [ ] Weight = max(0, mean Q − floor); floor starts at **50**; no-update state plus an alert when nobody qualifies
- [ ] Identity = hotkey + registration (a recycled UID starts fresh)
- [ ] An event-log entry for every step (feeds C's SSE)

**Done-when evidence:**
**Done:**
**Not done / gaps:**
**Decisions:**
**Interfaces changed:**
**Blockers:**

---

## Phase 6: Chain integration

**Status:** not started · **Done when:** Phase 5 scores land on-chain as weights and read back correctly.

- [ ] Register the subnet and neurons on the local node; miners publish endpoints with `bt.ServeAxon`; validator permit confirmed
- [ ] Chain process: `bt.SetWeights` through plan → execute → readback; receipts and commit/reveal state stored
- [ ] Engine commitments with `set_commitment`; read back per miner (confirm the v11 read API; REVIEW: `client.identity.commitment` unverified)
- [ ] Testnet funding and registration started in parallel
- [ ] Optional: test weight-setting and commit-reveal against mainnet chain rules with [TensorFork](https://github.com/soumyacodes007/tensorfork)

**Done-when evidence:**
**Done:**
**Not done / gaps:**
**Decisions:**
**Interfaces changed:**
**Blockers:**

---

## Session log (newest first)

| Date | Branch | What changed | Tests run | Next |
| --- | --- | --- | --- | --- |
