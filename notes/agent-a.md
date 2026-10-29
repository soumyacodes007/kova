# Agent A: mechanism (phases 2, 3, 7)

Owns: `challenges/`, `evaluation/`, `execution/`, `audit/`, `images/cad-worker/`, `images/drawing-worker/`, and the `protocol/` challenge and evaluation schemas. Rules: [AGENTS.md](../AGENTS.md).

For each phase: tick items only with evidence (a command plus its result). List what's not done as clearly as what's done.

---

## Day 1: protocol drafts

**Status:** not started

- [ ] Public and private challenge record schemas in `protocol/`, with a version
- [ ] Evaluation record schema: per set (V, C, G, D, Q_s, failed checks with locations) plus the task total Q
- [ ] Handoff to C: one sample public challenge (PNG + JSON) in `fixtures/public/`, logged in `shared.md`

**Done:**
**Not done / gaps:**
**Decisions:**
**Interfaces changed:**
**Blockers:**

---

## Phase 2: Challenges and drawings

**Status:** not started · **Done when:** one command produces a hidden plate and a drawing a person can read.

- [ ] Plate family generator with a private seed, plus a reference self-test
- [ ] draftwright drawing (SVG → PNG), lint coverage check, scan look
- [ ] Public and private challenge records written to storage (through B's storage layer)
- [ ] Critical features declared per family and published in the public record

**Done-when evidence:**
**Done:**
**Not done / gaps:**
**Decisions:**
**Interfaces changed:**
**Blockers:**

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
