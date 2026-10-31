import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { HillLive } from "@/components/hill/live";
import { Page, Skeleton } from "@/components/app/page-parts";
import { BackendPending, DethroneMeter, FamilyBars, FAMILY_LABEL, SampleBanner, Sheet, SourceBadge, TaskStrip, q1, shortRev } from "@/components/hill/ui";
import { getHill, href, isSample } from "@/lib/hill";
import { when } from "@/lib/format";

export const metadata: Metadata = { title: "The hill | CADRecover" };

type SP = Promise<Record<string, string | string[] | undefined>>;

async function HillBody({ searchParams }: { searchParams: SP }) {
  const sample = isSample(await searchParams);
  const res = await getHill({ sample });
  if (!res.ok) return <BackendPending error={res.error} samplePath="/hill?sample=1" />;
  const hill = res.data;
  const champ = hill.champion;
  const live = hill.live_match;
  const lineage = [...hill.lineage].reverse();

  return (
    <>
      {sample && <SampleBanner live="/hill" />}
      <HillLive active={!sample} />
      <Sheet
        footer={
          <>
            <span>title: the hill, drawing to CAD</span>
            <span>margin {hill.margin} points</span>
            <span>{hill.tasks_per_match} hidden drawings per match</span>
            <span>families: {hill.families.map((f) => FAMILY_LABEL[f]).join(", ")}</span>
          </>
        }
      >
        <div className="grid gap-8 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
          <section aria-label="Current champion">
            <p className="font-mono text-[12px] text-ink-soft">current champion</p>
            {champ ? (
              <>
                <h1 className="mt-2 break-words text-4xl font-medium tracking-[-0.035em] md:text-[3.4rem] md:leading-[1.02]">
                  <Link href={href(`/hill/models/${champ.fingerprint}`, sample)} className="hover:text-accent">
                    {champ.name}
                  </Link>
                </h1>
                <div className="mt-4 flex flex-wrap items-center gap-3">
                  <SourceBadge m={champ} />
                  <span className="font-mono text-[12px] text-ink-soft">
                    {champ.repo ? `${champ.repo}@${shortRev(champ.revision)}` : "catalog model"} · fp {champ.fingerprint.slice(0, 10)}
                  </span>
                </div>
                <div className="mt-8 grid gap-6 sm:grid-cols-3">
                  <div>
                    <p className="text-[13px] text-ink-soft">mean score</p>
                    <p className="font-mono text-5xl tracking-[-0.04em]">{q1(champ.mean_quality)}</p>
                  </div>
                  <div>
                    <p className="text-[13px] text-ink-soft">critical features right</p>
                    <p className="font-mono text-3xl tracking-[-0.03em]">
                      {champ.critical_pass_rate == null ? "n/a" : `${Math.round(champ.critical_pass_rate * 100)}%`}
                    </p>
                  </div>
                  <div>
                    <p className="text-[13px] text-ink-soft">matches won / lost</p>
                    <p className="font-mono text-3xl tracking-[-0.03em]">
                      {champ.matches_won} / {champ.matches_lost}
                    </p>
                  </div>
                </div>
                {champ.mean_quality != null && (
                  <div className="mt-8 max-w-xl">
                    <DethroneMeter score={champ.mean_quality} margin={hill.margin} />
                  </div>
                )}
                <div className="mt-7 grid gap-6 sm:grid-cols-2">
                  <div>
                    <p className="mb-2 text-[13px] text-ink-soft">latest match, task by task</p>
                    <TaskStrip tasks={champ.recent_tasks} size="md" />
                  </div>
                  <div>
                    <p className="mb-2 text-[13px] text-ink-soft">by part family</p>
                    <FamilyBars per={champ.per_family} />
                  </div>
                </div>
              </>
            ) : (
              <p className="mt-3 max-w-[50ch] text-[16px] leading-relaxed text-ink-soft">
                No champion yet. The first model to score at least 50 takes the hill.
              </p>
            )}
          </section>

          <section aria-label="Revision table: every champion so far" className="self-start">
            <table className="w-full border border-ink font-mono text-[12.5px]">
              <caption className="pb-2 text-left text-[12px] text-ink-soft">revisions: every champion so far</caption>
              <thead>
                <tr className="border-b border-ink text-left">
                  <th className="w-10 border-r border-ink px-2 py-1.5 font-normal">rev</th>
                  <th className="border-r border-ink px-2 py-1.5 font-normal">champion</th>
                  <th className="w-14 border-r border-ink px-2 py-1.5 text-right font-normal">score</th>
                  <th className="w-20 px-2 py-1.5 text-right font-normal">block</th>
                </tr>
              </thead>
              <tbody>
                {lineage.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-2 py-3 text-ink-soft">
                      none yet
                    </td>
                  </tr>
                )}
                {lineage.map((r, i) => (
                  <tr key={r.rev} className={`border-b border-line last:border-0 ${i === 0 ? "text-ink" : "text-ink-soft"}`}>
                    <td className="border-r border-line px-2 py-1.5">{r.rev}</td>
                    <td className="max-w-0 truncate border-r border-line px-2 py-1.5">
                      <Link href={href(`/hill/models/${r.fingerprint}`, sample)} className="hover:text-accent">
                        {r.name}
                      </Link>
                    </td>
                    <td className="border-r border-line px-2 py-1.5 text-right">{r.score.toFixed(1)}</td>
                    <td className="px-2 py-1.5 text-right">{r.crowned_at_block.toLocaleString("en-US")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </div>
      </Sheet>

      <div className="mt-6 grid gap-4 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <section aria-label="Live match" className="rounded-md bg-ink p-6 text-paper md:p-7">
          {live ? (
            <>
              <p className="flex flex-wrap items-center justify-between gap-3 font-mono text-[12px]">
                <span className="text-accent">{live.status === "running" ? "match in progress" : "latest match"}</span>
                <span className="text-[#a8a8a3]">
                  {live.status === "running" && live.tasks_done < live.tasks_total ? `scoring drawing ${live.tasks_done + 1} · ` : ""}
                  {live.tasks_done}/{live.tasks_total} drawings · seed {live.seed?.value ?? "hidden until match ends"}
                </span>
              </p>
              <div className="mt-4 grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-end gap-4">
                <div className="min-w-0">
                  <p className="text-[12.5px] text-[#a8a8a3]">challenger</p>
                  <p className="truncate text-xl font-medium">{live.challenger.name}</p>
                  <p className="font-mono text-4xl tracking-[-0.04em] text-accent">{live.challenger_mean == null ? "..." : q1(live.challenger_mean)}</p>
                </div>
                <span className="pb-2 font-mono text-[13px] text-[#a8a8a3]">vs</span>
                <div className="min-w-0 text-right">
                  <p className="text-[12.5px] text-[#a8a8a3]">champion</p>
                  <p className="truncate text-xl font-medium">{live.champion?.name ?? "none"}</p>
                  <p className="font-mono text-4xl tracking-[-0.04em]">{live.champion_mean == null ? "..." : q1(live.champion_mean)}</p>
                </div>
              </div>
              <div className="mt-5 flex gap-[3px]" aria-label="Match progress">
                {Array.from({ length: live.tasks_total }, (_, i) => (
                  <span key={i} className={`h-1.5 flex-1 rounded-sm ${i < live.tasks_done ? "bg-accent" : "bg-white/15"}`} />
                ))}
              </div>
              <Link
                href={href(`/hill/match/${live.match_id}`, sample)}
                className="mt-6 inline-flex h-10 items-center rounded-md bg-accent px-4 text-[14px] font-medium text-ink transition-colors hover:bg-accent-hover"
              >
                Watch the match
              </Link>
            </>
          ) : (
            <p className="text-[15px] text-[#c9c9c4]">No match running. The next challenger in the queue starts one.</p>
          )}
        </section>

        <section aria-label="Queue" className="rounded-md border border-line p-6">
          <p className="text-[14px] font-medium">Waiting to challenge</p>
          {hill.queue.length === 0 ? (
            <p className="mt-2 text-[14px] text-ink-soft">The queue is empty.</p>
          ) : (
            <ol className="mt-3 grid gap-2.5">
              {hill.queue.map((m, i) => (
                <li key={m.fingerprint} className="flex items-baseline justify-between gap-3 text-[14px]">
                  <Link href={href(`/hill/models/${m.fingerprint}`, sample)} className="truncate hover:text-accent">
                    <span className="mr-2 font-mono text-[12px] text-ink-soft">{i + 1}</span>
                    {m.name}
                  </Link>
                  <span className="shrink-0 font-mono text-[12px] text-ink-soft">
                    {m.commit_block ? `block ${m.commit_block}` : when(m.submitted_at)}
                  </span>
                </li>
              ))}
            </ol>
          )}
          <Link href={href("/hill/leaderboard", sample)} className="mt-5 inline-block text-[14px] underline-offset-2 hover:underline">
            Full leaderboard
          </Link>
        </section>
      </div>
    </>
  );
}

export default function HillPage({ searchParams }: { searchParams: SP }) {
  return (
    <Page>
      <Suspense fallback={<Skeleton rows={6} />}>
        <HillBody searchParams={searchParams} />
      </Suspense>
    </Page>
  );
}
