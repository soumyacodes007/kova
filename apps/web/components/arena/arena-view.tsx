"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Badge } from "@/components/app/page-parts";
import { clientPath, type EventOut, type MinerRunResult, type RunDetail, type SetResult } from "@/lib/api";
import { q, shortHash, when } from "@/lib/format";

import type { Marker } from "./arena-viewer";

const ArenaViewer = dynamic(() => import("./arena-viewer"), {
  ssr: false,
  loading: () => <div className="h-full w-full animate-pulse bg-surface" />,
});

const LIVE = new Set(["dispatching", "collecting", "evaluating"]);
const SET_NAMES = ["Drawing", "Edit 1", "Edit 2", "Edit 3"];

function setTone(s: SetResult | undefined) {
  if (!s) return "border border-dashed border-ink/20 text-ink-soft";
  if (s.passed) return "bg-accent text-ink";
  if (s.q_s > 0) return "bg-accent/25 text-ink";
  return "border border-ink/15 text-ink-soft hatch";
}

function MiniSets({ sets }: { sets: SetResult[] }) {
  return (
    <span className="grid grid-cols-4 gap-1">
      {[0, 1, 2, 3].map((i) => {
        const s = sets.find((x) => x.index === i);
        return <span key={i} className={`h-2 rounded-[1px] ${setTone(s)}`} />;
      })}
    </span>
  );
}

function MinerCard({ r, active, onClick }: { r: MinerRunResult; active: boolean; onClick: () => void }) {
  const failed = r.failure_class && r.failure_class !== "none";
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`flex w-44 shrink-0 flex-col gap-2.5 rounded-md border p-3 text-left transition-colors active:translate-y-px ${
        active ? "border-ink bg-paper shadow-card" : "border-line bg-paper/60 hover:border-ink/30"
      }`}
    >
      <span className="flex items-baseline justify-between gap-2">
        <span className="font-mono text-[11.5px] text-ink-soft">uid {r.uid}</span>
        <span className="font-mono text-[11.5px] text-ink-soft">{r.evaluated ? "scored" : r.assignment_status}</span>
      </span>
      <span className="truncate font-mono text-[13.5px]">{r.label ?? `uid ${r.uid}`}</span>
      <span className="flex items-baseline justify-between">
        <span className={`font-mono text-2xl tracking-[-0.03em] ${r.quality === 100 ? "" : "text-ink-soft"}`}>
          {r.quality == null ? "..." : Math.round(r.quality)}
        </span>
        {failed && <span className="text-[11.5px] text-fail">{r.failure_class === "miner" ? "failed" : "outage"}</span>}
      </span>
      <MiniSets sets={r.sets} />
    </button>
  );
}

function describe(e: EventOut): string {
  const p = e.payload as Record<string, unknown>;
  const uid = p.uid != null ? `uid ${p.uid}` : "";
  switch (e.kind) {
    case "run.started":
      return `round started: ${p.miners} miners, ${p.deadline_s}s deadline`;
    case "job.sent":
      return `${uid} received the drawing`;
    case "job.done":
      return p.error ? `${uid} answered with an error: ${p.error}` : `${uid} answered`;
    case "job.evaluated":
      return `${uid} scored ${q(p.quality as number)}  sets [${(p.sets as number[] | undefined)?.map((s) => Math.round(s)).join(", ") ?? ""}]`;
    case "weights.proposed":
      return `weights proposed ${JSON.stringify(p.weights)}`;
    case "weights.submitted":
    case "weights.committed":
      return `weights ${e.kind.split(".")[1]} at block ${p.block}`;
    case "weights.revealed":
      return `weights read back at block ${p.block}`;
    default:
      return e.kind;
  }
}

const CHANGES_DETAIL = (e: EventOut) => e.kind === "job.evaluated" || e.kind.startsWith("weights.");

