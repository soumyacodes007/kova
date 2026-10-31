import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { Empty, Page, PageHead, Skeleton } from "@/components/app/page-parts";
import { BackendPending, FamilyBars, SampleBanner, SourceBadge, StatusBadge, TaskStrip, q1, shortRev } from "@/components/hill/ui";
import { getHill, getModels, href, isSample } from "@/lib/hill";
import type { Model } from "@/lib/hill-types";

export const metadata: Metadata = { title: "Track B leaderboard | CADRecover" };

type SP = Promise<Record<string, string | string[] | undefined>>;

const ORDER: Record<Model["status"], number> = {
  champion: 0, evaluating: 1, scored: 2, defeated: 3, queued: 4, prechecked: 5, submitted: 6, rejected: 7,
};

function ScoreCell({ m, line }: { m: Model; line: number | null }) {
  const v = m.mean_quality;
  return (
    <div>
      <p className={`font-mono text-[26px] leading-none tracking-[-0.03em] ${m.status === "champion" ? "text-ink" : v == null ? "text-ink-soft" : ""}`}>
        {q1(v)}
      </p>
      <div className="relative mt-3 h-2.5" aria-hidden="true">
        {v != null && (
          <span className={`absolute left-0 top-[3px] h-1 rounded-sm ${m.status === "champion" ? "bg-accent" : "bg-ink/55"}`} style={{ width: `${v}%` }} />
        )}
        {line != null && <span className="absolute top-0 h-2.5 w-[2px] bg-accent" style={{ left: `${line}%` }} />}
      </div>
    </div>
  );
}

function Row({ m, rank, line, sample, linked = true }: { m: Model; rank: number | null; line: number | null; sample: boolean; linked?: boolean }) {
  const champion = m.status === "champion";
  return (
    <li
      className={`grid grid-cols-[2.25rem_minmax(0,1fr)] gap-x-4 gap-y-4 border-t py-6 lg:grid-cols-[2.25rem_minmax(0,1.6fr)_9rem_minmax(0,1fr)_9.5rem_7rem] lg:items-center ${
        champion ? "border-ink" : "border-line"
      }`}
    >
      <span className={`font-mono text-2xl tracking-[-0.03em] ${champion ? "text-accent" : "text-ink-soft"}`}>{rank ?? "·"}</span>
      <div className="min-w-0">
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
          {linked ? (
            <Link href={href(`/hill/models/${m.fingerprint}`, sample)} className="truncate text-[17px] font-medium hover:text-accent">
              {m.name}
            </Link>
          ) : (
            <span className="truncate text-[17px] font-medium">{m.name}</span>
          )}
          <StatusBadge m={m} />
        </p>
        <p className="mt-1.5 truncate font-mono text-[11.5px] text-ink-soft">
          {m.repo ? `${m.repo}@${shortRev(m.revision)}` : "Chutes catalog model"}
          {m.base_model && ` · from ${m.base_model}`}
        </p>
        <div className="mt-2.5 flex flex-wrap items-center gap-3">
          <SourceBadge m={m} />
          {m.hf_url && (
            <a href={m.hf_url} target="_blank" rel="noreferrer" className="text-[12.5px] underline-offset-2 hover:underline">
              Hugging Face
            </a>
          )}
          {m.chutes_url && (
            <a href={m.chutes_url} target="_blank" rel="noreferrer" className="text-[12.5px] underline-offset-2 hover:underline">
              Chutes
            </a>
          )}
        </div>
        {m.reject_reason && <p className="mt-2 text-[13px] text-fail">{m.reject_reason}</p>}
      </div>
      <div className="col-span-2 lg:col-span-1">
        <ScoreCell m={m} line={line} />
      </div>
      <div className="col-span-2 lg:col-span-1">
        <FamilyBars per={m.per_family} />
      </div>
      <div className="col-span-2 grid gap-2 lg:col-span-1">
        {m.recent_tasks.length ? <TaskStrip tasks={m.recent_tasks} /> : <span className="text-[12px] text-ink-soft">no match yet</span>}
        <span className="font-mono text-[11.5px] text-ink-soft">
          critical {m.critical_pass_rate == null ? "n/a" : `${Math.round(m.critical_pass_rate * 100)}%`} · edits{" "}
          {m.edit_pass_rate == null ? "n/a" : `${Math.round(m.edit_pass_rate * 100)}%`}
        </span>
      </div>
      <div className="col-span-2 grid gap-1 font-mono text-[12px] lg:col-span-1 lg:text-right">
        <span>
          {m.matches_won} won · {m.matches_lost} lost
        </span>
        <span className="text-ink-soft">{m.mean_latency_s == null ? "n/a" : `${m.mean_latency_s.toFixed(1)}s per drawing`}</span>
      </div>
    </li>
  );
}

