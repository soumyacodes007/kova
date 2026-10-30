"use client";

import dynamic from "next/dynamic";
import { useCallback, useState } from "react";

import { clientPath } from "@/lib/api";
import type { Entry, MatchDetail } from "@/lib/hill-types";

import { useHillEvents } from "./live";
import { RaceChart, Stamp } from "./race-chart";
import { FAMILY_LABEL } from "./ui";

const ArenaViewer = dynamic(() => import("@/components/arena/arena-viewer"), {
  ssr: false,
  loading: () => <div className="h-full w-full animate-pulse bg-surface" />,
});

const src = (url: string) => (url.startsWith("/v1/") ? clientPath(url) : url);

function winner(t: MatchDetail["tasks"][number]) {
  const a = t.challenger.quality;
  const b = t.champion?.quality ?? null;
  if (a == null || (t.champion && b == null)) return null;
  if (b == null || a > b) return "challenger";
  if (b > a) return "champion";
  return "tie";
}

function Side({ title, name, e, tone }: { title: string; name: string; e: Entry | null; tone: "accent" | "ink" }) {
  const cand = e?.models.find((m) => m.set_index === 0 && m.kind === "candidate");
  const failed = e?.sets.flatMap((s) => s.failed_checks.filter((c) => c.location).map((c) => ({ name: c.name, location: c.location as [number, number, number] }))) ?? [];
  return (
    <div className="min-w-0 overflow-hidden rounded-md border border-line bg-paper">
      <div className="flex items-baseline justify-between gap-3 border-b border-line px-4 py-3">
        <p className="min-w-0 truncate text-[14px]">
          <span className="text-ink-soft">{title} </span>
          <span className="font-medium">{name}</span>
        </p>
        <span className={`font-mono text-2xl tracking-[-0.03em] ${tone === "accent" ? "text-accent" : ""}`}>{e?.quality ?? "..."}</span>
      </div>
      <div className="aspect-[4/3]">
        {cand ? (
          <ArenaViewer layers={[{ url: clientPath(cand.url), tone: "part" }]} markers={failed} focus={null} label={`${name}'s part`} />
        ) : (
          <div className="flex h-full items-center justify-center p-6 text-center text-[13px] text-ink-soft">
            {e?.quality == null ? "Not scored yet." : "No 3D file for this entry."}
          </div>
        )}
      </div>
      <div className="flex gap-1 border-t border-line px-4 py-3">
        {(e?.sets ?? []).map((s) => (
          <span key={s.index} className={`h-2 flex-1 rounded-[1px] ${s.passed ? "bg-accent" : s.q_s > 0 ? "bg-accent/30" : "hatch border border-ink/15"}`} />
        ))}
        {e?.error && <span className="text-[12px] text-fail">{e.error}</span>}
      </div>
    </div>
  );
}