/** The run's events from the API, polled while the round is live. `onScored` runs when a score lands. */
function useRunEvents(runId: string, live: boolean, onScored: () => void) {
  const [events, setEvents] = useState<EventOut[]>([]);
  const onScoredRef = useRef(onScored);
  useEffect(() => {
    onScoredRef.current = onScored;
  }, [onScored]);

  useEffect(() => {
    let closed = false;
    let poll: ReturnType<typeof setInterval> | undefined;
    const seen = new Set<number>();
    let first = true;
    const add = (list: EventOut[]) => {
      const fresh = list.filter((e) => !seen.has(e.event_id));
      fresh.forEach((e) => seen.add(e.event_id));
      if (!fresh.length || closed) return;
      setEvents((prev) => [...prev, ...fresh].sort((a, b) => a.event_id - b.event_id));
      if (!first && fresh.some(CHANGES_DETAIL)) onScoredRef.current();
      first = false;
    };

    async function pollOnce() {
      const after = seen.size ? Math.max(...seen) : 0;
      try {
        const res = await fetch(clientPath(`/v1/events?run_id=${runId}&after=${after}&limit=500`), { cache: "no-store" });
        if (res.ok) add(((await res.json()) as { events: EventOut[] }).events);
      } catch {
        /* the status bar reports an offline API */
      }
    }

    pollOnce();
    if (live) poll = setInterval(pollOnce, 2500);
    return () => {
      closed = true;
      if (poll) clearInterval(poll);
    };
  }, [runId, live]);

  return events;
}

