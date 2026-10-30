# Agent A: mechanism (phases 2, 3, 7)

Owns: `challenges/`, `evaluation/`, `execution/`, `audit/`, `images/cad-worker/`, `images/drawing-worker/`, and the `protocol/` challenge and evaluation schemas. Rules: [AGENTS.md](../AGENTS.md).

For each phase: tick items only with evidence (a command plus its result). List what's not done as clearly as what's done.

---

## Day 1: protocol drafts

**Status:** done (2026-10-29)

- [x] Public and private challenge record schemas in `protocol/challenge.py`; versions in `protocol/version.py` (PROTOCOL_VERSION 0.1.0, SCORING_VERSION 2.1)
- [x] Evaluation record schema in `protocol/evaluation.py`: `SetScore` per set (V, C, G, D, failed checks with location), `Evaluation` with exactly 4 sets. The canonical formula is `set_quality()`/`task_quality()`.
- [x] Handoff to C: `fixtures/public/sample_plate/` (challenge.json + clean drawing.png), logged in `shared.md`

**Done:**
- Evidence: `~/.cadrecover/envs/services/bin/python -m pytest -q tests/services/test_protocol.py` → **10 passed**. Covers:
  - the PRD v2.1 worked table: **100 / 75 / 25 / 0**
  - an invalid build zeroing a set
  - the four-set rule
  - a validator outage having no score
  - the public record carrying no seed or values
  - the JobResult hash check

**Not done / gaps:** none for day 1.
**Decisions:**
- The public record holds parameter *names and ranges* only, never the drawn values; miners must read the drawing.
- The score formula lives once, in `protocol/evaluation.py`; the evaluator (phase 3) must call it, not reimplement it.

**Interfaces changed:** created v0.1.0 (see `shared.md` → Contracts).
**Blockers:** none.

---

## Phase 2: Challenges and drawings

**Status:** done (2026-10-29) · **Done when:** one command produces a hidden plate and a drawing a person can read.

- [x] Plate family generator with a private seed, plus a reference self-test
  - `challenges/families/plate_spec.py`: pure data, seeded `sample()`, `is_valid()`, 0.5 mm steps, optional centred slot
  - `families/plate.py`: build123d geometry; `self_test()` checks a valid single solid, exact analytic volume, and every feature matched
  - `challenges/measure.py`: holes and slots read from top-face circle edges; shared with the phase 3 evaluator
- [x] draftwright drawing (SVG → PNG), lint coverage check, scan look (`challenges/drawing_worker.py`). Coverage needs both:
  1. every requirement in draftwright's own ledger is `placed`
  2. every required value appears in a rendered label (`plate_spec.required_labels`)
  - Rasterized with PyMuPDF at 150 dpi. The scan look is seeded: rotation ±0.6°, blur, noise, paper tint.
- [x] Public and private challenge records written to storage (`challenges/pipeline.py`):
  - public: `~/.cadrecover/artifacts/public/<id>/` (challenge.json + drawing.png)
  - private: `~/.cadrecover/runtime/private/<id>/` (0700: private.json 0600, s0.step, drawing.svg)
  - SQLite row and `challenge.created` event via `storage/db.py`
- [x] Critical features declared per family and published: `hole_1..4` and `slot` (if present), with size and position tolerance of 0.1 mm

**Done-when evidence:**
- `~/.cadrecover/envs/services/bin/cadrecover challenge new --family plate --seed 12345`
  - produced `ch_51b40eea12677918` in **43 s**, 1 attempt
  - lint `passed: true, score 1.0, errors 0, warnings 0`
  - coverage `ok: true, ledger_requirements 9, missing_required [], unplaced []`
- **Human check:** opened the published `drawing.png`. 130 × 51 × 14 plate, `4× ⌀6 THRU`, 10 mm edge offsets, slot 27.5 × 9.5 with its position, title "Mounting plate / LEGACY-1987-2345". Readable.
- Tests: `make test` → services **16 passed**, cad **4 passed** (self-test over 25 seeds; 4 holes + slot measured; an extra hole and moved holes are caught), drawing **2 passed** (coverage ok on a slotted plate; a missing required value is rejected).

