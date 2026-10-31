/** Track B (king of the hill) read API. Mirrors docs/api/hill-contract.md (draft 0.2); change both together. */

import type { Schemas } from "@/lib/api";

export type ModelStatus =
  | "submitted"
  | "prechecked"
  | "queued"
  | "evaluating"
  | "scored"
  | "champion"
  | "defeated"
  | "rejected";

export type Family = "plate" | "flange" | "wafer_chuck" | "vacuum_chamber";

export type Model = {
  /** Miner: weight-metadata SHA256; catalog: SHA256 of "chutes-catalog:" + provider id (not a weights claim). */
  fingerprint: string;
  name: string;
  source: "catalog" | "miner" | "mock";
  repo: string | null;
  revision: string | null;
  base_model: string | null;
  hotkey: string | null;
  uid: number | null;
  commit_block: number | null;
  submitted_at: string;
  status: ModelStatus;
  reject_reason: string | null;
  progress: { done: number; total: number } | null;
  mean_quality: number | null;
  per_family: Partial<Record<Family, number>>;
  critical_pass_rate: number | null;
  edit_pass_rate: number | null;
  recent_tasks: number[];
  matches_won: number;
  matches_lost: number;
  mean_latency_s: number | null;
  tee: boolean;
  chutes_url: string | null;
  hf_url: string | null;
  fee: { amount_tao: number; simulated: boolean } | null;
};

export type LineageEntry = {
  rev: string;
  fingerprint: string;
  name: string;
  crowned_at_block: number;
  crowned_at: string;
  score: number;
  dethroned_at_block: number | null;
};

export type ModelRef = { fingerprint: string; name: string };

export type MatchSummary = {
  match_id: string;
  challenger: ModelRef;
  champion: ModelRef | null;
  status: "running" | "decided";
  /** Hidden during a match; revealed after decision and retirement of every task. */
  seed: { block_hash: string; drand_round: number; value: number } | null;
  tasks_total: number;
  tasks_done: number;
  challenger_mean: number | null;
  champion_mean: number | null;
  margin: number;
  verdict: "crowned" | "defended" | null;
  decided_block: number | null;
  started_at: string;
};

export type Entry = {
  quality: number | null;
  latency_s: number | null;
  error: string | null;
  sets: Schemas["SetResult"][];
  models: Schemas["ModelFile"][];
};

export type MatchTask = {
  index: number;
  challenge_id: string;
  family: Family;
  drawing_url: string;
  challenger: Entry;
  champion: Entry | null;
};

export type Hill = {
  margin: number;
  tasks_per_match: number;
  families: Family[];
  champion: Model | null;
  lineage: LineageEntry[];
  live_match: MatchSummary | null;
  queue: Model[];
};

export type StatusEvent = { status: ModelStatus; at: string; block: number | null; detail: string | null };
export type ModelDetail = { model: Model; matches: MatchSummary[]; events: StatusEvent[] };
export type MatchDetail = { match: MatchSummary; tasks: MatchTask[] };
