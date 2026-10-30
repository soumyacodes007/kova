/**
 * Every number on the landing page, with where it came from. Nothing here is invented:
 * - zeroScore: `apps/web/scripts/landing-assets.py` output (flange seed 1000, real checker), 2026-10-30.
 * - attackChart, swappedEngine, receipt: measured runs on a local Bittensor network, recorded in
 *   notes/agent-a.md (Phase 7 attack chart, block 3686; swapped-engine audit, block 29321) and
 *   notes/agent-c.md (Phase 8 gate run: commit block 1584, reveal block 1595).
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

export type AttackRow = {
  miner: string;
  behaviour: string;
  honest: boolean;
  meanQ: number;
  weight: number;
};

export const attackChart: AttackRow[] = [
  { miner: "mock-oracle", behaviour: "Honest", honest: true, meanQ: 100, weight: 0.5 },
  { miner: "mock-noisy", behaviour: "Honest, misreads sometimes", honest: true, meanQ: 100, weight: 0.5 },
  { miner: "diag-constant", behaviour: "Ignores the hidden edits", honest: false, meanQ: 25, weight: 0 },
  { miner: "diag-wrong-holes", behaviour: "Guesses hole sizes", honest: false, meanQ: 0, weight: 0 },
  { miner: "diag-crash", behaviour: "Forbidden import, crashes", honest: false, meanQ: 0, weight: 0 },
];

export const attackChartBlock = 3686;

export const swappedEngine = { audit: 25, live: 100, revokedAtBlock: 29321 };

export const receipt = { committedAt: 1584, revealedAt: 1595 };

export const redrawCost = "$150-300";
