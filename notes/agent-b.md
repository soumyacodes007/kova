# Agent B: chain and validator (phases 1, 5, 6)

Owns: `validator/`, `chain/`, `storage/`, `compose.yaml`, `Makefile`, `pyproject.toml`, `uv.lock`, and the `protocol/` weight batch and receipt schemas. Rules: [AGENTS.md](../AGENTS.md).

For each phase: tick items only with evidence (a command plus its result). List what's not done as clearly as what's done.

---

## Phase 1: Setup and environments (unblocks everyone; do first)

**Status:** done (2026-10-29) · **Done when:** every environment imports its libraries and the local chain produces blocks.

- [x] Three locked environments (`make envs`), each with its own `uv.lock`; the venvs live in `~/.cadrecover/envs/`:
  - **services:** root `pyproject.toml` + `uv.lock`, extra `services`. Python 3.12.3, bittensor 11.3.0, FastAPI 0.162, pydantic 2.14.
  - **cad:** `images/cad-worker/`. Python 3.12.3, build123d **0.13.0**, cadquery-ocp-novtk 8.0.1.1.
  - **drawing:** `images/drawing-worker/`. Python **3.13.12**, draftwright 0.4.35, build123d **0.11.1**, PyMuPDF 2.0.
- [x] Docker Compose skeleton (`compose.yaml`): `localnet` on 127.0.0.1:9944/9945, with later services listed by phase and owner
- [x] SQLite (WAL) schema (`storage/schema.sql`, `storage/db.py`): challenges, miners (hotkey + registration block), runs, assignments (UNIQUE run + hotkey), submissions, evaluations, evaluation_sets, events (SSE cursor), weight_batches, receipts, commitments, audits
- [x] Local subtensor running (`docker compose up -d localnet`, image `subtensor-localnet:devnet`). Wallets for owner, validator and miner1–5 in `~/.cadrecover/wallets/` (0700), mnemonics in `MNEMONICS.local-dev.txt` (0600). Nothing in git.
- [x] Runtime folders outside the repo: `~/.cadrecover/runtime/` (DB + `private/` 0700) and `~/.cadrecover/artifacts/public/` (`paths.py`)

**Done-when evidence:**
- `bash scripts/check-envs.sh`:
  - services: `bittensor 11.3.0 | fastapi 0.162.0 | pydantic 2.14.1 | protocol 0.1.0`
  - cad: `python 3.12.3 | build123d 0.13.0 | volume 174.867 | step 19022 B` (builds and exports a solid)
  - drawing: `python 3.13.12 | build123d 0.11.1 | draftwright 0.4.35 | pymupdf 2.0`
- `cadrecover chain heartbeat --network local` → `{"first": 23, "second": 33, "producing": true, "spec_version": 484}`
- `cadrecover setup wallets` printed 7 coldkey/hotkey pairs
- `tests/services/test_storage.py` → WAL on, all tables present, challenge round trip, idempotent reconnect

**Not done / gaps:**
- **Testnet funding/registration not started.** It's listed under Phase 6; ask the organizers early.
- **Localnet runtime is spec 484** (devnet image); mainnet is 486. That's fine for the loop, but don't claim mainnet behaviour from localnet.
- **Dev wallets have no password**, by design for unattended local runs. Never fund them on mainnet.
- **Only `localnet` runs in Compose for now;** the other services are commented placeholders.
- **No Postgres,** as the PRD allows (SQLite WAL on one host).

**Decisions:**
- Envs and runtime state live in `~/.cadrecover` on the WSL filesystem: SQLite WAL is unreliable on `/mnt/c`, and ground truth stays outside the repo.
- The drawing env runs Python 3.13, because draftwright needs it for build123d 0.11 (on 3.12 it pins <0.11). The CAD env stays on build123d 0.13; the two exchange STEP files.
- **Tests are split per env:** `tests/services`, `tests/cad`, `tests/drawing`, all run by `make test`.

**Interfaces changed:** `protocol/weights.py` v0.1.0 (WeightBatch, WeightReceipt, MinerIdentity).
**Blockers:** none.

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
| 2026-10-29 | b/phase-1-setup | 3 envs + locks, compose localnet, SQLite schema, wallets, CLI `setup wallets` / `chain heartbeat`, Makefile | services 12 passed (at merge), heartbeat producing | Phase 5 scheduler against stubs; start testnet funding |
