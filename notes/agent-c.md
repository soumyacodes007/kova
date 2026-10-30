# Agent C: miner, API and frontend (phases 4, 8, then 9–11)

Owns: `miner/`, `api/`, `cli.py`, `apps/web/`, `fixtures/public/`, and the `protocol/` job and result envelopes. Rules: [AGENTS.md](../AGENTS.md).

For each phase: tick items only with evidence (a command plus its result). List what's not done as clearly as what's done.

---

## Day 1: protocol drafts

**Status:** done (2026-10-29)

- [x] Job request and result envelope schemas in `protocol/jobs.py`:
  - `JobRequest`: idempotent `job_id`, PublicChallenge, `drawing_url`, deadline
  - `JobAccepted`, `JobStatus`
  - `JobResult`: source capped at 64 KB, `source_sha256` validated against the source, entry point, model ID and strategy version recorded but never trusted

**Done:** evidence in `tests/services/test_protocol.py`: `test_job_result_hash_must_match_source`, `test_job_request_round_trips` (in the 10 passed).
**Not done / gaps:** HTTP signing isn't in these bodies, by design: `bt.http_auth` headers carry it (Phase 4).
**Decisions:** the signature lives in transport headers, not in the envelope. A valid signature proves the sender, not correctness.
**Interfaces changed:** created v0.1.0.
**Blockers:** none. **Ready for Phase 4:** use `fixtures/public/sample_plate/` as the practice task (`cli.py` already has `challenge new/show`, added by A; command list below).

---

## Phase 4: Miner and signed jobs

**Status:** done with **mock strategies** (2026-10-29); real VLM strategies wait for an API key · **Done when:** a signed job returns build123d code that scores above the floor (50).

- [x] **FastAPI miner** (`miner/server.py`, `cadrecover miner run`):
  - `POST /v1/jobs` → 202, idempotent by `job_id` (a retry never re-runs the model)
  - `GET /v1/jobs/{id}`, `GET /v1/health`
  - every request is verified with `bt.http_auth.verify`: receiver binding, freshness, signature, replay via `InMemoryNonceStore`
  - optional validator allowlist (403)
  - the drawing's sha256 is checked against the challenge record
  - **responses are signed with the miner hotkey** (`POST /v1/results/{job_id}` payload bound to the validator), and the validator verifies them in `validator/client.py`
- [~] **Strategies:** per the user (2026-10-29), **mock/scripted for now**:
  - `mock-oracle` (reads perfectly) and `mock-noisy` (seeded misreads: thickness ±1 mm 35% of the time, hole +0.5 mm 15%). Both are labelled `mock`, need `CADRECOVER_DEV_ORACLE=1`, and only work on the validator's machine.
  - `claude-vision` is a slot that raises a clear error until it's implemented.
  - **Not done:** real strategies 1 (direct vision-to-CAD), 2 (extract-then-build) and 3 (render-and-repair).
- [x] **Diagnostic miners**, labelled `diagnostic`:
  - `diag-constant` (expect 25)
  - `diag-proportional` (expect 25)
  - `diag-wrong-holes` (expect 0)
  - `diag-crash` (forbidden import; expect 0)
- [x] **Recorded per job:** `model_id`, `strategy_version` (`<strategy>/<version>`) and `duration_s` in JobResult. Budget isn't tracked; mocks have no cost.

**Done-when evidence:**
- Round `run_47c501d8e4`: the real `mock-oracle` miner process (port 8101, wallet miner1) received a signed job, returned build123d source in a signed result, and the validator's sandboxed rebuild scored **Q 100 (100/100/100/100), above the floor of 50**.
- Tests: `tests/services/test_miner_protocol.py` **8 passed**:
  - round trip with a verified signed result
  - an idempotent retry runs the model once
  - a hash mismatch fails the job
  - **unsigned, tampered, wrong-receiver and replay → 401**
  - another validator can't read someone else's job → 404
  - the allowlist → 403

**Not done / gaps:**
- **No real vision strategy.** It needs `ANTHROPIC_API_KEY`. Then implement `ClaudeVision` (read the claude-api docs first): send the drawing PNG, the public record and the edit rules; return `DRAWN` + `build_part(overrides)` source; render-and-repair loop for strategy 3.
- **Job state is in memory**, so a miner restart forgets in-flight jobs. The validator treats that as a timeout.
- **Mocks read ground truth.** They prove the loop, not miner skill. Never run them on testnet.

**Decisions:**
- **Mock strategies are gated:** they need `CADRECOVER_DEV_ORACLE=1` and a local private record, and they're labelled `mock` in `/v1/health` and the leaderboard labels.
- **Results are signed over the response body** as a `POST /v1/results/{job_id}` payload bound to the validator. That reuses `http_auth` without a custom scheme.

