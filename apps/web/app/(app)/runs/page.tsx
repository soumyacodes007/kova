import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { Badge, Empty, Offline, Page, PageHead, Skeleton } from "@/components/app/page-parts";
import { api, type RunSummary } from "@/lib/api";
import { q, when } from "@/lib/format";

export const metadata: Metadata = { title: "Runs | CADRecover" };

const LIVE = new Set(["dispatching", "collecting", "evaluating"]);

async function RunList() {
  const res = await api<RunSummary[]>("/v1/runs?limit=100");
  if (!res.ok) return <Offline error={res.error} />;
  if (!res.data.length) return <Empty title="No rounds yet">Start one with `make demo`.</Empty>;

  return (
    <ul className="border-b border-line">
      {res.data.map((r) => (
        <li key={r.run_id} className="border-t border-line">
          <Link
            href={`/arena/${r.run_id}`}
            className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-6 gap-y-2 py-5 transition-colors hover:bg-surface/60 md:grid-cols-[minmax(0,1.3fr)_7rem_8rem_8rem_8rem] md:items-center md:px-3"
          >
            <div className="min-w-0">
              <p className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <span className="font-mono text-[15px]">{r.run_id}</span>
                <Badge tone={LIVE.has(r.status) ? "accent" : r.status === "aborted" ? "fail" : "plain"}>{r.status}</Badge>
              </p>
              <p className="mt-1 text-[13px] text-ink-soft">
                {r.family ?? "unknown family"} · {when(r.started_at)}
              </p>
            </div>
            <p className="text-right font-mono text-[14px] md:text-left">
              {r.evaluated}/{r.miners}
              <span className="block text-[11.5px] text-ink-soft">evaluated</span>
            </p>
            <p className="font-mono text-[14px]">
              {q(r.best_quality)}
              <span className="block text-[11.5px] text-ink-soft">best{r.best_uid != null && `, uid ${r.best_uid}`}</span>
            </p>
            <p className="font-mono text-[14px]">
              {q(r.mean_quality)}
              <span className="block text-[11.5px] text-ink-soft">mean</span>
            </p>
            <p className="hidden text-right text-[13px] text-ink md:block">Open in arena</p>
          </Link>
        </li>
      ))}
    </ul>
  );
}

export default function RunsPage() {
  return (
    <Page>
      <PageHead title="Runs">
        Every round the validator has played: one new drawing, every miner&apos;s answer, rebuilt and scored at the
        drawing&apos;s values and three hidden edits.
      </PageHead>
      <Suspense fallback={<Skeleton rows={7} />}>
        <RunList />
      </Suspense>
    </Page>
  );
}
