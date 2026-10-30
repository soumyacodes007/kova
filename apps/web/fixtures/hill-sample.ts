/**
 * SAMPLE DATA, NOT FROM THE NETWORK. Track B UI work only, shown when a page is opened with ?sample=1 and always
 * under a visible "sample data" banner. Live routes never fall back to it (AGENTS.md: no invented data on live
 * routes). Model names are real Chutes catalog ids; every score, block and hash below is made up.
 */

import type { Hill, MatchDetail, MatchSummary, Model, ModelDetail, StatusEvent } from "@/lib/hill-types";

const fp = (n: number) => `${(n * 0x9e3779b1 >>> 0).toString(16).padStart(8, "0")}${"c0ffee42d15ea5e5".slice(0, 8)}`;

function model(n: number, name: string, over: Partial<Model>): Model {
  return {
    fingerprint: fp(n),
    name,
    source: "catalog",
    repo: null,
    revision: null,
    base_model: null,
    hotkey: null,
    uid: null,
    commit_block: 8336800 + n * 40,
    submitted_at: "2026-10-30T12:00:00Z",
    status: "defeated",
    reject_reason: null,
    progress: null,
    mean_quality: null,
    per_family: {},
    critical_pass_rate: null,
    edit_pass_rate: null,
    recent_tasks: [],
    matches_won: 0,
    matches_lost: 1,
    mean_latency_s: null,
    tee: true,
    chutes_url: null,
    hf_url: null,
    fee: null,
    ...over,
  };
}

const MODELS: Model[] = [
  model(1, "cad-reader-7b", {
    source: "miner", repo: "sample-miner/cad-reader-7b", revision: "3f1c9a0e5b7d2c4a8e6f1b3d5c7a9e0f2b4d6c8a",
    base_model: "Qwen/Qwen2.5-VL-7B-Instruct", hotkey: "5F3sa2TJAWMqDhXG6jhV4N8ko9SxwGy8TpaQS1XaKRHmbsy1", uid: 3,
    status: "champion", mean_quality: 81.5, per_family: { plate: 95, flange: 78.5, wafer_chuck: 71 },
    critical_pass_rate: 0.82, edit_pass_rate: 0.74, recent_tasks: [100, 100, 75, 100, 50, 100, 75, 100, 25, 100],
    matches_won: 2, matches_lost: 0, mean_latency_s: 14.2, hf_url: "https://huggingface.co/", fee: { amount_tao: 0.1, simulated: true },
  }),
  model(2, "gemma-4-31B-turbo-TEE", {
    status: "defeated", mean_quality: 76.0, per_family: { plate: 92, flange: 70, wafer_chuck: 66 },
    critical_pass_rate: 0.77, edit_pass_rate: 0.65, recent_tasks: [100, 75, 75, 100, 50, 75, 50, 100, 25, 100],
    matches_won: 1, matches_lost: 1, mean_latency_s: 9.8, chutes_url: "https://chutes.ai/",
  }),
  model(3, "Qwen3.8-27B-TEE", {
    status: "evaluating", progress: { done: 7, total: 10 }, mean_quality: 79.3, per_family: { plate: 100, flange: 75, wafer_chuck: 58 },
    critical_pass_rate: 0.8, edit_pass_rate: 0.7, recent_tasks: [100, 100, 75, 50, 100, 75, 55], matches_lost: 0,
    mean_latency_s: 18.4, chutes_url: "https://chutes.ai/",
  }),
  model(4, "Kimi-K2.6-TEE", {
    status: "defeated", mean_quality: 68.5, per_family: { plate: 88, flange: 61, wafer_chuck: 52 },
    critical_pass_rate: 0.66, edit_pass_rate: 0.55, recent_tasks: [75, 75, 50, 100, 25, 75, 50, 100, 25, 75],
    mean_latency_s: 22.1, chutes_url: "https://chutes.ai/",
  }),
  model(5, "Qwen3.6-27B-TEE", {
    status: "queued", matches_lost: 0, chutes_url: "https://chutes.ai/",
  }),
  model(6, "copycat-7b", {
    source: "miner", repo: "sample-miner/copycat-7b", revision: "9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b",
    base_model: "Qwen/Qwen2.5-VL-7B-Instruct", hotkey: "5Hb7Gv2Lf9Kp3mXqWzR8sT4uYcN6dE1aJ5oV2iQ7hF3kPx9M", uid: 5,
    status: "rejected", reject_reason: "same weights as cad-reader-7b, committed later", matches_lost: 0, tee: false,
    fee: { amount_tao: 0.1, simulated: true },
  }),
];

const decided: MatchSummary = {
  match_id: "m_sample_crown",
  challenger: { fingerprint: fp(1), name: "cad-reader-7b" },
  champion: { fingerprint: fp(2), name: "gemma-4-31B-turbo-TEE" },
  status: "decided",
  seed: { block_hash: "0x5a3e…91c2", drand_round: 5_210_441, value: 4040116331 },
  tasks_total: 10,
  tasks_done: 10,
  challenger_mean: 82.5,
  champion_mean: 75.0,
  margin: 2,
  verdict: "crowned",
  decided_block: 8337320,
  started_at: "2026-10-30T13:10:00Z",
};