**Not done / gaps:**
- **Hidden edit sets are not generated yet.** `PrivateChallenge.sets` only has s0. The discriminative edit sampler is a Phase 3 item.
- **draftwright rounds labels to 0.1 mm:** a 4.75 radius shows as `R4.8`, and 51.25 as `51.2`. Harmless today, because the slot width 9.5 is dimensioned exactly and tolerances are 0.1, but revisit if tolerances tighten. Options: 1 mm steps for derived values, or label precision 2.
- **The scan-look PNG is 3.3 MB** (noise defeats compression); the clean one is 142 KB. Fine for local use; shrink before serving at scale.
- **Generation takes ~43 s per challenge**, mostly draftwright plus worker start-up. Fine for 180 s rounds; pre-generate a pool if needed.
- **No sandboxing yet:** the CAD worker only builds *our* references. Miner code must wait for the phase 3 sandbox.
- Only the plate family exists. Flange, chuck and chamber are phase 7.

**Decisions:**
- **Only the PNG is public.** draftwright's SVG stays private, since its geometry is machine-readable.
- **Coverage rule:** if a drawing misses a required value, the part is resampled with the next seed and a `challenge.drawing_rejected` event is logged.
- **Opaque ids:** `ch_` + 16 random hex characters, unrelated to the seed.
- **CLI output** shows public facts and file paths only, never values.
- **Development challenges are retired** whenever their seed or values are exposed: `ch_51b40eea12677918` and `ch_df01e47027a76f04` (fixture).

**Interfaces changed:** none beyond v0.1.0.
**Blockers:** none.

---

## Phase 3: Evaluator and sandbox

**Status:** done (2026-10-29) · **Done when:** `cadrecover score my_part.py --task <id>` prints a correct score breakdown.

- [x] **Sandboxed worker** (`execution/sandbox.py`, `images/cad-worker/Dockerfile` + `sandbox_runner.py`):
  - image `cadrecover-sandbox:build123d-0.13.0` (1.81 GB)
  - **one fresh container per parameter set**
  - `--network none --read-only --tmpfs /tmp`, 1 GB memory / no swap, 1 CPU, 64 PIDs, `--cap-drop ALL`, `no-new-privileges`, uid 1000, 60 s limit plus a host-side kill
  - only the source and overrides are mounted (read-only), plus an empty `/out`
  - the runner is standalone (build123d only). AST allowlist: `build123d, math, typing, dataclasses`; it forbids `eval/exec/open/__import__/…` and dunder attributes
- [x] **Scoring at every parameter set** (`evaluation/checks.py`, `evaluation/evaluator.py` in the CAD env as a separate process that sees STEP files only, never code; `evaluation/score.py` orchestrates):
  - V (one valid solid with finite, positive volume)
  - C (holes and slot present and placed within 0.1 mm)
  - G (IoU against the reference at the same values)
  - D (fraction of dimensions within tolerance)
  - Q from `protocol.task_quality`
- [x] **Discriminative edit sampler** (`challenges/edits.py`, `cad_worker edits`): shift > 5 × 0.1 mm and self-IoU < 0.85, both logged per edit in the private record (`max_feature_shift_mm`, `reference_self_iou`). The pipeline now writes s1–s3 references.
- [x] STEP from the sandbox, GLB per set (reference + candidate) via `--glb-dir` (rounds write to `runtime/runs/<run>/uid<N>/`). Per-set measurements and failed checks with world-space locations are stored in `evaluation_sets`.
- [x] **Self-test reproduces exactly on real solids** (`tests/cad/test_evaluator.py`, plain and slotted plates): **100 · 75 · 25 · 0**

**Done-when evidence:**
- On fresh challenge `ch_b0e73f6b786699d9`, `cadrecover score <file> --task <id>` for 5 sources (from `miner/templates.py`):
  - **honest 100**
  - **constant 25**: holes off by 12–21 mm at each edit
  - **proportional 25**: IoU **0.99** at every edit, yet C = 0 (holes off by 2–4 mm)
  - **wrong_holes 0**: size check
  - **crash 0**: `invalid_source: forbidden import: socket`; failure class `miner`
- Edits: shifts of 17.5 / 21.5 / 12.5 mm, self-IoU 0.719 / 0.759 / 0.503.
- Tests: cad **18 passed**; services sandbox tests **4 passed** (build, forbidden import, timeout, `BLOCKED` network).

**Not done / gaps:**
- **Containers are not hostile-grade isolation** (shared kernel). Mainnet needs disposable worker VMs.
- **~2–3 s per container × 4 sets + ~5 s of evaluation ≈ 15–20 s per submission, run sequentially.** Parallelise (cap 2–3 workers) before more miners.
- **`offset()` assumes through-features run along Z.** True for plate, flange and chuck; the chamber's ports need per-feature axes (Phase 7).
- GLBs are written but not yet served. That's Phase 8/9.

