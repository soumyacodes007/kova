import type { components } from "@/lib/api-types";

export type Schemas = components["schemas"];
export type Status = Schemas["StatusOut"];
export type RunSummary = Schemas["RunSummary"];
export type RunDetail = Schemas["RunDetail"];
export type MinerRunResult = Schemas["MinerRunResult"];
export type SetResult = Schemas["SetResult"];
export type Leaderboard = Schemas["Leaderboard"];
export type LeaderboardRow = Schemas["LeaderboardRow"];
export type WeightBatch = Schemas["WeightBatchOut"];
export type Commitment = Schemas["CommitmentOut"];
export type Audit = Schemas["AuditOut"];
export type EventOut = Schemas["EventOut"];

/** Server side: the read API itself. Client side: the same API through the /api/v1 rewrite. */
export const API_BASE = process.env.CADRECOVER_API_URL ?? "http://127.0.0.1:8000";
export const clientPath = (path: string) => `/api${path}`;

export type ApiResult<T> = { ok: true; data: T } | { ok: false; error: string };

/** Live data, never cached. Call it inside a <Suspense> boundary (Cache Components). */
export async function api<T>(path: string): Promise<ApiResult<T>> {
  try {
    const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
    if (res.status === 404) {
      // FastAPI's own "Not Found" means the route does not exist; any other detail is a missing record
      const body = (await res.json().catch(() => null)) as { detail?: unknown } | null;
      return { ok: false, error: body?.detail === "Not Found" ? "route missing" : "not found" };
    }
    if (!res.ok) return { ok: false, error: `API answered ${res.status}` };
    return { ok: true, data: (await res.json()) as T };
  } catch {
    return { ok: false, error: "unreachable" };
  }
}
