/**
 * Every number on the landing page, with where it came from. Nothing here is invented:
 * - zeroScore: `apps/web/scripts/landing-assets.py` output (flange seed 1000, real checker), 2026-10-30.
 * - gateRun, attackChart, honestAudit, transcript: the backend-gate run `DEMO_HEADLESS=1 make demo`,
 *   2026-10-29, log at ~/.cadrecover/runtime/logs/gate-demo.log (also notes/agent-c.md, Phase 8).
 * - swappedEngine: notes/agent-a.md, Phase 7 (audit of a swapped engine, revoked at block 29321).
 * - redrawCost: PRD.md market table ("Standard 2D-to-3D conversion (one provider)").
 */

export const zeroScore = {
  drawingNumber: "LEGACY-1987-1000",
  boltCircleError: "0.8 mm",
  holeOffset: "0.400 mm",
  tolerance: "0.1 mm",
  holes: 6,
  shapeOverlap: "99.8%",
  dimensionsInTolerance: "100%",
  score: 0,
};

export const gateRun = {
  runId: "run_6b6a61efe4",
  date: "29 Oct 2026",
  committedAt: 1584,
  revealedAt: 1595,
  qualityFloor: 50,
};

export type AttackRow = {
  uid: number;
  miner: string;
  honest: boolean;
  /** Q per parameter set: the drawing's own values, then the three hidden edits */
  sets: [number, number, number, number];
  meanQ: number;
  weight: number;
  verdict: string;
};

export const attackChart: AttackRow[] = [
  { uid: 2, miner: "mock-oracle", honest: true, sets: [100, 100, 100, 100], meanQ: 100, weight: 0.5,
    verdict: "Reads the drawing and keeps every dimension a parameter." },
  { uid: 3, miner: "mock-noisy", honest: true, sets: [100, 100, 100, 100], meanQ: 100, weight: 0.5,
    verdict: "Honest, but misreads a value now and then." },
  { uid: 4, miner: "diag-constant", honest: false, sets: [100, 0, 0, 0], meanQ: 25, weight: 0,
    verdict: "Copies the drawing and ignores edits. The hidden edits catch it." },
  { uid: 5, miner: "diag-wrong-holes", honest: false, sets: [0, 0, 0, 0], meanQ: 0, weight: 0,
    verdict: "Makes every hole 30% too large. The critical-feature check zeroes each set." },
  { uid: 6, miner: "diag-crash", honest: false, sets: [0, 0, 0, 0], meanQ: 0, weight: 0,
    verdict: "Imports a network library. The sandbox refuses to build it." },
];

export const honestAudit = { live: 100, audit: 90.3, tasks: [100, 88, 83], margin: 10, block: 1601 };

export const swappedEngine = { live: 100, audit: 25, revokedAtBlock: 29321 };

export type TranscriptLine = { text: string; tone?: "head" | "dim" | "ok" | "cmd" };

/** Lines copied verbatim from the gate-run log; "..." marks lines left out. */
export const transcript: TranscriptLine[] = [
  { text: "$ DEMO_HEADLESS=1 make demo", tone: "cmd" },
  { text: "== 1/6 localnet", tone: "head" },
  { text: "producing blocks: 12 -> 21" },
  { text: "== 3/6 subnet bootstrap (idempotent)", tone: "head" },
  { text: "netuid 2 | validator uid 1 | commit-reveal on" },
  { text: "== 5/6 miners (5 local, axons served, engines committed)", tone: "head" },
  { text: "engine miner1 sha256:65a62fa2263f block 279" },
  { text: "...", tone: "dim" },
  { text: "== 6/6 doctor", tone: "head" },
  { text: "all checks passed" },
  { text: "[round] run_6b6a61efe4: challenge ch_10d48037791c735c · 5 miners · deadline 180s" },
  { text: "  uid 2   mock-oracle            done     Q 100.0  sets [100, 100, 100, 100]" },
  { text: "  uid 4   diag-constant          done     Q  25.0  sets [100, 0, 0, 0]" },
  { text: "  uid 5   diag-wrong-holes       done     Q   0.0  sets [0, 0, 0, 0]" },
  { text: "...", tone: "dim" },
  { text: "[chain] weights committed at block 1584" },
  { text: "[chain] read back at block 1595: {2: 0.5, 3: 0.5} (matches the batch)" },
  { text: "[audit] 5DyvYVHhCD… engine 73cf808a1f19 live 100.0 audit 90.3 -> PASS" },
  { text: "== backend gate check", tone: "head" },
  { text: "  ok round run_6b6a61efe4 done | weights revealed | audits uid 3 pass", tone: "ok" },
];

export const redrawCost = "$150-300";