export function MatchView({ detail: initial, poll = false }: { detail: MatchDetail; poll?: boolean }) {
  const [detail, setDetail] = useState(initial);
  const { match, tasks } = detail;
  const matchId = match.match_id;

  // a scored task or a verdict changes the match: refetch it, and keep the last good copy on failure
  const refresh = useCallback(async () => {
    try {
      const res = await fetch(clientPath(`/v1/matches/${encodeURIComponent(matchId)}`), { cache: "no-store" });
      if (res.ok) setDetail((await res.json()) as MatchDetail);
    } catch {
      /* keep the last good match */
    }
  }, [matchId]);
  useHillEvents(poll && match.status === "running", refresh);

  const firstDone = tasks.findIndex((t) => t.challenger.quality != null);
  const [sel, setSel] = useState(Math.max(0, firstDone));
  const t = tasks[sel];
  const ch = tasks.map((x) => x.challenger.quality);
  const cp = tasks.map((x) => x.champion?.quality ?? null);
  const wins = tasks.reduce(
    (acc, x) => {
      const w = winner(x);
      if (w === "challenger") acc.ch += 1;
      if (w === "champion") acc.cp += 1;
      return acc;
    },
    { ch: 0, cp: 0 },
  );

  return (
    <div className="grid gap-8">
      <section aria-label="Scoreboard" className="grid gap-6 rounded-md bg-ink p-6 text-paper md:p-8 lg:grid-cols-[minmax(0,1fr)_auto]">
        <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-end gap-4">
          <div className="min-w-0">
            <p className="text-[12.5px] text-[#a8a8a3]">challenger</p>
            <p className="truncate text-2xl font-medium tracking-[-0.02em]">{match.challenger.name}</p>
            <p className="font-mono text-6xl tracking-[-0.05em] text-accent">{match.challenger_mean?.toFixed(1) ?? "..."}</p>
            <p className="font-mono text-[12px] text-[#a8a8a3]">{wins.ch} drawings won</p>
          </div>
          <span className="pb-6 font-mono text-[14px] text-[#a8a8a3]">vs</span>
          <div className="min-w-0 text-right">
            <p className="text-[12.5px] text-[#a8a8a3]">champion</p>
            <p className="truncate text-2xl font-medium tracking-[-0.02em]">{match.champion?.name ?? "empty hill"}</p>
            <p className="font-mono text-6xl tracking-[-0.05em]">{match.champion_mean?.toFixed(1) ?? "..."}</p>
            <p className="font-mono text-[12px] text-[#a8a8a3]">{wins.cp} drawings won</p>
          </div>
        </div>
        <div className="flex items-center justify-center lg:min-w-[14rem]">
          {match.verdict ? (
            <div className="rounded-sm bg-paper p-3">
              <Stamp verdict={match.verdict} block={match.decided_block} />
            </div>
          ) : (
            <p className="text-center font-mono text-[13px] text-[#c9c9c4]">
              drawing {match.tasks_done} of {match.tasks_total}
              <span className="block text-[12px] text-[#a8a8a3]">needs +{match.margin} to take the hill</span>
            </p>
          )}
        </div>
      </section>

      <section aria-label="Running score" className="rounded-md border border-line p-5 md:p-6">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <p className="text-[15px] font-medium">Running mean, drawing by drawing</p>
          <p className="flex flex-wrap gap-4 font-mono text-[12px] text-ink-soft">
            <span className="flex items-center gap-1.5">
              <span className="h-[3px] w-5 bg-accent" /> challenger
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-[2px] w-5 bg-ink" /> champion
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-5 border-t border-dashed border-accent" /> champion + margin
            </span>
          </p>
        </div>
        <RaceChart challenger={ch} champion={cp} total={match.tasks_total} margin={match.margin} />
      </section>

      <section aria-label="Drawings in this match">
        <p className="mb-3 text-[15px] font-medium">The {match.tasks_total} hidden drawings</p>
        <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-5">
          {tasks.map((x) => {
            const w = winner(x);
            const on = x.index === sel;
            return (
              <button
                key={x.index}
                type="button"
                onClick={() => setSel(x.index)}
                aria-pressed={on}
                className={`overflow-hidden rounded-md border text-left transition-colors active:translate-y-px ${
                  on ? "border-ink shadow-card" : "border-line hover:border-ink/30"
                }`}
              >
                <span className="relative block aspect-[4/3] bg-[#f3efe6]">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={src(x.drawing_url)} alt="" className="h-full w-full object-cover object-center" loading="lazy" />
                  {w && (
                    <span
                      className={`absolute right-1.5 top-1.5 rounded-sm px-1.5 py-0.5 font-mono text-[10.5px] ${
                        w === "challenger" ? "bg-accent text-ink" : w === "champion" ? "bg-ink text-paper" : "bg-paper text-ink"
                      }`}
                    >
                      {w === "tie" ? "tie" : w === "challenger" ? "challenger" : "champion"}
                    </span>
                  )}
                </span>
                <span className="flex items-baseline justify-between gap-2 px-2.5 py-2 font-mono text-[12px]">
                  <span className="text-ink-soft">
                    {x.index + 1}. {FAMILY_LABEL[x.family]}
                  </span>
                  <span>
                    <span className="text-accent">{x.challenger.quality ?? "..."}</span>
                    <span className="text-ink-soft">/</span>
                    {x.champion?.quality ?? "..."}
                  </span>
                </span>
              </button>
            );
          })}
        </div>
      </section>

      {t && (
        <section aria-label={`Drawing ${t.index + 1} side by side`} className="grid gap-4">
          <p className="text-[15px] font-medium">
            Drawing {t.index + 1}: {FAMILY_LABEL[t.family]} <span className="font-mono text-[12px] font-normal text-ink-soft">{t.challenge_id}</span>
          </p>
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)]">
            <div className="overflow-hidden rounded-md border border-line bg-[#f3efe6]">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={src(t.drawing_url)} alt={`Drawing for task ${t.index + 1}`} className="h-full w-full object-contain" />
            </div>
            <Side title="challenger" name={match.challenger.name} e={t.challenger} tone="accent" />
            <Side title="champion" name={match.champion?.name ?? "none"} e={t.champion} tone="ink" />
          </div>
        </section>
      )}
    </div>
  );
}
