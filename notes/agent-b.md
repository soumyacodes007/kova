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

**Status:** done (2026-10-29), with **static discovery** until Phase 6 · **Done when:** a full round with 5 miners completes and the leaderboard numbers are in SQLite.

- [x] **Scheduler** (`validator/round.py`, `cadrecover validator run`):
  - A's `new_challenge()`, which now includes the hidden edits
  - discovery from `~/.cadrecover/miners.json` (`validator/discovery.py`, written by `scripts/run-miners.sh`). **The metagraph is Phase 6.**
  - signed dispatch and polling (`validator/client.py`) with result signatures verified; deadline enforced (default 180 s), then timeout = 0
  - drawings served read-only from the public store (`validator/artifacts.py`, 127.0.0.1:**8790**)
- [x] Every submission is rebuilt and evaluated through A's `score_source` (sandbox + evaluator). Every miner gets the same task each round. Rolling aggregation is in `validator/aggregate.py`: WINDOW 20, MIN_SAMPLES 1 for the demo.
- [x] **Weights:**
  - weight = max(0, mean Q − 50), normalized
  - nobody above the floor → empty batch, receipt `skipped_no_qualifier`, event `weights.no_update`
  - batches are stored with receipt state **`proposed`**; chain submission is Phase 6
- [x] Identity = hotkey + `registered_at_block` (the `miners` table key; aggregation groups by it)
- [x] **Events at every step:** `run.started`, `job.sent / done / failed / timeout / dispatch_failed`, `job.evaluated` (per-set scores), `weights.proposed / no_update`, `challenge.retired`. The challenge is retired after each round.

**Done-when evidence:**
- Round 1 (`run_47c501d8e4`, **3 m 12 s**, 5 real miner processes):
  - mock-oracle **100**, mock-noisy **100**, diag-constant **25** [100, 0, 0, 0], diag-wrong-holes **0**, diag-crash **0**
  - weights proposed `{uid1: 0.5, uid2: 0.5}`
- Rounds 2–3 (with the pre-fix evaluator): leaderboard mock-oracle 100 (3 samples), **mock-noisy 58.3**, constant 25, crash 0, wrong-holes 0; weights `{1: 0.857, 2: 0.143}`. This exposed A's through-axis bug (see agent-a); the fix is in.
- Rounds 4–5 (after A's fix):
  - mock-noisy **93.6** (sets 91 / 91 / 100 / 91: a thickness misread now costs only G and D) and **0** in round 4 (hole misread, correctly zeroing every set)
  - leaderboard after 5 rounds: mock-oracle 100 (w 0.931), mock-noisy 53.7 (w 0.069), constant 25, wrong-holes 0, crash 0
- SQLite after 3 rounds: runs 3 · assignments 15 · submissions 15 · evaluations 15 · evaluation_sets 60 · events 63 · weight_batches 3 · receipts 3 (`proposed`).
- Tests: `tests/services/test_aggregate.py` **4 passed**:
  - floor and 2:1 normalisation
  - no qualifier → no weights
  - an outage is excluded, not zeroed
  - a recycled UID starts fresh

**Not done / gaps:**
- **Discovery is static** (`miners.json`). Phase 6 reads the metagraph and only queries registered, serving miners.
- **Weights are not on-chain yet.** Receipts stop at `proposed`.
- **MIN_SAMPLES = 1 is a demo setting.** Raise it (e.g. 5) for real runs.
- **Scoring is sequential:** about 3 minutes per round for 5 miners, mostly sandbox and evaluator time. Parallelising rebuilds (2–3 workers) would roughly halve it.
- **One challenge per round** (the PRD's "same family mix per batch" is trivially true with one family).
- The artifact server serves the whole public store. That's fine because it only holds public files, but it doesn't check whether a challenge is still active.

**Decisions:**
- Artifact port moved from 8090 to **8790** (8090 is taken by a Windows process; WSL mirrored networking shares ports).
- Challenges are retired right after their round, since their ground truth may then be revealed (`/runs` pages, Phase 10).
- Job ids are `<run_id>-uid<N>`.

**Interfaces changed:** none (uses protocol 0.2.0).
**Blockers:** none for Phase 6. Start testnet funding.

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
| 2026-10-29 | c/phase-4-miner (B commit) | Validator round, signed client, static discovery, artifact server, aggregation, DB writers, `validator run` / `leaderboard` | aggregate 4 passed; 5 live rounds | Phase 6: register on localnet, metagraph discovery, `bt.SetWeights` with readback |
| 2026-10-29 | b/phase-1-setup | 3 envs + locks, compose localnet, SQLite schema, wallets, CLI `setup wallets` / `chain heartbeat`, Makefile | services 12 passed (at merge), heartbeat producing | Phase 5 scheduler against stubs; start testnet funding |
