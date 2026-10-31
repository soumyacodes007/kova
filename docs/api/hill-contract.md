# Track B (king of the hill) read API: draft contract 0.2

Status: **draft**, written by C for the frontend (2026-10-30). The backend implements it; change it here first and log
the change in `notes/shared.md` → Contracts. TypeScript mirror: `apps/web/lib/hill-types.ts`.

All endpoints are read-only, under the same API as Track A (`make api`, 127.0.0.1:8000). Until they exist, the pages
show "Track B backend not live yet"; `?sample=1` renders labelled sample data for UI work only.

## Statuses

`submitted → prechecked → queued → evaluating → scored → champion | defeated`, or `rejected` (with `reject_reason`)
at any step. A model has one current status.

## `GET /v1/hill`

```jsonc
{
  "margin": 2.0,                 // points a challenger must beat the champion by, on the same tasks
  "tasks_per_match": 10,
  "families": ["plate", "flange", "wafer_chuck"],
  "champion": Model | null,
  "lineage": [LineageEntry],     // oldest first; the last one is the current champion
  "live_match": MatchSummary | null,
  "queue": [Model]               // prechecked/queued, oldest commit first
}
```

`LineageEntry`: `{ "rev": "A", "fingerprint", "name", "crowned_at_block", "crowned_at", "score", "dethroned_at_block": number|null }`

## `GET /v1/models` → `[Model]`, best first

Optional `?network=local|test` (default: the network the API serves) lists another network's models; records never mix networks.

```jsonc
{
  "fingerprint": "f3a9…",        // miner: sorted weight LFS hashes; catalog: sha256("chutes-catalog:" + provider model id)
  "name": "gemma-4-31B-turbo-TEE",
  "source": "catalog" | "miner" | "mock", // catalog = a Chutes catalog model entered by the validator;
                                 // mock = scripted demo miner on localnet (reads private values), never a model
  "repo": "google/gemma-4-31b" | null,
  "revision": "40-hex commit" | null,
  "base_model": "string" | null,
  "hotkey": "ss58" | null, "uid": number | null,
  "commit_block": number | null, "submitted_at": "iso",
  "status": "…", "reject_reason": string | null,
  "progress": { "done": 4, "total": 10 } | null,   // while evaluating
  "mean_quality": number | null,                   // 0..100 over its scored tasks
  "per_family": { "plate": 92.5, "flange": 80.0 }, // mean Q per family
  "critical_pass_rate": number | null,             // 0..1, sets with every critical feature right
  "edit_pass_rate": number | null,                 // 0..1, hidden-edit sets that passed
  "recent_tasks": [100, 75, 0, …],                 // Q of its latest match's tasks, in order
  "matches_won": 0, "matches_lost": 0,
  "mean_latency_s": number | null,
  "tee": true,                                     // runs in a Chutes TEE (claimed by Chutes, not verified by us)
  "chutes_url": string | null, "hf_url": string | null,
  "fee": { "amount_tao": 0.1, "simulated": true } | null
}
```

## `GET /v1/models/{fingerprint}` → `{ "model": Model, "matches": [MatchSummary], "events": [StatusEvent] }`

`StatusEvent`: `{ "status", "at", "block": number|null, "detail": string|null }`

## `GET /v1/matches` → `[MatchSummary]`, newest first

```jsonc
{
  "match_id": "m_…",
  "challenger": { "fingerprint", "name" },
  "champion": { "fingerprint", "name" } | null,    // null for the very first crowning
  "status": "running" | "decided",
  "seed": { "block_hash": "0x…", "drand_round": 123, "value": 4040116331 } | null, // null while running
  "tasks_total": 10, "tasks_done": 7,
  "challenger_mean": number | null, "champion_mean": number | null,
  "margin": 2.0,
  "verdict": "crowned" | "defended" | null,
  "decided_block": number | null,
  "started_at": "iso"
}
```

## `GET /v1/matches/{match_id}` → `{ "match": MatchSummary, "tasks": [MatchTask] }`

```jsonc
{
  "index": 0, "challenge_id": "ch_…", "family": "flange",
  "drawing_url": "/v1/challenges/ch_…/drawing.png",
  "challenger": Entry, "champion": Entry | null
}
```

`Entry`: `{ "quality": number|null, "latency_s": number|null, "error": string|null, "sets": [SetResult], "models": [ModelFile] }`,
where `SetResult` and `ModelFile` are the Track A schemas (`/v1/runs/{run_id}`), so the 3D viewer and checks are shared.

## Events (SSE `/v1/events/stream`, kinds)

`model.status` (`fingerprint`, `status`), `hill.match_started`, `hill.task_scored` (`match_id`, `index`, `side`,
`quality`), `hill.crowned` / `hill.defended` (`match_id`, `fingerprint`, `block`).

Catalog fingerprints identify provider endpoints, not verified weights; catalog revisions are not pinned. Champion results are cached only within each match on its fresh drawings.

Active match entropy is private: seed is null while running, including block_hash and drand_round. Revealed only after a decided match retires its tasks.
