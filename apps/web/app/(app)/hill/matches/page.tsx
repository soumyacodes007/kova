import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { Badge, Empty, Page, PageHead, Skeleton } from "@/components/app/page-parts";
import { BackendPending, SampleBanner, q1 } from "@/components/hill/ui";
import { when } from "@/lib/format";
import { getMatches, href, isSample } from "@/lib/hill";

export const metadata: Metadata = { title: "Matches | CADRecover" };

type SP = Promise<Record<string, string | string[] | undefined>>;

async function List({ searchParams }: { searchParams: SP }) {
  const sample = isSample(await searchParams);
  const res = await getMatches({ sample });
  if (!res.ok) return <BackendPending error={res.error} samplePath="/hill/matches?sample=1" />;
  if (!res.data.length) return <Empty title="No matches yet">A match starts when the first challenger clears its pre-check.</Empty>;

  return (
    <>
      {sample && <SampleBanner live="/hill/matches" />}
      <ul className="border-b border-line">
        {res.data.map((m) => (
          <li key={m.match_id} className="border-t border-line">
            <Link
              href={href(`/hill/match/${m.match_id}`, sample)}
              className="grid gap-4 py-6 transition-colors hover:bg-surface/60 md:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)_10rem] md:items-center md:px-3"
            >
              <div className="min-w-0">
                <p className="flex flex-wrap items-center gap-3">
                  <span className="font-mono text-[13px] text-ink-soft">{m.match_id}</span>
                  {m.status === "running" ? (
                    <Badge tone="accent">
                      live {m.tasks_done}/{m.tasks_total}
                    </Badge>
                  ) : (
                    <Badge tone={m.verdict === "crowned" ? "ink" : "plain"}>{m.verdict ?? "decided"}</Badge>
                  )}
                </p>
                <p className="mt-2 text-[18px] font-medium tracking-[-0.01em]">
                  {m.challenger.name} <span className="font-normal text-ink-soft">vs</span> {m.champion?.name ?? "empty hill"}
                </p>
                <p className="mt-1 font-mono text-[11.5px] text-ink-soft">
                  {when(m.started_at)} · {m.seed ? `seed ${m.seed.value} (block ${m.seed.block_hash}, drand ${m.seed.drand_round})` : "seed hidden until match ends"}
                </p>
              </div>
              <p className="font-mono text-[14px]">
                <span className="text-accent">{q1(m.challenger_mean)}</span>
                <span className="text-ink-soft"> vs </span>
                {q1(m.champion_mean)}
                <span className="block text-[11.5px] text-ink-soft">needs +{m.margin} to take the hill</span>
              </p>
              <p className="text-[13px] md:text-right">
                {m.decided_block != null ? (
                  <span className="font-mono">block {m.decided_block.toLocaleString("en-US")}</span>
                ) : (
                  <span className="text-ink-soft">deciding</span>
                )}
              </p>
            </Link>
          </li>
        ))}
      </ul>
    </>
  );
}

export default function MatchesPage({ searchParams }: { searchParams: SP }) {
  return (
    <Page>
      <PageHead title="Matches">
        Each challenger meets the champion on the same hidden drawings, drawn from a seed nobody knows in advance: a
        future block hash plus a drand round.
      </PageHead>
      <Suspense fallback={<Skeleton rows={4} />}>
        <List searchParams={searchParams} />
      </Suspense>
    </Page>
  );
}