export function ArenaView({ initial }: { initial: RunDetail }) {
  const [detail, setDetail] = useState(initial);
  const run = detail.run;
  const live = LIVE.has(run.status);

  const results = useMemo(
    () => [...detail.results].sort((a, b) => (b.quality ?? -1) - (a.quality ?? -1) || a.uid - b.uid),
    [detail.results],
  );
  const [uid, setUid] = useState<number | null>(results[0]?.uid ?? null);
  const [setIndex, setSetIndex] = useState(0);
  const [ghost, setGhost] = useState(true);
  const [focus, setFocus] = useState<number | null>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch(clientPath(`/v1/runs/${run.run_id}`), { cache: "no-store" });
      if (res.ok) setDetail((await res.json()) as RunDetail);
    } catch {
      /* keep the last good detail */
    }
  }, [run.run_id]);

  // a scored job or a weight receipt changes the detail: refetch it
  const events = useRunEvents(run.run_id, live, refresh);

  const miner = results.find((r) => r.uid === uid) ?? results[0];
  const set = miner?.sets.find((s) => s.index === setIndex);
  const candidate = miner?.models.find((m) => m.set_index === setIndex && m.kind === "candidate");
  const reference = miner?.models.find((m) => m.set_index === setIndex && m.kind === "reference");
  const checks = set?.failed_checks ?? [];
  const markers: Marker[] = checks
    .filter((c) => c.location)
    .map((c) => ({ name: c.name, location: c.location as [number, number, number] }));

  const layers = [
    ...(candidate ? [{ url: clientPath(candidate.url), tone: "part" as const }] : []),
    ...(reference && ghost ? [{ url: clientPath(reference.url), tone: "ghost" as const }] : []),
  ];

  const challenge = detail.challenge;

  return (
    <div className="grid gap-8">
      <div className="flex flex-wrap items-end justify-between gap-6">
        <div>
          <p className="flex flex-wrap items-center gap-3">
            <span className="font-mono text-[13px] text-ink-soft">{run.family ?? "unknown"} round</span>
            <Badge tone={live ? "accent" : run.status === "aborted" ? "fail" : "plain"}>{live ? `live: ${run.status}` : run.status}</Badge>
          </p>
          <h1 className="mt-2 font-mono text-2xl tracking-[-0.02em] md:text-3xl">{run.run_id}</h1>
        </div>
        <dl className="flex flex-wrap gap-x-8 gap-y-3 font-mono text-[12.5px]">
          <div>
            <dt className="text-ink-soft">challenge</dt>
            <dd>{run.challenge_id}</dd>
          </div>
          <div>
            <dt className="text-ink-soft">started</dt>
            <dd>{when(run.started_at)}</dd>
          </div>
          <div>
            <dt className="text-ink-soft">evaluated</dt>
            <dd>
              {run.evaluated}/{run.miners}
            </dd>
          </div>
          <div>
            <dt className="text-ink-soft">best</dt>
            <dd>
              {q(run.best_quality)}
              {run.best_uid != null && ` (uid ${run.best_uid})`}
            </dd>
          </div>
        </dl>
      </div>

      <div className="-mx-4 flex gap-3 overflow-x-auto px-4 pb-1 md:mx-0 md:px-0" role="group" aria-label="Miners in this round">
        {results.map((r) => (
          <MinerCard
            key={r.uid}
            r={r}
            active={r.uid === miner?.uid}
            onClick={() => {
              setUid(r.uid);
              setFocus(null);
            }}
          />
        ))}
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <section aria-label="Drawing" className="grid content-start gap-4">
          <div className="overflow-hidden rounded-md border border-line bg-[#f3efe6]">
            {/* the API serves the published drawing; next/image would need it on an allowed remote host */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={clientPath(`/v1/challenges/${run.challenge_id}/drawing.png`)}
              alt={`Drawing for challenge ${run.challenge_id}`}
              className="h-auto w-full"
            />
          </div>
          {challenge && (
            <div className="rounded-md border border-line p-4">
              <p className="text-[13px] text-ink-soft">Parameters the miner&apos;s code must accept</p>
              <ul className="mt-3 grid gap-x-6 gap-y-1.5 font-mono text-[12.5px] sm:grid-cols-2">
                {challenge.parameters.map((p) => (
                  <li key={p.name} className="flex justify-between gap-3">
                    <span>{p.name}</span>
                    <span className="text-ink-soft">
                      {p.min} to {p.max} {p.unit}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>

        <section aria-label="Model and checks" className="grid content-start gap-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex rounded-md border border-line p-0.5" role="tablist" aria-label="Parameter set">
              {SET_NAMES.map((name, i) => {
                const s = miner?.sets.find((x) => x.index === i);
                return (
                  <button
                    key={name}
                    role="tab"
                    type="button"
                    aria-selected={setIndex === i}
                    onClick={() => {
                      setSetIndex(i);
                      setFocus(null);
                    }}
                    className={`flex items-center gap-2 rounded-sm px-3 py-1.5 text-[13px] transition-colors ${
                      setIndex === i ? "bg-ink text-paper" : "text-ink-soft hover:text-ink"
                    }`}
                  >
                    {name}
                    {s && <span className={`h-2 w-2 rounded-[1px] ${setTone(s)}`} />}
                  </button>
                );
              })}
            </div>
            <label className="flex cursor-pointer items-center gap-2 text-[13px] text-ink-soft">
              <input type="checkbox" checked={ghost} onChange={(e) => setGhost(e.target.checked)} className="accent-[#ff5e1f]" />
              Reference overlay
            </label>
          </div>

          <div className="relative aspect-[4/3] overflow-hidden rounded-md border border-line bg-paper">
            {layers.length ? (
              <ArenaViewer
                layers={layers}
                markers={markers}
                focus={focus}
                label={`Part built by ${miner?.label ?? "the miner"} for ${SET_NAMES[setIndex]}`}
              />
            ) : (
              <div className="flex h-full items-center justify-center p-8 text-center text-[14px] text-ink-soft">
                {miner?.evaluated ? "No model was built for this set." : "The model appears here once this miner is scored."}
              </div>
            )}
            {layers.length > 0 && (
              <p className="pointer-events-none absolute bottom-3 left-3 font-mono text-[11.5px] text-ink-soft">
                {reference ? (ghost ? "grey: miner's part, orange lines: reference" : "miner's part") : "reference shown once the challenge retires"}
              </p>
            )}
          </div>

          {set && (
            <div className="rounded-md border border-line">
              <dl className="grid grid-cols-5 divide-x divide-line border-b border-line font-mono">
                {[
                  ["V", set.valid ? "1" : "0"],
                  ["C", set.critical_ok ? "1" : "0"],
                  ["G", set.geometry.toFixed(3)],
                  ["D", set.dimensions.toFixed(2)],
                  ["Q", Math.round(set.q_s * 100).toString()],
                ].map(([k, v]) => (
                  <div key={k} className="px-3 py-3">
                    <dt className="text-[11.5px] text-ink-soft">{k}</dt>
                    <dd className={`mt-0.5 text-lg ${k === "Q" && set.q_s < 1 ? "text-fail" : ""}`}>{v}</dd>
                  </div>
                ))}
              </dl>
              <div className="p-4">
                {!set.revealed ? (
                  <p className="text-[14px] text-ink-soft">
                    The challenge is still active, so failed checks and hidden values stay private until it retires.
                  </p>
                ) : checks.length === 0 ? (
                  <p className="text-[14px] text-ink-soft">Every check passed for this set.</p>
                ) : (
                  <ul className="grid gap-1.5">
                    {checks.map((c, i) => (
                      <li key={`${c.name}-${i}`}>
                        <button
                          type="button"
                          onClick={() => setFocus(focus === i ? null : i)}
                          disabled={!c.location}
                          className={`flex w-full items-baseline justify-between gap-4 rounded-sm px-2 py-1.5 text-left font-mono text-[12.5px] transition-colors ${
                            focus === i ? "bg-fail/10" : "hover:bg-surface"
                          }`}
                        >
                          <span className="text-fail">{c.name}</span>
                          <span className="text-ink-soft">{c.message}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
                {set.values && (
                  <p className="mt-4 border-t border-line pt-3 font-mono text-[11.5px] leading-relaxed text-ink-soft">
                    built with{" "}
                    {Object.entries(set.values)
                      .map(([k, v]) => `${k}=${v}`)
                      .join(", ")}
                  </p>
                )}
              </div>
            </div>
          )}

          {miner && (
            <p className="font-mono text-[11.5px] text-ink-soft">
              source {shortHash(miner.source_sha256)}
              {miner.strategy_version && ` · ${miner.strategy_version}`}
              {miner.duration_s != null && ` · ${miner.duration_s.toFixed(2)}s`}
              {miner.failure_reason && <span className="text-fail"> · {miner.failure_reason}</span>}
            </p>
          )}
        </section>
      </div>

      <section aria-label="Round events" className="rounded-md border border-line">
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <p className="text-[14px] font-medium">Round events</p>
          <p className="font-mono text-[11.5px] text-ink-soft">{live ? "updating" : `${events.length} events`}</p>
        </div>
        {events.length === 0 ? (
          <p className="px-4 py-6 text-[14px] text-ink-soft">No events recorded for this round.</p>
        ) : (
          <ol className="max-h-80 overflow-y-auto px-4 py-3 font-mono text-[12.5px] leading-[1.9]">
            {[...events].reverse().map((e) => (
              <li key={e.event_id} className="grid grid-cols-[4.5rem_minmax(0,1fr)] gap-3">
                <span className="text-ink-soft">{new Date(e.at).toISOString().slice(11, 19)}</span>
                <span className={e.kind.startsWith("weights.") ? "text-ink" : e.kind === "job.evaluated" ? "text-ink" : "text-ink-soft"}>
                  {describe(e)}
                </span>
              </li>
            ))}
          </ol>
        )}
      </section>

      <p className="text-[13px] text-ink-soft">
        Score any solution against this task, exactly as the validator does:{" "}
        <code className="font-mono text-ink">cadrecover score solution.py --task {run.challenge_id}</code>
        {" · "}
        <Link href="/runs" className="text-ink underline-offset-2 hover:underline">
          all runs
        </Link>
      </p>
    </div>
  );
}