const live: MatchSummary = {
  match_id: "m_sample_live",
  challenger: { fingerprint: fp(3), name: "Qwen3.8-27B-TEE" },
  champion: { fingerprint: fp(1), name: "cad-reader-7b" },
  status: "running",
  seed: { block_hash: "0x81d0…7fa4", drand_round: 5_210_902, value: 1922554107 },
  tasks_total: 10,
  tasks_done: 7,
  challenger_mean: 79.3,
  champion_mean: 82.1,
  margin: 2,
  verdict: null,
  decided_block: null,
  started_at: "2026-10-30T14:02:00Z",
};

export const sampleHill: Hill = {
  margin: 2,
  tasks_per_match: 10,
  families: ["plate", "flange", "wafer_chuck"],
  champion: MODELS[0],
  lineage: [
    { rev: "A", fingerprint: fp(4), name: "Kimi-K2.6-TEE", crowned_at_block: 8336900, crowned_at: "2026-10-30T12:20:00Z", score: 68.5, dethroned_at_block: 8337010 },
    { rev: "B", fingerprint: fp(2), name: "gemma-4-31B-turbo-TEE", crowned_at_block: 8337010, crowned_at: "2026-10-30T12:42:00Z", score: 76.0, dethroned_at_block: 8337320 },
    { rev: "C", fingerprint: fp(1), name: "cad-reader-7b", crowned_at_block: 8337320, crowned_at: "2026-10-30T13:44:00Z", score: 81.5, dethroned_at_block: null },
  ],
  live_match: live,
  queue: [MODELS[4]],
};

export const sampleModels: Model[] = MODELS;
export const sampleMatches: MatchSummary[] = [live, decided];

const FAMS = ["plate", "flange", "wafer_chuck", "flange", "plate", "wafer_chuck", "flange", "plate", "wafer_chuck", "flange"] as const;
const CH = [100, 100, 75, 100, 50, 100, 75, 100, 25, 100];
const DEF = [100, 75, 75, 100, 50, 75, 50, 100, 25, 100];

function entry(q: number | null) {
  const sets = q == null ? [] : [0, 1, 2, 3].map((i) => {
    const pass = i < Math.round((q / 100) * 4);
    return { index: i, valid: true, critical_ok: pass, geometry: pass ? 1 : 0.97, dimensions: pass ? 1 : 0.6, q_s: pass ? 1 : 0,
      passed: pass, failed_check_count: pass ? 0 : 1, failed_checks: [], values: null, revealed: false };
  });
  return { quality: q, latency_s: q == null ? null : 12.5, error: null, sets, models: [] };
}

export function sampleMatch(id: string): MatchDetail | null {
  const m = sampleMatches.find((x) => x.match_id === id);
  if (!m) return null;
  const done = m.tasks_done;
  return {
    match: m,
    tasks: Array.from({ length: m.tasks_total }, (_, i) => ({
      index: i,
      challenge_id: `ch_sample_${i}`,
      family: FAMS[i],
      drawing_url: i % 2 ? "/assets/flange-drawing-top.webp" : "/assets/flange-drawing.webp",
      challenger: entry(i < done ? (m.status === "running" ? [100, 100, 75, 50, 100, 75, 55][i] ?? null : CH[i]) : null),
      champion: entry(i < done ? (m.status === "running" ? [100, 100, 75, 100, 50, 100, 75][i] ?? null : DEF[i]) : null),
    })),
  };
}

export function sampleModel(fingerprint: string): ModelDetail | null {
  const model = MODELS.find((x) => x.fingerprint === fingerprint);
  if (!model) return null;
  const events: StatusEvent[] = [
    { status: "submitted", at: "2026-10-30T12:58:00Z", block: model.commit_block, detail: model.fee?.simulated ? "fee simulated on this network" : null },
    { status: "prechecked", at: "2026-10-30T12:59:00Z", block: null, detail: "weights present, fingerprint unique" },
    { status: "queued", at: "2026-10-30T12:59:10Z", block: null, detail: null },
  ];
  if (model.status !== "queued" && model.status !== "rejected") events.push({ status: "evaluating", at: "2026-10-30T13:10:00Z", block: null, detail: "10 hidden drawings" });
  if (model.status === "champion" || model.status === "defeated") events.push({ status: model.status, at: "2026-10-30T13:44:00Z", block: 8337320, detail: null });
  if (model.status === "rejected") events.push({ status: "rejected", at: "2026-10-30T12:59:00Z", block: null, detail: model.reject_reason });
  return { model, matches: sampleMatches.filter((m) => m.challenger.fingerprint === fingerprint || m.champion?.fingerprint === fingerprint), events };
}