**Interfaces changed:** none beyond protocol 0.2.0 (A).
**Blockers:** the vision-model API key (user is sorting it out).

---

## Phase 8: API, CLI and terminal demo

**Status:** done · **Done when (BACKEND GATE):** `make demo` runs a full round, a weight submission and an audit end to end, visible in the terminal alone.

- [x] FastAPI read API and SSE with resumable event IDs; TypeScript types generated from OpenAPI (`src/cadrecover/api/`, `docs/api/openapi.json`, `apps/web/lib/api-types.ts`; regenerate with `scripts/export-openapi.py`, `--check` for staleness)
- [x] CLI: `doctor`, `task sample`, `score`, `miner run`, `validator run`, `status` (+ `events --follow`, `api serve`, `auditor run`)
- [x] Rich logs, 3-pane tmux layout, `make demo` starts everything (`DEMO_HEADLESS=1` for a scripted run; `make demo-down`)
- [x] Gate passed → marked in `shared.md` with evidence

**Done-when evidence:** from a clean state (DB and `chain.json` moved to `~/.cadrecover/backup-pre-gate-20261029-0911`, localnet container recreated): `DEMO_HEADLESS=1 make demo` → localnet blocks 12 → 21; bootstrap netuid 2, commit-reveal on; 5 engine images; 5 miners (axons + engine commitments); `doctor` all checks passed; 2 rounds (oracle 100, noisy 100, constant 25, wrong-holes 0, crash 0); weights `{2: 0.5, 3: 0.5}` committed at block 1584, revealed at 1595; audit uid 3 engine `73cf808a1f19` live 100.0 audit 90.3 (100, 88, 83) → PASS; `chain weights` block 2515 `{2: 0.5, 3: 0.5}`; `backend gate check: ok round run_6b6a61efe4 done | weights revealed | audits uid 3 pass` → `demo ok`, EXIT=0. Full log: `~/.cadrecover/runtime/logs/gate-demo.log`.

**Done:** API endpoints status, runs, run detail (per-set V/C/G/D/Q, failed checks, GLB/drawing URLs), leaderboard, miners, weights with every receipt, commitments, audits, public challenges, events + SSE stream (`Last-Event-ID` resume, keep-alives); read-only DB; CORS localhost:3000. Tests: `tests/services/test_api.py` (54: shapes, no private leak, 13 path-traversal attempts, SSE resume, OpenAPI freshness), `tests/services/test_cli.py`.

**Not done / gaps:**
- No endpoint for miner source or STEP download (Phase 11 needs STEP).
- Chain probe in `/v1/status` only for `local`.
- Miner logs are empty (server logs at warning); `events --follow` replaces them in the tmux pane.
- Audits take 3–10 min, so `make demo` is ~15 min end to end.
- Honest miners are mocks until claude-vision is wired.

**Decisions:** while a challenge is active the API withholds per-set values, failed-check text and reference GLBs (they leak answers); all shown once retired. Leaderboard `latest_batch_weight` is what the newest batch gave; use it for on-chain claims.
**Interfaces changed:** new read API (OpenAPI is the contract for the frontend).
**Blockers:** none.

---

## Phase 9: Arena on the real API *(only after the backend gate)*

**Status:** in progress (pages built on recorded rounds; a live round not yet watched in the browser) · **Done when:** a live round plays in the browser with no fixture data.

- [x] Next.js shell, status bar, React Three Fiber viewer loading validator GLBs (`components/app/`, `components/arena/`; status bar polls `/v1/status` every 5 s)
- [x] /arena/[runId]: drawing, miner strip, round events (polled every 2.5 s while live), per-set V/C/G/D/Q and failed checks, reference ghost overlay, failure focus (click a check: red ring + camera framing). Not done: section view
- [ ] Parameter slider: queue a rebuild on release; swap the model when the result arrives

