# Review of PRD v2

Reviewed 2026-10-29. Overall rating: **about 8/10**. The plan is honest and well gated. Fix items 1–3 before writing code.

## Fix before building

### 1. ✅ Resolved in PRD v2.1: the scoring formula paid the cheat the pitch is about

**Resolution:**
- Every parameter set (the drawing's values plus 3 hidden edits) is scored for geometry and dimensions, averaged equally.
- A missing or misplaced critical feature zeroes that set.
- Hidden edits must move a critical feature by more than 5× tolerance and keep the reference's self-overlap below 0.85.
- A constant model now tops out at 25 against a floor of 50. The PRD's worked table shows 100, 75, 25 and 0.

**Original finding:** `Q = 100·V·(0.50G + 0.20D + 0.30E)` weighted editability at only 30%. A hard-coded model that ignores parameters still earns the full G and D at the drawing's own size, so it scores about **70**. The PRD's own checklist says it "scores well on geometry". If the quality floor is below 70, it gets paid.

- **Fix:** score G and D at *every* parameter set (the drawing's values plus each hidden edit) and average them. A constant model then fails two-thirds of the geometry checks too.
- **Alternative:** make E a multiplier, e.g. `Q = 100·V·(0.7G + 0.3D)·E`.

### 2. The market section misses the direct competitor

The PRD lists Backflip as "text to 3D print". Backflip now ships **2D Drawing to CAD**: parametric models with editable feature trees, live in Autodesk Fusion ([DEVELOP3D](https://develop3d.com/cad/backflip-converse-2d-engineering-drawings-directly-into-cad/)).

So these lines need rewriting, because they're easy to attack:
- "nobody sells verified drawing-to-CAD at scale"
- the judge answer "isn't it already solved?"

**Suggested positioning:** "Backflip and others *claim* editable output; nobody publishes verified results. CADRecover's validator is the public, measured benchmark, and the model is open."

### 3. Fresh seeds don't stop overfitting to a family

A new seed changes a part's dimensions, not its kind. A miner can hand-write one template solver per family: read the dimensions from the drawing, fill in a script. That wins every round without solving drawing-to-CAD.

**Fix:**
- Hold out at least one family that miners never see during development.
- Generate parts by combining features, not only from fixed families.
- Give a share of the score to the held-out set.

## Tighten

4. **The schedule doesn't add up.** The storage row says "3-day build", the plan has 11 phases, and about 11 days remain. Treat the wafer chuck and the vacuum chamber as stretch goals from the start; the flange is already a convincing hard case.
5. **Audits of LLM-based miners won't reproduce exactly.** Define the pass rule, e.g. a rerun must score within 10 points on 3 hidden tasks. Otherwise "Audit ✓" is an unsupported claim.
6. **draftwright is AGPL.** Fine on the validator; keep it out of anything shipped to customers (the on-prem engine).

## Small things

- The two `[embedded content: …]` diagrams didn't carry over into PRD.md.
- `client.identity.commitment(...)` isn't confirmed in v11. These other SDK names do match bittensor 11.3: `ServeAxon`, `SetWeights`, `http_auth`, `RegisterSubnet`, `BurnedRegister`, `calls.Commitments`.
- [TensorFork](https://github.com/soumyacodes007/tensorfork) can test weight-setting and commit-reveal against real mainnet chain rules before testnet.
