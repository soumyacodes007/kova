import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { Badge, Bar, Empty, Offline, Page, PageHead, Skeleton } from "@/components/app/page-parts";
import { api, type Leaderboard, type LeaderboardRow } from "@/lib/api";
import { pct, q, shortHash, shortKey } from "@/lib/format";

export const metadata: Metadata = { title: "Leaderboard | CADRecover" };

function AuditBadge({ row }: { row: LeaderboardRow }) {
  if (!row.audit) return <span className="text-[12px] text-ink-soft">not audited</span>;
  const pass = row.audit.verdict === "pass";
  return (
    <span className="flex flex-col items-start gap-1">
      <Badge tone={pass ? "plain" : "fail"}>{pass ? "audit pass" : `audit ${row.audit.verdict}`}</Badge>
      <span className="font-mono text-[11.5px] text-ink-soft">
        {q(row.audit.audit_mean)} vs {q(row.audit.live_mean)}
        {row.audit.block != null && ` · block ${row.audit.block}`}
      </span>
    </span>
  );
}

function Row({ row, floor }: { row: LeaderboardRow; floor: number }) {
  const earns = (row.latest_batch_weight ?? 0) > 0;
  return (
    <li className="grid grid-cols-[2.5rem_minmax(0,1fr)_auto] gap-x-4 gap-y-3 border-t border-line py-5 lg:grid-cols-[2.5rem_minmax(0,1.4fr)_minmax(0,1.2fr)_6rem_6rem_9rem_5rem] lg:items-center">
      <span className="font-mono text-2xl tracking-[-0.03em] text-ink-soft">{row.rank}</span>
      <div className="min-w-0">
        <p className="flex items-baseline gap-2.5">
          <span className="font-mono text-[12px] text-ink-soft">uid {row.uid}</span>
          <span className="truncate font-mono text-[15px]">{row.label ?? shortKey(row.hotkey)}</span>
        </p>
        <p className="mt-1 truncate font-mono text-[11.5px] text-ink-soft" title={row.hotkey}>
          {shortKey(row.hotkey)} · engine {shortHash(row.committed_engine)}
        </p>
      </div>
      <p className="text-right font-mono text-[15px] lg:order-last">
        {(row.latest_batch_weight ?? 0).toFixed(3)}
        <span className="block text-[11.5px] text-ink-soft lg:hidden">weight</span>
      </p>
      <div className="col-span-3 lg:col-span-1">
        <div className="flex items-baseline justify-between gap-3">
          <span className={`font-mono text-xl tracking-[-0.02em] ${row.mean_quality >= floor ? "" : "text-ink-soft"}`}>
            {q(row.mean_quality)}
          </span>
          <span className="text-[12px] text-ink-soft">{row.samples} tasks</span>
        </div>
        <div className="mt-2">
          <Bar value={row.mean_quality} tone={earns ? "accent" : "muted"} />
        </div>
      </div>
      <p className="font-mono text-[14px] max-lg:col-span-1">
        {pct(row.drawing_pass_rate)}
        <span className="block text-[11.5px] text-ink-soft lg:hidden">drawing</span>
      </p>
      <p className="font-mono text-[14px]">
        {pct(row.edit_pass_rate)}
        <span className="block text-[11.5px] text-ink-soft lg:hidden">hidden edits</span>
      </p>
      <div>
        <AuditBadge row={row} />
      </div>
    </li>
  );
}

async function Board() {
  const res = await api<Leaderboard>("/v1/leaderboard");
  if (!res.ok) return <Offline error={res.error} />;
  const lb = res.data;
  if (!lb.rows.length) return <Empty title="No scored miners yet">Run a round with `make demo` and the standings appear here.</Empty>;

  return (
    <>
      <div className="mb-6 flex flex-wrap gap-x-8 gap-y-2 font-mono text-[12.5px] text-ink-soft">
        <span>floor {lb.quality_floor}</span>
        <span>window {lb.window} tasks</span>
        <span>
          latest batch{" "}
          {lb.latest_batch_id ? (
            <Link href="/chain" className="text-ink underline-offset-2 hover:underline">
              {lb.latest_batch_id}
            </Link>
          ) : (
            "none"
          )}
        </span>
      </div>
      <div className="hidden grid-cols-[2.5rem_minmax(0,1.4fr)_minmax(0,1.2fr)_6rem_6rem_9rem_5rem] gap-x-4 pb-3 text-[12.5px] text-ink-soft lg:grid">
        <span>#</span>
        <span>Miner</span>
        <span>Mean score</span>
        <span>Drawing pass</span>
        <span>Edits pass</span>
        <span>Audit</span>
        <span className="text-right">Weight</span>
      </div>
      <ul className="border-b border-line">
        {lb.rows.map((row) => (
          <Row key={`${row.hotkey}-${row.registered_at_block}`} row={row} floor={lb.quality_floor} />
        ))}
      </ul>
    </>
  );
}

export default function LeaderboardPage() {
  return (
    <Page>
      <PageHead title="Leaderboard">
        Rolling mean score over each miner&apos;s recent tasks. Scores under the floor earn nothing, and a failed
        audit zeroes the weight until a clean one. Weight is what the newest batch set on chain.
      </PageHead>
      <Suspense fallback={<Skeleton rows={5} />}>
        <Board />
      </Suspense>
    </Page>
  );
}