**Done-when evidence:**
**Done:** 2026-10-30 scaffold only: `create-next-app` in `apps/web` (Next 16.4.3, React 19.3, TypeScript, Tailwind 4, ESLint, App Router, `@/*` alias); `npm run lint` clean, `npm run build` passes. Uses npm, not pnpm (pnpm isn't installed on this machine). `lib/api-types.ts` kept. No pages, R3F or shadcn yet.
2026-10-30 landing page `/` (static): tokens from the supplied Cloudflare DESIGN.md (light only, one orange accent, ink text on orange for AA contrast), Geist; R3F viewer (three 0.187, fiber 9, drei 10) showing real GLBs from `apps/web/scripts/landing-assets.py` (flange seed 1000; candidate with bolt circle +0.8 mm: IoU 0.998, D 1.0, critical fail, 6 holes 0.400 mm off). Every number is sourced in `lib/landing-data.ts`. `npm run lint` clean, `npm run build` passes; checked at 1440 and 375 px (no horizontal scroll, no console errors). The "Next: king of the hill" section is labelled Planned.
2026-10-30 app pages on the real read API (`make api`, proxied through `/api/v1/*` by a Next rewrite): /arena (redirects to the latest round), /arena/[runId], /leaderboard, /runs (+ /runs/[id] redirects to the arena), /chain, /docs. Evidence: `curl` of each page from the dev server against the 29 Oct DB: /leaderboard shows mock-oracle and both audit passes; /runs lists 7 rounds; /chain shows batch wb_5bb804178e with receipts and 4 audits; /arena/run_48c02312ed renders with real GLBs (`/api/v1/runs/.../s0.candidate.glb` 200). In the browser: wrong-holes miner shows 4 red markers exactly on the holes; clicking `hole_2.size` frames that hole. `npx tsc --noEmit`, `npm run lint` clean; `npm run build` passes (pages are partial prerenders with streamed data).
**Not done / gaps:**
- No live round watched in the browser yet (needs `make demo` running with `make api`); events are polled, not SSE.
- Parameter slider: needs a backend rebuild endpoint; the API is read-only.
- Section view not built. The offline panel (API down) is written but not exercised.
- Arena viewer has no wheel zoom on purpose (page scroll); camera framing is a fixed iso direction.

---

## Phase 10: Trust pages *(with A and B)*

**Status:** mostly built · **Done when:** a judge can trace any score to its checks and its chain receipt.

- [x] /leaderboard, /runs/[id] (= arena), audits (on /chain). /security not a page: the landing page carries the measured attack chart
- [x] Block numbers on every weight receipt, commitment and audit (/chain); reproduce command on the arena (`cadrecover score solution.py --task <id>`)

**Done-when evidence:**
**Done:**
**Not done / gaps:**

---

## Phase 11: Ship *(all)*

**Status:** blocked by gate · **Done when:** one live run, one recorded run, a real chain receipt and a downloadable STEP.

- [ ] Testnet run if registration is live; otherwise localnet with readback
- [ ] README, MINER.md, MECHANISM.md; positioning vs Backflip (REVIEW #2)
- [ ] Backup video of a real run; rehearse three times

**Done-when evidence:**
**Done:**
**Not done / gaps:**

---

## Session log (newest first)

| Date | Branch | What changed | Tests run | Next |
| --- | --- | --- | --- | --- |
| 2026-10-30 | c/phase-9-web | Track B pages checked and fixed (sample links, 404 split), live polling, status bar items, contract guard | tsc, lint, build clean; HTTP sweep 18 routes | Browser pass at both viewports; live Track A round |
| 2026-10-30 | shared working tree (root coordinating phase-12 branches) | Track B five read endpoints, shared Track A SetResult/ModelFile types, active-task disclosure checks and GLB serving, metadata-check/model-submit/hill-run CLI; OpenAPI/TS regenerated | WSL node.exe TypeScript noEmit, ESLint and Next production build passed; pytest pending A's environment lock | Run API/CLI tests, verify real hill run in browser; no testnet spend or live deployment authorized |
| 2026-10-29 | b/phase-6-chain | Read API + SSE + TS types, doctor/status/task sample/events/api serve, rich logs, `make demo` | services 138 passed; gate run EXIT=0 | Wire claude-vision; Phase 9 arena on the real API |
| 2026-10-29 | c/phase-4-miner | Signed FastAPI miner, mock/diagnostic strategies, templates, `miner run`, `scripts/run-miners.sh` | services miner protocol 8 passed; live round Q 100 | Wire `ClaudeVision` when the API key arrives; Phase 8 after the Phase 6/7 gate |
| 2026-10-29 | a/phase-0-protocol | Job envelopes; `cli.py` created with B's and A's commands (C owns the file; see `shared.md` Requests) | 10 passed | Phase 4: FastAPI miner + strategy 1 against the sample fixture |

## Phase 12: Track B API and CLI

**Status:** in progress; no end-to-end claim until the real catalog run and all suites pass.

- [ ] Five read routes match `docs/api/hill-contract.md`, with GLBs and Track A disclosure rules.
- [ ] CLI `model check`, `model submit` and `hill run` use B's precheck, hotkey commitments and shared-budget runner.
- [ ] Real `/hill`, `/hill/leaderboard`, `/hill/match/<id>` browser verification (no fixtures).

**Implemented, verification pending:** API storage queries, the five routes and read-only GLB route; public errors/checks/values/reference models withheld on active tasks; model event history; generated OpenAPI/TypeScript. Tests cover live/retired disclosure, 404s and local/test separation. No miner source runs in the API. Runtime settings use `CADRECOVER_API_NETWORK=local|test` (default local); the same fingerprint is separate on each network.

**Decisions:** testnet CLI submissions and catalog runs require the operator's explicit `--allow-testnet-spend` opt-in. Catalog runs print the runner's complete result, including actual recorded spend. The API uses the canonical scoring formula when private serialized SetScore records omit the computed `q` property. Hill contract draft 0.2 makes `MatchSummary.seed` nullable: exposing a deterministic generation seed would reveal active ground truth, so every API surface hides the seed until the match is decided and every task retired; the frontend handles null explicitly. Model events from another hotkey or later commitment do not become the original model's status history. These changes are coordinated with B in `notes/shared.md`.

**Evidence so far:** all commands invoked from WSL. `node.exe node_modules/typescript/bin/tsc --noEmit` and `node.exe node_modules/eslint/bin/eslint.js` exited 0; `node.exe node_modules/next/dist/bin/next build` exited 0, listing `/hill`, `/hill/leaderboard`, `/hill/match/[id]`, models, matches and submit routes. `~/.cadrecover/envs/services/bin/python scripts/export-openapi.py --types python` wrote both contract artifacts successfully.

**Not done:** services tests pending A's three-suite prerequisite lock; no real hill crowning, live artifact/browser evidence, local model commit/readback or testnet commit→reveal verified by C yet. Miner deployment remains B's disabled-by-default integration; this frontend does not claim queued models were evaluated. Existing user changes in the frontend and CLI are preserved.

## Phase 9b: Track B pages, live updates, status bar (C, 2026-10-30)

**Status:** pages built and checked over HTTP against the live read API; **not checked in a browser** (this session had no browser tool).

- [x] `cd apps/web && npx tsc --noEmit` exit 0; `npm run lint` clean; `npm run build` exit 0, route table lists `/hill`, `/hill/leaderboard`, `/hill/matches`, `/hill/match/[id]`, `/hill/models/[fingerprint]`, `/hill/submit`, `/tracks` (18 pages).
- [x] No em or en dashes in any rendered page text (regex over the HTML minus scripts, 18 routes: 0). The only hits in `apps/web` source are the Next-generated `AGENTS.md`.
- [x] HTTP sweep of `/`, `/tracks`, `/arena`, `/arena/run_48c02312ed`, `/leaderboard`, `/runs`, `/chain`, `/docs`, `/hill`, `/hill/leaderboard`, `/hill/matches`, `/hill/submit`, `/hill/match/<id>` and the five Track B routes with `?sample=1`: all 200, none crashed; the "Sample data." banner appears only with `?sample=1` and on every sample page.
- [x] Sample mode keeps `?sample=1` on nav, track switch, and in-page links (was a bug: the nav dropped it; fixed in `components/app/nav-links.tsx`).
- [x] Offline (API process stopped): `/leaderboard`, `/chain`, `/hill`, `/arena`, `/runs` return 200 with the "not running" or "No live data" panel and no crash. API restarted after.
- [x] Backend now serves Track B (`/v1/hill` returns the empty hill). Live `/hill`, `/hill/leaderboard`, `/hill/matches` render the real empty state. A missing record (`/hill/match/m_nope`, `/hill/models/abc`) now says "No such match/model"; `lib/api.ts` separates FastAPI's `Not Found` (route missing, keeps the "backend isn't live" panel) from a record 404.
- [x] Types regenerated (`export-openapi.py`, `gen-ts-types.py`). `lib/hill-contract-check.ts` compares the generated schemas with `lib/hill-types.ts` at build time. Two differences are raised in `shared.md`: optional-vs-required, and `Hill.families` is `string[]`.
- [x] Live updates (`components/hill/live.tsx`): polls `/api/v1/events?kind=hill&after=<last id>` every 2.5 s only while a match is running; `/hill` calls `router.refresh()`, `/hill/match/[id]` refetches the match, on `hill.task_scored`, `hill.crowned`, `hill.defended`. Proxy path `/api/v1/events?kind=hill` returns 200 through the Next rewrite. SSE not used.
- [x] Status bar (`components/app/status-bar.tsx`): on `/hill*` shows "champion <name> <score>" and "match <done>/<total>" from `/api/v1/hill`; hidden when the endpoint fails.

**Not done:**
- No browser check at 1440x900 or 375x812: no console-error check, no `scrollWidth === innerWidth` check, no click on a match tile to see the side-by-side panel update. Needs a session with the browser pane.
- Live polling and the status-bar items are only exercised against an empty hill (no champion, no match), so the running-match path has no live evidence; sample mode never polls by design.
- Task 4 (watch a live Track A round via `make demo`) not run. Task 8 (arena section view, `/try`) not started.
- The working tree is shared with a coordinating session that edits `hill-types.ts`, `docs/api/hill-contract.md`, `lib/api-types.ts` and these notes concurrently (contract now draft 0.2: `seed` is null until a match is decided; the pages already handle it).