**Decisions:**
- **Protocol 0.2.0:** `build_part(overrides)` gets `{}` at s₀ and only the changed keys at edits. Passing all values would let a template score without reading the drawing (found while building this phase).
- **Evaluator fix (found in Phase 5's rounds):** critical positions are compared *across* the through-axis. A 1 mm thickness misread used to move the measured hole centres in Z and zero whole sets. It now costs only G and D. Regression test: `test_misread_thickness_costs_geometry_not_critical_features`. Confirmed live in round `run_dc8b4cfb6d`: mock-noisy's thickness misread scored 93.6 (sets 91 / 91 / 100 / 91).
- **Sandbox infrastructure failures** (Docker or image missing, evaluator crash) are classed as `validator_outage` and excluded for everyone. Miner code failures are class `miner` and score 0.

**Interfaces changed:** protocol 0.1.0 → **0.2.0**: `ParameterSet.overrides`; `PublicChallenge.entry_point` text (logged in `shared.md`).
**Blockers:** none.

---

## Phase 7: Families, audits, robustness

**Status:** done (flange and wafer chuck; chamber remains uncommitted stretch work) · **Done when:** diagnostic miners earn about 0, an honest audit passes, and a swapped engine fails.

- [x] Flange family (passes its reference self-test first): `tests/cad/test_flange_evaluator.py` on plain 6-bolt, hubbed 4-bolt, hubbed 8-bolt → 100 / 75 / 25 / 0 (plus proportional bolt circle 25, wrong bore 0, wrong bolt count 0)
- [x] Wafer chuck *(stretch)*: reference, drawings, discriminative edits, diagnostic templates and real-solid 100/75/25/0 self-test; see prerequisite verification below
- [ ] Multi-port vacuum chamber *(stretch, existing work preserved uncommitted; full live done-when not proven)*
- [~] Held-out or feature-composed family against template solvers (REVIEW #3): **decision recorded, not solved** (see Decisions)
- [x] Auditor: committed engine image → hidden tasks → compare → zero on failure (`audit/auditor.py`, `cadrecover auditor run`)
- [x] Audit pass rule defined and documented (REVIEW #5): mean audit Q over 3 fresh hidden tasks ≥ live mean Q − 10
- [x] Verification checklist run; attack-chart numbers recorded from measurements (below)

**Done-when evidence:**
- Honest audit: `auditor run --top 1` → 3 tasks Q 100.0 → `engine a6f5b5bba590 live 100.0 audit 100.0 -> PASS` (block 22448).
- Swapped engine: miner1 keeps serving mock-oracle live but commits the diag-constant image `sha256:3d4fd12e…` (block 25022) → `live 100.0 audit 25.0 -> FAIL (audit mean 25.0 < live 100.0 - 10)` (blocks 25035, 25944) → next round revokes miner1's weight on chain (read back at block 29321). Re-committing the honest image → PASS → `{2: 1.0}` read back at block 32749.
- Diagnostic miners earn 0: see the attack chart (gate run).

**Flange:** parameters outer_diameter, thickness, bore_diameter, bolt_circle_diameter, bolt_hole_diameter, optional hub_diameter + hub_height, structural bolt_count 4/6/8 (never edited, never published: miners count holes on the drawing). Critical features: bore + every bolt hole (0.1 mm). Edits: outer diameter ±15–40 %, bolt circle resampled independently (≥ 4 mm move) so "scale holes with the disc" and "ignore the edit" both fail. 10 live challenges + 20 seeds passed coverage first try; `cadrecover score` on two tasks: honest 100, constant 25, wrong_holes 0, proportional 25.

**Verification checklist (PRD §Verification):**

| Check | Evidence |
| --- | --- |
| Reference vs itself passes every metric and edit | `test_correct_model_scores_100` (plate plain/slotted; flange ×3) |
| Wrong hole size / missing / moved / wrong units / mirrored fail the right check | `test_wrong_hole_size_scores_0`, `test_missing_hole_fails_critical`, `test_moved_hole_fails_critical` (1 mm = 10× tol → `hole_1.position`), `test_wrong_units_fails` (inch model → Q 0); mirrored: plate and flange are mirror-symmetric, so `test_mirrored_part_…` asserts a mirrored model is NOT penalised; handedness matters only for asymmetric families (none yet) |
| Extra holes (superset of guesses) fail | new `extra_<kind>` critical check in `evaluation/checks.py`; `test_extra_hole_fails_critical` |
| Constant 25, one edit wrong 75 | `test_constant_model_scores_25`, `test_one_edit_wrong_scores_75` (both families) |
| Accepted edits move a feature > 5× tol, self-IoU < 0.85 | `test_edits_are_discriminative` (both families) |
| Empty, crashing, malformed output → 0 | sandbox `test_empty_or_malformed_output_does_not_build` (empty, syntax error, not a solid, no build_part), `test_forbidden_import_…`, `test_runaway_code_times_out`, `test_missing_solid_is_invalid` |
| Fresh unseen seeds across demo families | plate: every live round; flange: 10 challenges + seeds 0–19 |
| Tampered / wrong receiver / stale / replay / unsigned / oversized request / oversized source / unknown validator | `test_bad_requests_are_rejected[...]` (6 cases), `test_oversized_source_is_rejected`, `test_allowlist_blocks_unknown_validators`, `test_other_validator_cannot_read_someone_elses_job` |
| Duplicate assignment | idempotent `job_id` (`test_signed_job_round_trip…` retry runs the model once); DB `UNIQUE(run_id, miner_hotkey)` |
| Timeout / no response / CAD failure / validator outage distinct | round outcomes `timeout` / `failed: dispatch` / sandbox `timeout|invalid_source|exception` / `failure_class=validator_outage` (excluded, not zeroed: `test_validator_outage_is_excluded_not_zeroed`). **Killed worker (OOM) not tested.** |
| Restart duplicates nothing; SSE reconnect rebuilds the same state | miner idempotency + per-run job ids; API `test_api.py` SSE resume tests. **Validator restart mid-round not tested.** |
| Weight readback matches netuid, validator, miners | `_set_weights` → `matches()` on the validator's row; live blocks 15596, 29321, 32749 |
| Honest audit passes, swapped fails | above |

**Attack chart (measured, gate run):** fresh localnet, 3 rounds (`make demo` gate run + 1), plate family, mock honest miners

| Miner | Type | Mean Q (n=3) | Share of weight (on chain, block 3686) |
| --- | --- | --- | --- |
| mock-oracle (uid 2) | Honest mock | 100.0 | 0.50 |
| mock-noisy (uid 3) | Honest mock (misreads sometimes) | 100.0 this run; 0-100 per round in earlier sessions | 0.50 |
| diag-constant (uid 4) | Diagnostic | 25.0 (expected 25) | 0 (below floor) |
| diag-wrong-holes (uid 5) | Diagnostic | 0.0 (expected 0) | 0 |
| diag-crash (uid 6) | Diagnostic | 0.0 | 0 |

Swapped engine (miner serves oracle, commits the constant engine): audit 25 vs live 100 -> FAIL -> weight revoked on chain. The real strategies (claude-vision) are not measured yet: they wait for the API key.

**Not done / gaps:**
- Vacuum chamber remains uncommitted stretch work; the live hidden-challenge/sandbox/diagnostic/audit done-when has not been run for it.
- Template solvers (REVIEW #3) remain an **open risk**: see Decisions.
- Flange coverage uses a ledger waiver for a draftwright false negative (`holes:bore.*`, `holes:location.*`, `bosses:boss_height.length`): the dimensions are drawn and still enforced through `required_labels`; waived entries are reported in `coverage.waived`. Plate is unaffected.
- Flange: groove, separate bolt-circle and hub-height measurements not built (IoU covers hub height).
- Audits take 3–10 min (3 tasks × sandbox at 1 CPU).
- Mock engines get the task's private record mounted (only with `CADRECOVER_DEV_ORACLE=1`); real engines never do. The audit story is only fully meaningful with a real engine (claude-vision) + a fixed model endpoint for audits (PRD option A).

**Decisions:**
- Audit pass rule (REVIEW #5): one-sided, mean over 3 fresh hidden tasks ≥ live mean − 10. Better-than-live is not hiding anything; worse means live answers came from elsewhere. Missing image or no commitment = fail; validator outage = inconclusive (no verdict).
- A failed audit zeroes the hotkey until a clean audit; if it still holds on-chain weight and nobody qualifies, the round submits a self-weight to revoke it (B).
- Critical check now rejects extra critical features (stricter for every family; never weakens).
- **Held-out family (REVIEW #3):** the validator is open source, so a family "held out" in code is not secret, and a fixed family can always be template-solved. The real fix is feature-composed generation (random combinations of holes, slots, bores, bosses, pockets on varied bodies) or a closed generator run by the subnet owner. Not built in the hackathon. Mitigations today: two families, flange has no public practice fixture, fresh seeds, discriminative hidden edits, and engine audits on fresh tasks. Said plainly in the pitch.

**Interfaces changed:** none in `protocol/`. `checks.critical` adds `extra_<kind>` failures.
**Blockers:** none.

---

## Stage 2 prerequisite: wafer chuck (2026-10-30)

**Status:** done. Existing wafer chuck work is isolated from the vacuum-chamber and frontend work in a wafer-only commit on `a/phase-12-wafer-chuck`.

- [x] Pure deterministic wafer-chuck specification, CAD geometry, pipeline/CAD/evaluator registration, miner templates and CLI family registration.
- [x] Real-solid self-test reproduces **100 / 75 / 25 / 0** for one vacuum ring plus mounting holes, two vacuum rings, and two rings plus mounting holes. Evidence: `tests/cad/test_wafer_chuck_evaluator.py::test_correct_model_scores_100`, `test_one_edit_wrong_scores_75`, `test_constant_model_scores_25`, `test_wrong_hole_size_scores_0` all passed for every parametrized variant in the full CAD suite below. Proportional-pattern and wrong-count diagnostics also pass their expected 25/0 assertions.
- [x] Drawing coverage tests enforce each pattern's count, diameter and bolt-circle diameter; missing dimensions fail; only the existing disc-height ledger false negative is waived, while the thickness label remains required.
- [x] Three full suites run **separately and sequentially in WSL**, without weakening checks or tests:
  - `~/.cadrecover/envs/services/bin/python -m pytest tests/services -q` -> **177 passed, 1 warning in 61.69s** (FastAPI/httpx deprecation).
  - `~/.cadrecover/envs/cad/bin/python -m pytest tests/cad -q` -> **144 passed, 1 skipped in 402.76s**. The skip is the missing-second-ring test on a single-ring wafer variant; the two-ring cases run and pass.
  - `~/.cadrecover/envs/drawing/bin/python -m pytest tests/drawing -q` -> **11 passed, 1 warning in 526.98s**.

**Decisions:** hole-circle diameters are independent parameters rather than fixed fractions of plate diameter; structural ring counts are read from the drawing and never edited. This makes proportional-template diagnostics fail hidden edits and preserves the discriminative rules. No protocol shape changes. C-owned existing wafer template/strategy/CLI changes are included with the ownership request recorded in `notes/shared.md` by B.

**Not done / gaps:** vacuum-chamber code, axis-measurement changes, its registrations/templates/tests and unrelated frontend work remain untouched and uncommitted. The full live chamber done-when has not been demonstrated; its five-port drawing emits draftwright ScaleCompletenessWarning: structurally unreadable (annotation_ink_overlap, annotation_overlap), so it is explicitly excluded from this prerequisite commit. These counts record the prerequisite baseline; Stage 2 service changes made concurrently require their own final suite run. `git pull` was attempted by B at session start and reported that the current branch had no upstream; no remote changes were applied.

---

## Session log (newest first)

| Date | Branch | What changed | Tests run | Next |
| --- | --- | --- | --- | --- |
| 2026-10-30 | a/phase-12-wafer-chuck | Isolated existing wafer family and miner integration; preserved chamber/frontend WIP | services 177 passed; cad 144 passed, 1 skipped; drawing 11 passed, 1 warning | Stage 2 hill runner may cycle plate/flange/wafer_chuck; chamber remains stretch |
| 2026-10-29 | b/phase-6-chain | Flange family, engine images + auditor, pass rule, extra-feature check, checklist tests | cad 61, services 131+, drawing 5 | Feature-composed generator; wafer chuck (stretch) |
| 2026-10-29 | a/phase-3-evaluator (+ fix on c/phase-4-miner) | Protocol 0.2.0, edit sampler, sandbox image + runner, evaluator, `cadrecover score`; through-axis position fix | cad 18, services sandbox 4 | Phase 7: flange family, auditor, held-out family |
| 2026-10-29 | a/phase-2-plate | Plate family, measurement, CAD/drawing workers, pipeline, CLI `challenge new/show`, fixture | services 16, cad 4, drawing 2: all passed | Phase 3: sandboxed rebuilds, discriminative edit sampler, IoU/D checks, the 100/75/25/0 self-test on real solids |
| 2026-10-29 | a/phase-0-protocol | Protocol schemas + contract tests | 10 passed | Phase 2 |
