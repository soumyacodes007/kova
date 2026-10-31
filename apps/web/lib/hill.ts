import { sampleHill, sampleMatch, sampleMatches, sampleModel, sampleModels } from "@/fixtures/hill-sample";
import { api, type ApiResult } from "@/lib/api";
import type { Hill, MatchDetail, MatchSummary, Model, ModelDetail } from "@/lib/hill-types";

/** Track B data. `sample` serves the labelled fixture (UI work only); otherwise the live API, never a fallback. */
type Source = { sample: boolean };

const ok = <T,>(data: T): ApiResult<T> => ({ ok: true, data });
const missing = <T,>(): ApiResult<T> => ({ ok: false, error: "not found" });

export const getHill = ({ sample }: Source) => (sample ? Promise.resolve(ok<Hill>(sampleHill)) : api<Hill>("/v1/hill"));
export const getModels = ({ sample, network }: Source & { network?: "local" | "test" }) =>
  sample ? Promise.resolve(ok<Model[]>(sampleModels)) : api<Model[]>(network ? `/v1/models?network=${network}` : "/v1/models");
export const getMatches = ({ sample }: Source) =>
  sample ? Promise.resolve(ok<MatchSummary[]>(sampleMatches)) : api<MatchSummary[]>("/v1/matches");

export function getMatch(id: string, { sample }: Source) {
  if (!sample) return api<MatchDetail>(`/v1/matches/${encodeURIComponent(id)}`);
  const m = sampleMatch(id);
  return Promise.resolve(m ? ok(m) : missing<MatchDetail>());
}

export function getModel(fingerprint: string, { sample }: Source) {
  if (!sample) return api<ModelDetail>(`/v1/models/${encodeURIComponent(fingerprint)}`);
  const m = sampleModel(fingerprint);
  return Promise.resolve(m ? ok(m) : missing<ModelDetail>());
}

/** Keeps sample mode on links inside Track B. */
export const href = (path: string, sample: boolean) => (sample ? `${path}${path.includes("?") ? "&" : "?"}sample=1` : path);

export const isSample = (sp: Record<string, string | string[] | undefined>) => sp.sample === "1";