async function Board({ searchParams }: { searchParams: SP }) {
  const sample = isSample(await searchParams);
  const [models, hill, local] = await Promise.all([
    getModels({ sample }),
    getHill({ sample }),
    sample ? Promise.resolve(null) : getModels({ sample, network: "local" }),
  ]);
  if (!models.ok) return <BackendPending error={models.error} samplePath="/hill/leaderboard?sample=1" />;
  if (!models.data.length) return <Empty title="No models yet">The first catalog model or miner submission appears here.</Empty>;

  const rows = [...models.data].sort((a, b) => ORDER[a.status] - ORDER[b.status] || (b.mean_quality ?? -1) - (a.mean_quality ?? -1));
  const margin = hill.ok ? hill.data.margin : 0;
  const champ = rows.find((m) => m.status === "champion");
  const line = champ?.mean_quality != null ? Math.min(100, champ.mean_quality + margin) : null;
  let rank = 0;

  return (
    <>
      {sample && <SampleBanner live="/hill/leaderboard" />}
      <div className="mb-6 flex flex-wrap items-center gap-x-8 gap-y-3 text-[13px] text-ink-soft">
        <span className="flex items-center gap-2">
          <span aria-hidden="true" className="h-3 w-[2px] bg-accent" />
          {line != null ? `${line.toFixed(1)}: score to take the hill (champion + ${margin})` : "no champion yet"}
        </span>
        <span className="flex items-center gap-2">
          <TaskStrip tasks={[100, 50, 0, null]} /> one square per drawing in the latest match
        </span>
      </div>
      <div className="hidden grid-cols-[2.25rem_minmax(0,1.6fr)_9rem_minmax(0,1fr)_9.5rem_7rem] gap-x-4 pb-3 text-[12.5px] text-ink-soft lg:grid">
        <span>#</span>
        <span>Model</span>
        <span>Mean score</span>
        <span>By family</span>
        <span>Latest match</span>
        <span className="text-right">Record</span>
      </div>
      <ul className="border-b border-line">
        {rows.map((m) => {
          const ranked = m.mean_quality != null && m.status !== "rejected";
          return <Row key={m.fingerprint} m={m} rank={ranked ? ++rank : null} line={line} sample={sample} />;
        })}
      </ul>
      {local?.ok && local.data.length > 0 && <LocalRun models={local.data} margin={margin} />}
    </>
  );
}

/** The localnet run: same harness and real Chutes inference, on a local chain. Never mixed into the standings above. */
function LocalRun({ models, margin }: { models: Model[]; margin: number }) {
  const rows = [...models].sort((a, b) => ORDER[a.status] - ORDER[b.status] || (b.mean_quality ?? -1) - (a.mean_quality ?? -1));
  const champ = rows.find((m) => m.status === "champion");
  const line = champ?.mean_quality != null ? Math.min(100, champ.mean_quality + margin) : null;
  let rank = 0;
  return (
    <section aria-labelledby="local-run" className="mt-16">
      <h2 id="local-run" className="text-2xl font-medium tracking-[-0.02em]">
        Localnet run
      </h2>
      <p className="mt-2 max-w-[70ch] text-[14px] leading-relaxed text-ink-soft">
        The same catalog models, harness and real Chutes inference, played on a local Bittensor chain before the
        testnet run. Its champion and weights are local only; the standings above are testnet 605.
      </p>
      <ul className="mt-6 border-b border-line">
        {rows.map((m) => {
          const ranked = m.mean_quality != null && m.status !== "rejected";
          return <Row key={m.fingerprint} m={m} rank={ranked ? ++rank : null} line={line} sample={false} linked={false} />;
        })}
      </ul>
    </section>
  );
}

export default function HillLeaderboardPage({ searchParams }: { searchParams: SP }) {
  return (
    <Page>
      <PageHead title="Leaderboard">
        Every model that has entered the hill, champion first. Scores are means over hidden drawings, each rebuilt at
        the drawing&apos;s values and three hidden edits.
      </PageHead>
      <Suspense fallback={<Skeleton rows={6} />}>
        <Board searchParams={searchParams} />
      </Suspense>
    </Page>
  );
}
