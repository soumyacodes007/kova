/**
 * Compile-time guard: lib/hill-types.ts must stay the same shape as the generated OpenAPI schemas.
 * Generated schemas mark defaulted fields optional (the server always sends them), so optionality is
 * ignored here. Hill.families is `string[]` in the schema and `Family[]` in the UI (see notes/shared.md).
 * A failing line means the backend contract moved: fix hill-types.ts or raise it in notes/shared.md.
 */
import type { components } from "./api-types";
import type * as H from "./hill-types";

type S = components["schemas"];
type DR<T> = T extends object ? { [K in keyof T]-?: DR<T[K]> } : T;
type Same<A, B> = [A] extends [B] ? ([B] extends [A] ? true : "ui type is wider") : "generated type is not assignable";

const ok = true as const;
export const hill: Same<Omit<DR<S["Hill"]>, "families">, Omit<H.Hill, "families">> = ok;
export const model: Same<DR<S["ModelDetail"]["model"]>, H.Model> = ok;
export const modelDetail: Same<DR<S["ModelDetail"]>, H.ModelDetail> = ok;
export const matchSummary: Same<DR<S["MatchSummary"]>, H.MatchSummary> = ok;
export const matchDetail: Same<DR<S["MatchDetail"]>, H.MatchDetail> = ok;
export const matchTask: Same<DR<S["MatchTask"]>, H.MatchTask> = ok;
