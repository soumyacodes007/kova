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

**Status:** not started · **Done when:** `cadrecover score my_part.py --task <id>` prints a correct score breakdown.

- [ ] Sandboxed worker: no network, resource limits, a fresh container per build
- [ ] Scoring at every parameter set (s₀ + 3 hidden edits): V_s, C_s (critical features), G_s (solid IoU), D_s (dimensions); Q = mean
- [ ] Discriminative edit sampler: a critical feature moves more than 5× tolerance, reference self-IoU below 0.85; redraw otherwise; log both numbers
- [ ] STEP and GLB export; per-set measurements and failed-check locations stored
- [ ] **Self-test reproduces exactly: reference 100 · one-edit-wrong 75 · constant 25 · wrong hole 0**

**Done-when evidence:**
**Done:**
**Not done / gaps:**
**Decisions:**
**Interfaces changed:**
**Blockers:**

---

## Phase 7: Families, audits, robustness

**Status:** not started · **Done when:** diagnostic miners earn about 0, an honest audit passes, and a swapped engine fails.

- [ ] Flange family (passes its reference self-test first)
- [ ] Wafer chuck *(stretch)*
- [ ] Multi-port vacuum chamber *(stretch)*
- [ ] Held-out or feature-composed family against template solvers (REVIEW #3)
- [ ] Auditor: pull the committed engine image (needs B's Phase 6 commitments), run it on a hidden task, compare quality, zero the weight on failure
- [ ] Audit pass rule defined and documented (REVIEW #5)
- [ ] Verification checklist run; attack-chart numbers recorded from measurements

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
| 2026-10-29 | a/phase-2-plate | Plate family, measurement, CAD/drawing workers, pipeline, CLI `challenge new/show`, fixture | services 16, cad 4, drawing 2: all passed | Phase 3: sandboxed rebuilds, discriminative edit sampler, IoU/D checks, the 100/75/25/0 self-test on real solids |
| 2026-10-29 | a/phase-0-protocol | Protocol schemas + contract tests | 10 passed | Phase 2 |
