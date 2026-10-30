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

**Status:** done (localnet; testnet waits for test TAO) · **Done when:** Phase 5 scores land on-chain as weights and read back correctly.

- [x] Register the subnet and neurons on the local node; miners publish endpoints with `bt.ServeAxon`; validator permit confirmed: `cadrecover chain bootstrap` → netuid 2, validator uid 1, miner1–5 uids 2–6, permit True after an epoch; `serve-axon` ×5 → metagraph shows 5 axons
- [x] Chain process: `bt.SetWeights` through plan → execute → readback; receipts and commit/reveal state stored (`receipts` table, one row per state)
- [x] Engine commitments with `set_commitment`; read back per miner: the read is `sub.read("commitment", netuid=, hotkey_ss58=)` → `Commitment(block, data, fields)` (REVIEW's `client.identity.commitment` does not exist in v11)
- [ ] Testnet funding and registration: started; registration cost read live = τ1.0, but owner/validator/miner coldkeys hold τ0 on testnet. **Blocked on test TAO** (owner coldkey `5HHKrbRMDmxMU8sEstz6bXLWq7LA1kgKwa7QaDC7UQuW7LMg`)
- [ ] Optional: TensorFork run against mainnet rules (not done)

**Done-when evidence:**
- `cadrecover validator run --deadline 90` → `[round] metagraph netuid 2: 5 miners serving an axon` … `uid 2 mock-oracle Q 100.0` … `weights proposed: {2: 1.0}` → `[chain] weights submitted at block 15596` → `[chain] read back at block 15596: {2: 1.0} (matches the batch)`; `cadrecover chain weights` → `revealed_row {"2": 1.0}` at block 15602.
- Engine commitments: miner1–5 committed at blocks 17816–17864, each read back equal (`chain commit-engine` raises on mismatch).
- Audit-failed revoke (agent run): swapped engine → audit fail → `revoking it with a self-weight {1: 1.0}` → submitted + read back at block 29321; honest engine restored → `{2: 1.0}` read back at block 32749.
- Tests: `tests/services/test_chain_offline.py` (commitment encode/decode for every SDK shape, u16 readback tolerance, axon loopback mapping, audit pass rule, audit-zeroed and stale identities, audit-zeroed weight still on chain).

**Done:** `chain/bootstrap.py` (idempotent: fund from //Alice, RegisterSubnet or recover ours, StartCall, burned_register, AddStake, drand check), `chain/neurons.py` (ServeAxon, metagraph discovery, SetWeights, readback), `chain/commitments.py`, `validator/round.py` (metagraph discovery when `chain.json` exists, `--static` keeps Phase 5 behaviour), `aggregate.standings(current=, zeroed=)`, db receipts/commitments/audits helpers, CLI `chain bootstrap|serve-axon|weights|commit-engine`.

**Not done / gaps:**
- Fresh localnet (gate run): the drand beacon was current, commit-reveal stayed **on**, and receipts show the real flow: `proposed → committed (block 1584) → revealed (block 1595)`, and `committed 3619 [TimelockedWeightsCommitted] → revealed 3629`. On the earlier long-running localnet the beacon stalled and bootstrap turned commit-reveal off (see Decisions).
- Observed, not explained: the very first weight set on the fresh subnet (block 986) was readable in the same block, so it was most likely a plain set; its receipt said `committed` because the label then came from the hyperparameter. Fixed: the state now comes from the chain's own events (`TimelockedWeightsCommitted` → committed, otherwise submitted), logged with each `weights.*` event. State at 986 is pruned, so the cause can't be confirmed.
- Earlier long-running localnet: commit-reveal off, receipts `proposed → submitted → revealed`. The committed state was shown once (`TimelockedWeightsCommitted` at block 14426, reveal round 33483222) but could not reveal. Testnet keeps commit-reveal on; `_set_weights` waits for the reveal and records `committed` then `revealed` — unverified until testnet.
- A miner that only drops below the floor keeps its old on-chain row until someone else qualifies (only the audit-failed case is revoked).
- The self-weight revoke puts the validator uid into `WeightBatch.weights`; consumers read the `revokes_audit_failed` event flag. A protocol field would be cleaner (shared contract; not changed).
- Incentive (the third state) is not read back yet.

**Decisions:**
- Localnet only: `bootstrap` measures the drand lag (`LastStoredRound` vs real quicknet round). This image's beacon is stalled (~1300 rounds behind, never advances), so timelocked commits expire unrevealed; bootstrap turns `commit_reveal_weights_enabled` off for our subnet and records why in `chain.json`.
- BurnedRegister is forced through the MEV shield, which this single-node localnet never includes; on localnet only we submit the raw `burned_register` call. Testnet keeps the intent.
- The chain rejects loopback axons: miners bind 127.0.0.1, advertise this host's LAN IP, and a same-host validator maps that IP back to 127.0.0.1 (same-machine demo only).
- Commitments are hotkey-signed (`submit_call(..., signer="hotkey")`); payload `{"e": "sha256:…", "s": "strategy@version"}` ≤ 128 bytes Raw.
- Admin calls retry through the "protected weights window" around each epoch.

**Interfaces changed:** none in `protocol/`. New CLI commands (listed above).
**Blockers:** test TAO for testnet.

---

## Session log (newest first)

| Date | Branch | What changed | Tests run | Next |
| --- | --- | --- | --- | --- |
| 2026-10-29 | b/phase-6-chain | Bootstrap, ServeAxon, metagraph discovery, SetWeights + readback + receipts, engine commitments, audit-failed revoke, drand-stall handling | services 131 passed; live readbacks at blocks 15596, 29321, 32749 | Testnet once test TAO arrives; commit → reveal receipts there |
| 2026-10-29 | c/phase-4-miner (B commit) | Validator round, signed client, static discovery, artifact server, aggregation, DB writers, `validator run` / `leaderboard` | aggregate 4 passed; 5 live rounds | Phase 6: register on localnet, metagraph discovery, `bt.SetWeights` with readback |
| 2026-10-29 | b/phase-1-setup | 3 envs + locks, compose localnet, SQLite schema, wallets, CLI `setup wallets` / `chain heartbeat`, Makefile | services 12 passed (at merge), heartbeat producing | Phase 5 scheduler against stubs; start testnet funding |

## Phase 12 / Stage 2 Track B — king of the hill (2026-10-30/31)

**Status:** implementation complete, live verification in progress; not claiming the final gate.
Branch: b/phase-12-hill, atop A prerequisite ca8b9a6. No push.

- [x] Protocol0.3.0 model/hill records and shared Track A viewer shapes. Full services suite: **266 passed, 1 deprecation warning in72.60s**. Latest CLI tests after cap flags: **23 passed in4.60s**.
- [x] Metadata-only HF precheck: pinned40hex SHA, full safetensors/config,20,000,000,000 byte limit, sorted path:LFSsha fingerprint, duplicate rejection. Live model check Qwen/Qwen2.5-VL-3B-Instruct revision66285546d2b821cf421d4f5eb2576359d3770cd3: **7,509,337,976 bytes**, fingerprint ab78c2768a6df68a539e2c3303b8045bbc21c710d05059edef8d4a005d9e62b5; no weights downloaded.
- [x] Fixed Chutes harness, single python block, one network retry, usage/latency, atomic spend reservations. Unknown charges keep conservative bounds. Default$3 total/$0.50 match; CLI configurable. Excludes nonvision/unpriced/Kimi-K3 by default.
- [x] Real Gemma flange practice smoke ch_bb5f1e95eeddd029: **Q0**, sets0/0/0/0, **$0.00042951**, prompt1646/completion627, latency34.718s. Miner failure: invalid build123d extrude positional call. Scoring unchanged. Runtime log: ~/.cadrecover/runtime/logs/hill-smoke.log.
- [x] Local model submit miner1: hotkey-signed commitment readback **block2274**, watcher submitted/prechecked/queued; amount0 fee explicitly simulated; deploy disabled detail.
- [x] SHA256 entropy and deterministic task plan; post-commit block enforced; plate/flange/wafer_chuck cycling. Paid source cache before sandbox; per-side evaluation cache only within match. Interrupted matches remain hidden for resume.
- [x] Strict margin>2, initial floor>=50, ties defend; lineage A..Z,AA; atomic champion/status/decision/retirement/events. Tests cover outage/cache/resume, rollback, shared tasks, rule boundaries, lineage and catalog self-weight receipts.
- [x] Deploy dry-run GPU24/concurrency4/pinned revision, guarded cleanup executor. **No live deployment**. Disabled due $50 build balance, unverified vision request support/runtime billing upper bound.
- [ ] Real local catalog3-task matches, crown, actual weight receipts, final browser gate.
- [ ] Final regression evidence and B/C commits.
- [ ] Testnet match/commit-reveal receipts: user spend approval not given; no registrations/spend made.

**Decisions:** catalog fingerprint identifies provider ID, not attested weights; miner fingerprint hashes sorted safetensors path:LFSsha lines. Entire MatchSummary.seed object stays null until decision and all tasks retired (public entropy reconstructs private dimensions). Network isolation; spend cap shared across networks. Catalog champion self-weight has explicit reason. Shared board logs all decisions.

**Testnet verified READ-ONLY:** netuid605, owner coldkey5HHKrbRMDmxMU8sEstz6bXLWq7LA1kgKwa7QaDC7UQuW7LMg; owner hotkey5Dr8ujsPL3vkwjFpyYAPLGPvZLhwjexP9MusLiocXUymL7Wf UID0; permitTrue; commit-revealTrue. One neuron. No testnet hill matches/weight batches.
- Actual register_network inclusion **8336712**, transaction0x867b34c7dfe3a5add1b2fba1136590cbb842abc870003764c361b8c28ebc6d99; block0xd28b41609ec865d16a6708c3503825fc3b7da06e0170780de6ae24ec50a88583.
- Actual start_call605 inclusion **8336717**, transaction0xf633cc11798ac215813230ab8b888f555a828d5143317231ec76f09738e7abfe; block0xbf24b4b93bfb457667b24cd61f2bc715d291f291dfe6960115e528f5e4372b9f.
- chain-test.json heads8336714/8336719 are later readbacks, not inclusion blocks. File preserved.

**Known gaps:** invalid/duplicate commitments archived in hill_commitments/rejection events, never overwrite prior model. Custom deploy unverified/disabled. Catalog endpoints cannot attest pinned weights. Spend totals include unknown reservations. Concurrent Track A demo uses shared localnet; preserve its processes.

2026-10-31 verification update: full services suite **270 passed, 1 warning in 77.85s** after provider receipts, pinned harness and required response-schema fixes. Frontend TypeScript, ESLint and production build passed from WSL using installed node.exe. Final CAD then drawing suites running sequentially. Initial match m_95247cd4bbce finished on harness1 at mean0; no crown invented. Harness2 is shared across all new challengers, with the API reference documented above in shared Decisions; fresh catalog run in progress.

Connection proof: actual HTTP200 response ID **1a5d304e0e2349169142cd496af5f73c**, Gemma model, prompt2285/output403, **$0.00042331**, latency31.679s. Saved outside git at ~/.cadrecover/runtime/logs/chutes-connection-proof.json. New hill.provider_response events contain provider IDs/usage/cost only, no credentials/images/source. Unit test verifies receipt correlation and secret omission.

Environment recovery: WSL DNS tunneling resolver10.255.255.254 failed for Chutes and Hugging Face; UDP probes confirmed public resolvers reachable. Temporary /etc/resolv.conf uses1.1.1.1/8.8.8.8; original saved /tmp/cadrecover-resolvconf-before-hill. Chutes catalog HTTP200 afterward. Runtime original credential stays in Downloads and WSL profile reads it directly into the environment without copying/printing it.
