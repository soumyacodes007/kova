# CADRecover — Build Plan v2

Oct 29, 2026 · @Amlan

> **v2.1 (Oct 29):** scoring now runs at every parameter set (the drawing's values plus 3 hidden edits, averaged equally). A missing or misplaced critical feature zeroes that set, and hidden edits must be discriminative. A constant model now tops out at 25, and the floor starts at 50. See "Quality score per task".

## Review of the first plan

The first plan is technically strong and most of it stays. v2 keeps its engineering core and adds the pitch, a harder semiconductor demo family, on-chain engine audits, robustness pages, and a phase-by-phase build order with the backend first.

**What the first plan got right (kept as is)**

- **Current SDK reality.** Bittensor v11 has no Axon, Dendrite or Synapse; miners and validators build their own HTTP layer and sign requests with `bt.http_auth`. Endpoints are published with `bt.ServeAxon` and weights go through `bt.SetWeights`, which auto-selects plain or commit-reveal submission. Windows is unsupported natively, so services run in WSL. This replaces the older Synapse-based design discussed earlier.
- **Async jobs** (202 + polling) for minute-long agent runs, with idempotent assignment IDs so a retry never pays for a second model run.
- **Public vs private challenge records**, and retiring any challenge whose ground truth was revealed.
- **Never running miner code inside the validator process**, plus an honest note that containers are not hostile-grade isolation.
- **Scoring design:** validity gate, solid IoU plus two-way surface distance, independent feature checks, hidden edit tests, no speed bonus. v2.1 applies all of these at every parameter set.
- **Score to weights:** matched batches, minimum sample count, quality floor, explicit no-update state when nobody qualifies, identity = hotkey + registration, not UID.
- **Chain honesty:** commit, reveal and incentive shown as separate states, with receipts and readback.
- **UI truthfulness:** the viewer shows validator-rebuilt GLB files, one frozen shared transform, labeled replays, no invented events.
- **A real verification list** (wrong hole, missing hole, fixed holes, tampered payloads, restarts).

**What changes in v2**

| Area | First plan | v2 | Why |
| --- | --- | --- | --- |
| Part families | Plate, L-bracket, stepped block | Plate, flange, wafer chuck, multi-port vacuum chamber | Hard and visually striking; tells a semiconductor and aerospace story |
| Pitch and market | Not covered | Positioning, pricing evidence, BitMind and 404-GEN playbook | Judges score the problem and business, not only code |
| Robustness | Signed results only | Plus on-chain engine hash and background audits of top miners | Proves live answers come from a real, reusable engine |
| Miners | Up to 7 Claude strategies | 3 honest strategies + 2 labeled diagnostic miners | Fits model budget; diagnostic miners power the attack chart |
| Storage | Postgres | SQLite (WAL) on one host; Postgres only if already set up | Fewer moving parts for a 3-day build |
| Pages | Arena, runs, miners, network | Adds /security, /audits and a live status bar | Visible robustness for judges |
| Terminal | Process list | 3-pane tmux demo, Rich logs, one `make demo` | Proves the subnet is really running |
| VLM | Not specified | Used by miners and for failure explanations, never for scores | Keeps rewards objective |
| Schedule | 5 days, solo | 11 phases: backend end to end, then Next.js | No frontend work until the backend gate passes |

## Product, positioning and pitch

CADRecover is a Bittensor subnet that turns engineering drawings into editable, verified parametric CAD. Miners compete on fresh drawings generated from hidden parts; every model is checked against exact dimensions and parameter edits before it earns anything.

**One-line pitch**

> Aerospace, semiconductor and automotive companies keep parts in service for decades, and many exist only as old drawings. Redrawing one as 3D CAD costs $150–600 by hand. CADRecover pays miners to do it automatically, and every model is verified against the drawing's dimensions before it earns a cent.

**Positioning**

- **Not text-to-CAD.** That space is crowded (Autodesk Neural CAD, Zoo, AdamCAD). CADRecover starts from existing drawings and proves correctness.
- **Verified, not judged.** 404-GEN scores 3D output with a vision-language model in pairwise duels. CADRecover rewards only exact geometric checks, so a model that merely looks right earns nothing.
- **BitMind playbook.** Open competition builds the best model; companies use it through an API or a private (on-prem) deployment.
- **Privacy by design.** Miners only ever see synthetic drawings. The audited champion engine runs inside the customer's network, so confidential drawings never leave the building.

**Demo industry framing**

All demo parts come from semiconductor equipment: a mounting plate, a vacuum flange, a wafer chuck, and a multi-port vacuum chamber. Drawings carry a title block such as "Legacy part, 1987". Do not claim the subnet designs chips; it reconstructs mechanical parts.

**Lines for judges**

- "A VLM can't be fooled into paying for a wrong part here: every reward comes from measured geometry."
- "Answers stream in live, but every top miner's engine is registered on-chain and audited by re-running it ourselves."
- "The audited engine is the exact product a factory installs on-prem."

## Market evidence and business model

People already pay humans to convert drawings into CAD, and AI CAD is drawing heavy investment; nobody sells verified drawing-to-CAD at scale.

**Existing paid demand** ([CADmore](https://cadmore.com/blog/cad-conversion-cost), [Cad Crowd](https://www.cadcrowd.com/blog/?p=23090), [IndiaMART](https://m.indiamart.com/city/thane/cad-conversion.html))

| Service | Typical price |
| --- | --- |
| 2D drawing to full 3D solid with tolerancing | $200–600+ per part |
| Standard 2D-to-3D conversion (one provider) | $150–300 per part |
| Simple 2D cleanup of a scanned drawing | $40–200 per sheet |
| Legacy drawing conversion in India | about ₹2,000 per drawing |

Conversion firms also advertise turning US Department of Defense drawings into 3D models ([CADCAM.org](https://cadcam.org/3d-scanning/convert-2d-cad-drawing-to-3d)).

**Investment in AI CAD**

| Company | Funding or move | Focus |
| --- | --- | --- |
| [Autodesk Neural CAD](https://develop3d.com/cad/autodesks-ai-blueprint-for-cad/) | Foundation model in Fusion; generates editable B-rep and command history | Text, sketch, image to CAD |
| [Neural Concept](https://www.pulse.bot/saas/news/neural-concept-raises-100m-to-scale-ai-native-engineering-81df26ae-d340-4e56-9b5a-8b60430053d6/) | $100M Series C | AI-native engineering design |
| [Backflip](https://3dprint.com/315370/backflip-raises-30m-for-text-to-3d-print-software/) | $30M (a16z) | Text to 3D print |
| [Illoca](https://www.pulse.bot/ai/deals/illoca-raises-13m-seed-round-led-by-bessemer-venture-partners-9afde134-591e-42fa-a538-a7cca4231517/) | $13M seed | AI engineering engine |
| [AdamCAD](https://pasqualepillitteri.it/en/news/3372/adamcad-text-to-cad-ai-review-2026) | $4.1M (YC) | Text to parametric CAD |

Even Autodesk's system is described as a tool for bounded tasks with humans in control, not a magic button. The gap is trust: no one proves the output matches the drawing.

**Business model**

1. **Conversion bureaus first.** Firms that already redraw drawings use the champion engine to cut their cost per drawing. They have the customers and the backlog.
2. **Pay-per-drawing API** for small shops, with an AI-draft-plus-human-check workflow while accuracy matures.
3. **On-prem licence** of the audited engine for aerospace, defense and semiconductor manufacturers.
4. **Plugins** where engineers already work (FreeCAD, Onshape, SolidWorks), copying 404-GEN's Unity and Blender distribution.
5. Revenue funds token buybacks, as BitMind describes for its own business.

**Bittensor precedents**

- **BitMind (SN34):** adversarial competition improves detectors; sold through a paid API, an enterprise zero-retention API, and licensing deals with financial institutions ([docs](https://docs.bitmind.ai/llms-full.txt)).
- **404-GEN (SN17):** open-source solutions compound; Atlas adds usage-based enterprise pricing with fees flowing back to the network ([tao.media](https://www.tao.media/404-gen-sn17-introduces-atlas-to-bring-decentralized-3d-ai-into-enterprise-workflows/)). Monetization came late, a risk worth naming.
- **No subnet does engineering CAD.** 404-GEN makes meshes and Gaussian splats for games, not dimensionally exact parts.

## Mechanism: part families, scoring, incentives

The validator generates a hidden part, renders its drawing, and pays miners only for code that rebuilds the part correctly at the shown size and at hidden edited sizes.

**Difficulty ladder** (build in this order; add the next only after the previous passes its self-test)

| Order | Family | Key features | Edit rule given to miners | Role in demo |
| --- | --- | --- | --- | --- |
| 1 | Mounting plate | Outline, 4 holes, optional slot | Holes keep a 10 mm edge offset when width changes | Proves the loop; everyone solves it |
| 2 | Vacuum flange | Disc, center bore, bolt circle, groove | Bolt count fixed; holes stay on the bolt circle when its diameter changes | Clean semiconductor look |
| 3 | Wafer chuck | Round plate, vacuum-hole pattern, lift-pin holes | Pattern scales with plate diameter | Many small features |
| 4 | Multi-port vacuum chamber | Hollow body, 4–6 flanged ports, bolt circles per port | All ports update when port diameter changes | Hard case; most miners fail |

Avoid freeform surfaces (turbine blades, car bodies): drawings describe them poorly and checks get fuzzy. L-bracket and stepped block stay as optional extra families.

**Each challenge has two records**

- **Public:** opaque ID, drawing PNG, units (mm), coordinate frame, required parameter names, allowed ranges, edit rules, deadline, scoring version.
- **Private:** generator seed, reference solid, expected measurements, hidden edit values, reference results at those values. Never served to miners or the public artifact store until the round is retired.

**Miner contract**

```python
from build123d import Part

def build_part(params: dict[str, float]) -> Part:
    # Parameter names, units and frame come from the challenge.
    ...
```

**Quality score per task** (v2.1: every parameter set is scored the same way, so a model that ignores parameters can't win on overlap)

Each task has four parameter sets: the drawing's own values (s₀) plus three hidden edits (s₁–s₃). The miner's code is rebuilt and scored at every set against the reference rebuilt at the same values, and the sets are averaged equally:

```latex
Q_s = V_s \cdot C_s \cdot (0.7\,G_s + 0.3\,D_s)
\qquad
Q = 100 \cdot \tfrac{1}{4} \textstyle\sum_{s=0}^{3} Q_s
```

- V<sub>s</sub>, validity (0 or 1): at this set, the code runs within limits, returns one valid positive-volume solid, and uses the correct entry point.
- C<sub>s</sub>, critical features (0 or 1): every critical feature is present and placed within tolerance at this set. A missing or misplaced critical feature **zeroes the set**. One correct hole never compensates for a missing one.
- G<sub>s</sub>, geometry (0–1): solid IoU against the reference at this set. Two-way surface distance is recorded as a diagnostic only.
- D<sub>s</sub>, dimensions (0–1): the fraction of measured dimensions within published tolerance at this set: hole diameters, key lengths, bolt-circle diameters.

**Critical features** are fixed per family and published with the challenge. Examples: every hole's count, diameter and centre; the bolt circle; the bore; and each port's axis and bolt circle on the chamber. "Misplaced" means a feature's centre or axis is off by more than its positional tolerance.

**Hidden edits must be discriminative.** The validator draws edit values (within the published ranges) until each of s₁–s₃ satisfies both rules:

1. At least one critical feature moves by more than **5× its positional tolerance** compared with s₀.
2. The reference's overlap with itself across the edit, IoU(reference at s₀, reference at sₖ), is **below 0.85**.

Rule 1 means a model that ignores parameters leaves features misplaced at every hidden set, so C<sub>s</sub> = 0. Rule 2 means it can't hide behind a high overlap either.

**Worked scores** (four sets, so each set is worth 25 points)

| Candidate | s₀ (drawing) | s₁ | s₂ | s₃ | Q | Earns? (floor 50) |
| --- | --- | --- | --- | --- | --- | --- |
| Correct parametric model | 1.0 | 1.0 | 1.0 | 1.0 | **100** | Yes |
| Correct except one edit (a hole drifts at s₂) | 1.0 | 1.0 | 0 | 1.0 | **75** | Yes |
| Constant model (ignores parameters; exact at s₀) | 1.0 | 0 | 0 | 0 | **25** | No |
| Wrong hole size everywhere | 0 | 0 | 0 | 0 | **0** | No |

A constant model therefore tops out at 25. The quality floor starts at **50**, halfway between that ceiling and a model that is right at two or more sets. Recalibrate it from measured baseline and diagnostic-miner results before trusting rankings. Phase 3's self-test must reproduce this table exactly.

**From scores to weights**

- Every eligible miner gets the same family mix per batch; timeouts score 0; validator outages are excluded for everyone.
- Rolling mean over completed batches, with a minimum sample count before rewards.
- Weight = max(0, mean Q − quality floor), normalized. The floor starts at 50, which is above the constant-model ceiling of 25; recalibrate it from baseline results.
- Nobody above the floor means no new weights and an alert, never an invented winner.
- Identity is hotkey plus registration, so a recycled UID starts fresh.
- Ordinary Yuma, mechanism 0; no speed bonus, only a deadline.

**Attacks the mechanism must defeat**

| Attack | Defence |
| --- | --- |
| Crashing or empty code | Validity gate scores 0 |
| Hard-coded model that ignores parameters | Discriminative edits misplace its features at every hidden set; it tops out at 25, below the floor of 50 |
| Right shape, wrong hole size | The critical-feature check zeroes every set; it scores 0 |
| Copying another miner | Answers go privately to the validator; engine hash committed first |
| Memorizing past tasks | Fresh seed every round; revealed tasks retired |
| Human solving by hand | Background audits re-run the committed engine |
| Malicious code | No network, resource limits, separate worker, no secrets mounted |

## Architecture and protocol

CADRecover uses live query-response for the demo and adds on-chain engine commitments with background audits for robustness. Python owns truth and execution; Next.js only presents.

[embedded content: CADRecover architecture · 11 components — diagram not included in this copy]

Solid arrows carry live work each round; the dashed arrow is the audit path, where on-chain engine hashes tell the auditor which images to re-run.

**Two loops**

- **Live loop (every round):** validator creates a challenge, sends signed jobs to miners, miners return build123d source, the validator rebuilds and scores it, the arena updates.
- **Audit loop (background):** each miner commits a hash of its engine image on-chain at registration. Every N rounds the validator pulls the top miners' images, runs them on a hidden task with no network, and checks they reproduce similar quality. A failed audit zeroes the miner's weight.

This matches the 404-GEN idea of re-running winners' Docker images, without its CDN uploads, because CADRecover answers are small source files sent straight to the validator.

**Miner HTTP API** (FastAPI + httpx, every request signed with `bt.http_auth`)

| Method | Path | Purpose |
| --- | --- | --- |
| POST | /v1/jobs | Signed validator request; returns 202 + job\_id |
| GET | /v1/jobs/{job\_id} | Signed polling; status and result envelope |
| GET | /v1/health | Availability and protocol version |

The result envelope holds source text, its SHA-256, job ID, protocol version and entry point, signed by the miner hotkey. A signature proves who sent it, not that it is correct.

**Engine commitment and audits**

- Commitment = image digest + strategy version, written with the commitments pallet (`client.submit_call(bt.calls.Commitments.set_commitment(...))`; there is no intent for it in v11).
- Audits need a fixed model endpoint so the validator never needs miner API keys. Option A: serve an open-weight VLM behind one endpoint during audits. Option B: require open-weight models inside the image. For the hackathon, audit the deterministic baseline miner and one Claude miner using an operator-provided endpoint, and show the result as an "Audit ✓" badge.

**Where a VLM is used**

| Use | Allowed |
| --- | --- |
| Miners reading drawings and writing code | Yes, the main miner strategy |
| Plain-English failure explanations in the explorer | Yes |
| Tie-break between identical objective scores | Yes, tiny weight, rendered images only |
| Main score, dimension checks, edit tests | Never |

Never show raw miner text to a VLM judge: comments could carry injected instructions.

**Miner strategies for the demo**

1. Direct vision-to-CAD (fast baseline).
2. Extract dimensions into a structured record, then build.
3. Generate, render orthographic views, compare to the drawing, repair.
4. Diagnostic: constant-output model (ignores parameters), labeled and excluded from rankings.
5. Diagnostic: crash or forbidden-import code, labeled and excluded.

Record model ID, strategy version, duration and budget per job. Publish concrete events (draft created, build failed, repair attempted, submitted), not model reasoning.

## Validator, evaluation and sandbox

The validator never trusts a miner's claims: it rebuilds every submission itself, in a separate locked-down worker, and measures the result against the hidden reference.

**Challenge pipeline**

1. Sample a valid part from a family with a private seed; build the reference; reject invalid solids.
2. Export STEP to the drawing worker; draftwright renders multi-view, dimensioned SVG; rasterize to PNG.
3. Run draftwright's lint for annotation coverage; reject drawings missing a dimension the task needs.
4. Add scan look (slight blur, noise, rotation) for realism.
5. Draw three hidden edit sets within the published ranges, and redraw any that fails the discriminative rules (a critical feature moves more than 5× its tolerance; reference self-overlap below 0.85). Build reference solids at those values, and store all private artifacts outside the public root.

**Evaluation steps per submission**

1. Rebuild the miner code in a fresh container at the drawing's parameters.
2. Validity gate (V<sub>s</sub>): one finite, positive-volume, valid solid within time and memory limits.
3. Critical features (C<sub>s</sub>): measure holes (count, diameter, centre), bolt circles, bores and port axes from the solid's faces. Any critical feature missing or misplaced makes this set score 0.
4. Geometry and dimensions (G<sub>s</sub>, D<sub>s</sub>): solid IoU with the reference using CAD booleans; the fraction of key dimensions within tolerance; two-way surface distance for the diagnostics view.
5. Repeat steps 1–4 at each of the three hidden edit sets, in a fresh container each time, against the reference at the same values. Q is the equal-weight mean over all four sets.
6. Export STEP for download and GLB for the browser; store per-set measurements, failed checks with world-space location, timings and hashes.

agentcad (Apache 2.0) offers STEP export, a dimensional report with cylinder diameters, and an A/B comparison view; try it in a 2-hour spike for checks 3–4 before writing them from scratch ([PyPI](https://pypi.org/project/agentcad/0.5.0/)).

**Sandbox rules** (kept from the first plan)

- Separate Linux worker; no wallets, provider tokens, ground truth, host mounts or Docker socket inside.
- No network, non-root user, read-only root filesystem, temporary output dir, CPU, RAM, PID and output caps, dropped capabilities, hard wall-clock timeout.
- Never `exec` miner code inside the validator or API process; import returned geometry in a second constrained process.
- Cap concurrent rebuilds on the laptop so five miners cannot exhaust RAM.
- Call this a constrained hackathon environment, not hostile-grade isolation. Mainnet needs disposable worker machines or stronger isolation.

**Failure classes stored separately**

| Class | Example | Effect on miner |
| --- | --- | --- |
| Miner failure | Crash, timeout, invalid solid, wrong interface | Score 0 for that task |
| Validator outage | Worker died, CAD import bug | Task excluded for every miner |
| Audit failure | Committed engine cannot reproduce quality | Weight set to 0 until a clean audit |

## Bittensor v11 chain integration

Use the unified `bittensor` 11.x package (SDK, CLI and wallet in one), run it in WSL or Linux, and treat every chain action as an intent that is previewed, executed and read back ([migration guide](https://www.bittensor.com/docs/migration)).

**What v11 changes for this build**

| Need | v11 way |
| --- | --- |
| Miner/validator transport | Your own FastAPI server and httpx client; `bt.http_auth.sign` / `verify` for hotkey-signed requests |
| Publish miner endpoint | `bt.ServeAxon(netuid=..., ip=..., port=...)` |
| Discover miners | `client.subnets.metagraph(netuid)`; each neuron has `axon` as "ip:port" |
| Set weights | `bt.SetWeights(netuid=..., weights={uid: w}, version_key=...)`; commit-reveal chosen automatically; `version_key` defaults to 0 |
| Engine commitment | `client.submit_call(bt.calls.Commitments.set_commitment(...), wallet)`; read with `client.identity.commitment(...)` |
| Register subnet / neurons | `bt.RegisterSubnet()` waits for the assigned netuid; `bt.BurnedRegister(netuid=...)` |
| Preview anything | `client.plan(intent, wallet)` or `--dry-run` |
| Local testing | Local node; `MockSubtensor` no longer exists |

**Setup order (begin in Phase 1 so chain timing never blocks the demo)**

1. Create wallets: owner, validator, one per miner. Keep miners off the owner wallet.
2. Start a local node; then request testnet funds from the organizers.
3. Inspect costs, preview and register the subnet; record the assigned netuid.
4. Register the validator and miners; confirm validator permit.
5. Each miner serves its endpoint and commits its engine hash.
6. Make one successful weight submission and read it back.

**Read-only checks to run first**

```bash
btcli query --help
btcli tools
btcli query subnet-hyperparameters --network test --netuid NETUID --json
btcli query metagraph --network test --netuid NETUID --json
btcli query epoch-status --network test --netuid NETUID --json
```

**Rules kept from the first plan**

- Every environment names `local` or `test` explicitly; no mainnet in this build.
- A separate chain process owns the validator hotkey; the browser and miner code never see it.
- Persist proposed scores, submitted weights, result, block and readback; show commit, reveal and incentive as distinct states.
- One validator demonstrates the loop, not decentralized agreement. Say so if asked.
- Localhost endpoints work only for a same-machine demo; testnet peers need routable addresses.

## Terminal, CLI and demo setup

The terminal proves the subnet is really running; the browser carries the visual story. Both are on screen during the pitch.

**Processes (all under Docker Compose with restart policies)**

| Process | Job |
| --- | --- |
| Local subtensor | Blocks, registrations, weights |
| `cadrecover api` | Read API, operator actions, artifacts, SSE events |
| `cadrecover validator` | Challenges, job dispatch, collection, aggregation |
| `cadrecover miner --strategy ...` | One process per miner, own wallet, port and config |
| `cadrecover worker` | Sandboxed rebuilds, STEP and GLB export |
| `cadrecover chain` | Metagraph refresh, weight batches, receipts, commitments |
| `cadrecover auditor` | Pulls committed engine images and runs audits |
| `pnpm dev` | Next.js frontend |

**CLI for miners and judges** (to implement)

```
cadrecover doctor              # env, wallet, Docker, build123d, chain reachability
cadrecover task sample         # download a practice drawing + public spec
cadrecover score my_part.py    # run the same checks locally before mining
cadrecover miner run           # start a miner
cadrecover validator run       # start the validator
cadrecover status              # recent scores and rejection reasons
make demo                      # localnet + validator + 5 miners + dashboard
```

**Pitch layout:** browser arena on 70% of the screen, a 3-pane tmux terminal on 30% (validator, honest miner, diagnostic miner), logs styled with Rich.

**Validator pane example**

```
[round 42] task: vacuum chamber (hard) · seed hidden · deadline 180 s
[round 42] 5 miners queried · 4 responded · 1 timeout
  UID 7   valid · sets 4/4 · dims 18/18             Q 94
  UID 12  valid · s2: port 4 bolt circle rotated 15° → set zeroed   Q 71
  UID 3   crashed: forbidden import (diagnostic)   Q 0
[round 42] weights submitted · block 4,213,887 · commit-reveal pending
[audit]    UID 7 engine 9f3a…c21 re-run on hidden task · reproduced
```

Numbers above are illustrative of the format only; the live demo shows real values.

## Next.js app

The arena is the product demo; every other page exists to make the subnet look trustworthy. Build P0 first and stop adding pages if time slips.

**Pages**

| Priority | Route | Contents |
| --- | --- | --- |
| P0 | /arena/\[runId\] | Drawing left, large CAD viewport right, miner strip, parameter edits, evidence panel; LIVE or REPLAY label |
| P0 | Status bar (all pages) | Network, netuid, block height, validator heartbeat, round timer, miners responding |
| P0 | /leaderboard | Miners by mean Q, samples, dimension pass rate, edit pass rate, audit status, weight |
| P1 | /security | Attack chart: diagnostic miners (crash, constant output, wrong holes) earn about 0, honest miners earn |
| P1 | /audits | Engine hash, task, result, block, per miner |
| P1 | /runs and /runs/\[id\] | Past rounds: drawing, revealed reference, every submission with its checks |
| P2 | /miners/\[hotkey\] | History, per-family scores, failure types, strategy version |
| P2 | /network | Registered vs responding miners, weights proposed, commit and reveal state, receipts |
| P2 | /stats | Quality over time, rejection breakdown by stage, heatmap by family, baseline comparison |
| P2 | /try | Upload a drawing or pick a sample; champion model; STEP download; savings estimate |
| P2 | /docs and API page | Miner quickstart, mechanism, public read endpoints |

Design references: the [SN1 Apex dashboard](https://www.macrocosmos.ai/sn1/dashboard) (miner arena, task view, leaderboard), SN9's per-step leaderboard and validator board ([Macrocosmos](https://macrocosmosai.substack.com/p/more-oversight-better-visibility)), TrajectoryRL's rejection breakdown and scenario heatmap ([PyPI](https://pypi.org/project/trajrl/2.1.0/)), Distil's public API ([GitHub](https://github.com/unarbos/distil)).

**Arena behaviours (all driven by real events)**

- New drawing fades in when the challenge is created; countdown to deadline.
- Live event feed over SSE: submitted, build failed, checks passed.
- Models appear from the validator's rebuilt GLB, never a frontend-made model.
- Reference ghost overlay and section plane reveal missing or extra geometry, such as the chamber's hollow interior.
- Click a failed check to fly the camera to its recorded location; failed features glow red.
- Parameter slider queues backend rebuilds on release; models swap only when results arrive.
- Score bars animate only after evaluation completes; "Audit ✓" badge on audited miners.
- Presentation mode: one key for full-screen arena with large type.

**Robustness signals**

- Every weight set, commitment and audit shows its block number.
- "Reproduce this score" shows the task ID and command, e.g. `cadrecover score --task <id> --uid <uid>`.
- Versioned benchmark label: scoring version, families, task count.
- Judge edits are stored separately and never change official scores.

**Viewer choice**

React Three Fiber with GLB is the primary viewer, as the first plan said. Give three-cad-viewer one 4-hour spike only if click-to-measure becomes essential; its `updatePart` writes new geometry into existing GPU buffers, which suits the slider ([GitHub](https://github.com/bernhard-42/three-cad-viewer)). Browser measurements are display aids; the evaluator's numbers are authoritative.

**Look:** light drawing sheet beside a charcoal model workspace, one cyan accent for selection, red only for failures, monospace numbers with units, orthographic default camera, one main WebGL canvas plus static thumbnails.

## Stack, environments and repo structure

Three locked Python environments, one Next.js app, SQLite, and everything in Docker Compose. Lock exact versions in Phase 1; package availability is not proof of compatibility.

| Layer | Choice | Note |
| --- | --- | --- |
| Chain, API, miners, validator | Python 3.12, bittensor 11.x, FastAPI, httpx, Pydantic, uv | v11 is Linux/macOS only; use WSL on Windows |
| Drawing worker | Python 3.12, draftwright, the build123d version it requires | Own environment; the first plan found draftwright pins build123d below 0.11 on Python under 3.13; re-check on install. draftwright is AGPL |
| CAD execution and grading | Python 3.12, one exact build123d/OCP pair | Same engine for references and submissions |
| Storage | SQLite in WAL mode + local artifact folder | Postgres only if already comfortable |
| Live events | Server-sent events with event IDs for resume | FastAPI SSE |
| Frontend | Next.js App Router, TypeScript, Tailwind, shadcn/ui, Recharts | Types generated from the FastAPI OpenAPI schema |
| 3D | React Three Fiber 9 + Drei + Three.js, GLB from build123d `export_gltf(binary=True)` | Avoid R3F 10 alpha |
| Dev tools | OCP Viewer for inspection; PyVista or trimesh for heatmap images later | Not on the critical path |
| Terminal | Rich, tmux, Make | Demo polish |

**Repository**

```
cadrecover/
  apps/web/                 Next.js app
  src/cadrecover/
    protocol/               public/private schemas, versions
    challenges/             families, generator, drawing adapter, scan look
    miner/                  job server, provider adapter, strategies
    validator/              scheduler, collector, aggregation
    evaluation/             validity, geometry, features, edit tests
    execution/              sandboxed worker controller
    audit/                  engine pull, audit runs, results
    chain/                  metagraph, registration, commitments, weights
    api/                    read routes, operator routes, SSE
    storage/                SQLite models, artifact access
    cli.py
  images/cad-worker/        locked CAD execution image
  images/drawing-worker/    locked draftwright image
  tests/                    mechanism, protocol, chain
  fixtures/public/          labeled frontend fixtures
  docs/                     MINER.md, VALIDATOR.md, MECHANISM.md
  compose.yaml  Makefile  uv.lock  pnpm-lock.yaml
```

Private ground truth and secrets live in runtime folders outside the repo's public paths. Miner processes never inherit the developer's full filesystem access.

## Build phases

Eleven phases, in order: phases 1–8 build and prove the whole subnet in the terminal, and only then phases 9–11 build the Next.js app. Each phase ends with a done-when check; the next phase starts only after it passes.

[embedded content: Build roadmap · 3 phases, 4 gates — diagram not included in this copy]

Each band groups its phases; the gate between the rows is the only way into frontend work.

### Backend (phases 1–8)

**Phase 1: Setup and environments**

- [ ] WSL or Linux, uv, Python 3.12; three locked environments (services, drawing worker, CAD worker)
- [ ] Docker Compose skeleton; SQLite schema for runs, assignments, submissions, evaluations, events, weight batches, receipts, audits
- [ ] Local subtensor running; wallets for owner, validator and each miner

Done when: every environment imports its libraries and the local chain produces blocks.

**Phase 2: Challenges and drawings**

- [ ] Plate family generator with private seed and reference self-test
- [ ] draftwright drawing (SVG to PNG), lint coverage check, scan look
- [ ] Public and private challenge records written to storage

Done when: one command produces a hidden plate and a drawing a person can read.

**Phase 3: Evaluator and sandbox**

- [ ] Sandboxed worker: no network, resource limits, fresh container per build
- [ ] Validity gate, solid IoU, hole and dimension checks, hidden edit tests
- [ ] STEP and GLB export; measurements and failed-check locations stored
- [ ] Self-test reproduces the worked-score table exactly: reference 100, one-edit-wrong 75, constant output 25, wrong hole 0
- [ ] Edit sampler rejects non-discriminative edits, and logs the feature shift and the reference self-overlap for each accepted edit

Done when: `cadrecover score my_part.py --task <id>` prints a correct score breakdown.

**Phase 4: Miner and signed jobs**

- [ ] FastAPI miner: POST /v1/jobs (202), GET /v1/jobs/{id}, GET /v1/health; `bt.http_auth` sign and verify; idempotent assignments
- [ ] Claude strategy 1 (direct vision-to-CAD), then strategies 2 and 3
- [ ] Diagnostic miners: constant output, wrong holes, crash

Done when: a signed job returns build123d code that scores above the floor.

**Phase 5: Validator rounds and storage**

- [ ] Scheduler: create challenge, discover miners from the metagraph, dispatch, poll, enforce deadline
- [ ] Rebuild and evaluate every submission; matched batches; rolling aggregation; quality floor
- [ ] Event log entry for every step (feeds SSE later)

Done when: a full round with 5 miners completes and leaderboard numbers sit in SQLite.

**Phase 6: Chain integration**

- [ ] Register subnet and neurons on the local node; miners publish endpoints with `bt.ServeAxon`; validator permit confirmed
- [ ] Chain process: `bt.SetWeights` through plan, execute, readback; receipts and commit/reveal state stored
- [ ] Engine commitments with `set_commitment`; read back per miner
- [ ] Start testnet funding and registration in parallel

Done when: Phase 5 scores land on-chain as weights and read back correctly.

**Phase 7: Families, audits, robustness**

- [ ] Flange, then wafer chuck, then vacuum chamber; each passes its reference self-test first
- [ ] Auditor: pull committed engine image, run it on a hidden task, compare quality, zero weight on failure
- [ ] Run the verification checklist; record the attack-chart numbers

Done when: diagnostic miners earn about 0, an honest audit passes and a swapped engine fails.

**Phase 8: API, CLI and terminal demo**

- [ ] FastAPI read API and SSE with resumable event IDs; TypeScript types generated from OpenAPI
- [ ] CLI: doctor, task sample, score, miner run, validator run, status
- [ ] Rich logs, 3-pane tmux layout, `make demo` starts everything

Done when (backend gate): `make demo` runs a full round, a weight submission and an audit end to end, visible in the terminal alone.

### Frontend (phases 9–11)

**Phase 9: Arena on the real API**

- [ ] Next.js shell, status bar, React Three Fiber viewer loading validator GLBs
- [ ] /arena/\[runId\]: drawing, miner strip, live events, checks, ghost overlay, section view, failure focus
- [ ] Parameter slider: queue a rebuild on release, swap the model when the result arrives

Done when: a live round plays in the browser with no fixture data.

**Phase 10: Trust pages**

- [ ] /leaderboard, /security (attack chart), /audits, /runs/\[id\]
- [ ] Block numbers on every weight set, commitment and audit; reproduce-score command

Done when: a judge can trace any score to its checks and its chain receipt.

**Phase 11: Ship**

- [ ] Testnet run if registration is live; otherwise localnet with readback
- [ ] Optional: /stats, /try, /miners, three-cad-viewer spike
- [ ] README, MINER.md, MECHANISM.md; backup video of a real run; rehearse three times

Done when: one live run, one recorded run, a real chain receipt and a downloadable STEP.

**With three people:** A owns phases 2, 3 and 7; B owns 1, 5 and 6; C owns 4 and 8, then leads 9–11 once the backend gate passes.

**If time runs short, cut in this order:** wafer chuck, optional pages, testnet (keep localnet), audits (keep commitments). Never cut trustworthy scoring, one real weight cycle, or the arena.

## Verification and attack-proof plan

Before any demo, the scorer must reward the reference fully and punish every known bad model; these results also become the /security page.

**Mechanism checks**

- [ ] Reference compared with itself passes every metric and every allowed edit
- [ ] Wrong hole size, missing hole, moved hole, wrong units, mirrored part each fail the right check
- [ ] Constant-output model scores exactly 25 (full marks at the drawing's set, 0 at each hidden edit), below the floor of 50
- [ ] Model wrong at exactly one hidden edit scores 75
- [ ] Every accepted hidden edit moves a critical feature more than 5× its tolerance and keeps reference self-overlap below 0.85
- [ ] Empty, crashing or malformed output scores 0
- [ ] Fresh unseen seeds work across every family shown in the demo

**Protocol and chain checks**

- [ ] Tampered payload, wrong receiver, stale signature, replayed nonce, unregistered hotkey, duplicate assignment and oversized source are rejected
- [ ] Timeout, no response, killed worker, CAD import failure and validator outage produce distinct outcomes
- [ ] Restarting API or validator duplicates no jobs and no weight submissions; SSE reconnect rebuilds the same state
- [ ] Weight readback matches the intended netuid, validator and miner hotkeys, allowing for commit-reveal delay
- [ ] Audit of an honest engine passes; audit of a swapped engine fails

**Frontend checks**

- [ ] Real meshes, long generation times and 5 miner cards on the demo laptop
- [ ] No fixture data on live routes; replays labeled

**Attack chart for /security** (fill with measured results, not guesses)

| Miner | Type | Mean Q | Share of weight |
| --- | --- | --- | --- |
| Strategy 3: render-and-repair | Honest | measured | measured |
| Strategy 2: extract-then-build | Honest | measured | measured |
| Strategy 1: direct vision-to-CAD | Honest | measured | measured |
| Constant output | Diagnostic | measured (expected 25) | 0 (below floor) |
| Wrong holes | Diagnostic | measured (expected 0) | 0 |
| Crash / forbidden import | Diagnostic | 0 | 0 |

## Demo script and judge Q&A

The demo is three minutes; its climax is a judge changing a dimension and watching a wrong model break with a measured reason.

**Script**

1. **0:00 Problem (20 s).** Old drawings, $150–600 per part to redraw by hand, AI CAD booming but unverified.
2. **0:20 Terminal (20 s).** Miners registered with engine hashes; validator starts a round.
3. **0:40 Arena (60 s).** A vacuum chamber drawing appears; miners' models stream in; checks tick green or red.
4. **1:40 The edit (30 s).** A judge drags port diameter 40 → 63 mm. The champion rebuilds correctly; another model keeps old bolt holes and fails in red.
5. **2:10 Robustness (25 s).** /security: diagnostic miners earn about 0; audit badge on the champion; weights land on-chain with a block number.
6. **2:35 Business (25 s).** Conversion bureaus, pay-per-drawing API, on-prem licence; BitMind playbook.

Keep a recorded backup of a real run ready; switch without apologising if anything stalls.

**Likely judge questions**

| Question | Answer |
| --- | --- |
| Why does this need Bittensor? | Continuous open competition on fresh hidden parts keeps improving the engine; objective checks make rewards fair and unfakeable. |
| Isn't drawing-to-CAD already solved? | Research is active (Drawing2CAD, Drawing-Recode), but nothing verifies output against exact dimensions at scale. |
| Can miners cheat? | Validity gate, hidden edits, fresh seeds, private answers, engine commitments and audits; the /security page shows measured results. |
| Why not use a VLM judge like 404-GEN? | VLMs judge looks; a part must be right to 0.1 mm. VLMs help miners and explain failures, never set rewards. |
| Customers won't share drawings. | Miners only see synthetic drawings; the audited engine runs on-prem. |
| Do real drawings look like yours? | Not yet fully: scans, GD&T and assemblies come next as harder families. |
| How do you make money? | Conversion bureaus first, then API and on-prem licences; revenue buys back the token. |
| Is one validator decentralized? | No; this demonstrates the loop. Mainnet needs independent validators replaying the same checks. |

## Risks and roadmap

The biggest build risks are library version clashes and chain timing, so both are tackled in Phase 1.

| Risk | Likelihood | Fallback |
| --- | --- | --- |
| draftwright and build123d versions clash | Medium | Separate drawing image exchanging STEP; else build123d drafting helpers or a views-plus-dimension-table drawing |
| Testnet funds or registration late | Medium | Demo on localnet with real weights and readback; show testnet as in progress |
| Claude miners slow or rate-limited | Medium | Fewer concurrent miners; deterministic baseline miner; replay of a real earlier run |
| Vacuum chamber too hard to check reliably | Medium | Keep flange as the hard case; chamber as stretch |
| Live demo stalls (Wi-Fi, chain) | Medium | Recorded backup video of a real run |
| Laptop RAM exhausted by rebuilds | Low | Cap concurrent workers at 2–3 |
| Judges see self-run miners as fake competition | Low | Say plainly they are self-operated strategies; show the public miner CLI |

**Roadmap after the hackathon**

1. Harder families: scanned noise, GD&T symbols, multi-part assemblies, sheet metal.
2. Submitted solvers: miners commit engines; validators run them on identical hidden tasks (the on-prem product).
3. Fixed model endpoint for audits so every engine can be re-run fairly.
4. Independent validators and stronger isolation on disposable worker machines.
5. Design partner: one conversion bureau or manufacturer providing real (private) evaluation drawings run on-prem.
6. Plugins for FreeCAD, Onshape and SolidWorks; pay-per-drawing API.

## Sources

**Bittensor**

- [Migrating from v9/v10 (v11 SDK, signed HTTP, intents)](https://www.bittensor.com/docs/migration)
- [Signed requests](https://www.bittensor.com/docs/guides/signed-requests) · [Mining](https://www.bittensor.com/docs/guides/mining) · [Set weights](https://www.bittensor.com/docs/tx/set-weights)
- [Commitment query](https://pr-2953.preview.bittensor.com/llms.mdx/docs/query/commitment/content.md)

**Subnet precedents**

- [404-GEN competition system](https://github.com/404-Repo/404-gen-subnet) · [404-GEN commit tool](https://github.com/404-Repo/404-gen-commit) · [Atlas](https://www.tao.media/404-gen-sn17-introduces-atlas-to-bring-decentralized-3d-ai-into-enterprise-workflows/)
- [SATNet (Docker images committed on-chain)](https://github.com/wallscaler/SATNet)
- [Distil SN97](https://github.com/unarbos/distil)
- [BitMind docs](https://docs.bitmind.ai/llms-full.txt)
- [SN1 Apex dashboard](https://www.macrocosmos.ai/sn1/dashboard) · [SN9 leaderboards](https://macrocosmosai.substack.com/p/more-oversight-better-visibility) · [TrajectoryRL CLI](https://pypi.org/project/trajrl/2.1.0/)

**CAD tooling**

- [draftwright](https://pypi.org/project/draftwright/) · [build123d drafting helpers](https://pypi.org/project/build123d-drafting-helpers/0.15.3/)
- [build123d export\_gltf](https://build123d.readthedocs.io/en/stable/_modules/exporters3d.html)
- [three-cad-viewer](https://github.com/bernhard-42/three-cad-viewer) · [OCP Viewer](https://pypi.org/project/ocp-viewer)
- [agentcad](https://pypi.org/project/agentcad/0.5.0/)

**Research and market**

- [Drawing-Recode](https://arxiv.org/abs/2607.27558) · [Drawing2CAD](https://arxiv.org/html/2508.18733v2)
- [CADmore conversion costs](https://cadmore.com/blog/cad-conversion-cost) · [Cad Crowd](https://www.cadcrowd.com/blog/?p=23090) · [IndiaMART](https://m.indiamart.com/city/thane/cad-conversion.html) · [CADCAM.org](https://cadcam.org/3d-scanning/convert-2d-cad-drawing-to-3d)
- [Autodesk Neural CAD](https://develop3d.com/cad/autodesks-ai-blueprint-for-cad/) · [Neural Concept](https://www.pulse.bot/saas/news/neural-concept-raises-100m-to-scale-ai-native-engineering-81df26ae-d340-4e56-9b5a-8b60430053d6/) · [Backflip](https://3dprint.com/315370/backflip-raises-30m-for-text-to-3d-print-software/) · [AdamCAD](https://pasqualepillitteri.it/en/news/3372/adamcad-text-to-cad-ai-review-2026)
