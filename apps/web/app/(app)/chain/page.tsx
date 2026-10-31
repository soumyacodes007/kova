import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { Badge, Bar, Empty, Offline, Page, PageHead, Skeleton } from "@/components/app/page-parts";
import { api, type Audit, type Commitment, type EventOut, type WeightBatch } from "@/lib/api";
import { blockUrl, extrinsicBlock } from "@/lib/explorer";
import { q, shortHash, shortKey, when } from "@/lib/format";

export const metadata: Metadata = { title: "Chain | CADRecover" };

const STATE_TONE: Record<string, "accent" | "plain" | "fail" | "ink"> = {
  revealed: "accent",
  committed: "ink",
  submitted: "ink",
  proposed: "plain",
  failed: "fail",
  skipped_no_qualifier: "plain",
};

function SectionHead({ id, title, children }: { id: string; title: string; children?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-baseline justify-between gap-3">
      <h2 id={id} className="text-2xl font-medium tracking-[-0.02em]">
        {title}
      </h2>
      {children && <p className="text-[13px] text-ink-soft">{children}</p>}
    </div>
  );
}

function ExplorerLink({ href, children }: { href: string | null; children: React.ReactNode }) {
  if (!href) return <>{children}</>;
  return (
    <a href={href} target="_blank" rel="noreferrer" className="text-ink underline decoration-accent underline-offset-2 hover:text-accent">
      {children}
    </a>
  );
}

const TX_LABEL: Record<string, string> = {
  transfer: "Fund the miner's coldkey",
  register: "Register the miner (burned registration)",
  serve_axon: "Publish the miner's endpoint",
  hill_commit: "Track B: champion weight commit",
  trackA_commit: "Track A: round weight commit",
};

type ChainTx = {
  network: string;
  netuid: number;
  what: string;
  label?: string;
  extrinsic_id: string;
  extrinsic_hash: string;
  block: number;
  block_hash: string;
  signer: string;
  call: string;
};

async function Transactions() {
  const res = await api<{ events: EventOut[] }>("/v1/events?kind=chain.tx&limit=100");
  if (!res.ok) return <Offline error={res.error} />;
  const txs = res.data.events.map((e) => e.payload as unknown as ChainTx);
  if (!txs.length) return <Empty title="No recorded transactions yet" />;
  return (
    <div className="overflow-x-auto rounded-md border border-line">
      <table className="w-full min-w-[760px] text-[13px]">
        <thead>
          <tr className="border-b border-line text-left text-ink-soft">
            <th className="px-4 py-2.5 font-normal">what</th>
            <th className="px-4 py-2.5 font-normal">call</th>
            <th className="px-4 py-2.5 font-normal">extrinsic hash</th>
            <th className="px-4 py-2.5 text-right font-normal">block</th>
          </tr>
        </thead>
        <tbody>
          {txs.map((t) => (
            <tr key={t.extrinsic_hash} className="border-b border-line last:border-0 align-top">
              <td className="px-4 py-3">
                {t.label ?? TX_LABEL[t.what] ?? t.what}
                <span className="mt-0.5 block font-mono text-[11.5px] text-ink-soft">
                  {t.network} netuid {t.netuid} · signer {shortKey(t.signer)}
                </span>
              </td>
              <td className="px-4 py-3 font-mono text-[12px]">{t.call}</td>
              <td className="px-4 py-3 font-mono text-[12px]">
                <span className="break-all">
                  <ExplorerLink href={blockUrl(t.network, t.block)}>{t.extrinsic_hash}</ExplorerLink>
                </span>
                <span className="mt-0.5 block text-[11.5px] text-ink-soft">
                  extrinsic <ExplorerLink href={blockUrl(t.network, t.block)}>{t.extrinsic_id}</ExplorerLink>
                </span>
              </td>
              <td className="px-4 py-3 text-right font-mono text-[12px]">
                <ExplorerLink href={blockUrl(t.network, t.block)}>{t.block.toLocaleString("en-US")}</ExplorerLink>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function BatchCard({ b }: { b: WeightBatch }) {
  const weights = Object.entries(b.weights).sort((x, y) => y[1] - x[1]);
  return (
    <article className="grid gap-6 border-t border-line py-7 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
      <div className="min-w-0">
        <p className="flex flex-wrap items-center gap-3">
          <span className="font-mono text-[15px]">{b.batch_id}</span>
          {b.latest_state && <Badge tone={STATE_TONE[b.latest_state] ?? "plain"}>{b.latest_state}</Badge>}
        </p>
        <p className="mt-1.5 text-[13px] text-ink-soft">
          {b.network} netuid {b.netuid} · {when(b.created_at)}
          {b.run_id && (
            <>
              {" "}
              ·{" "}
              <Link href={`/arena/${b.run_id}`} className="text-ink underline-offset-2 hover:underline">
                {b.run_id}
              </Link>
            </>
          )}
        </p>
        {weights.length ? (
          <ul className="mt-5 grid gap-2.5">
            {weights.map(([uid, w]) => (
              <li key={uid} className="grid grid-cols-[3.5rem_minmax(0,1fr)_4rem] items-center gap-3 font-mono text-[12.5px]">
                <span className="text-ink-soft">uid {uid}</span>
                <Bar value={w * 100} />
                <span className="text-right">{w.toFixed(3)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-5 text-[13px] text-ink-soft">No miner cleared the floor, so no weights were set.</p>
        )}
      </div>

      <ol className="relative grid gap-0 border-l border-line pl-5" aria-label="Receipts">
        {b.receipts.map((r) => (
          <li key={r.receipt_id} className="relative pb-4 last:pb-0">
            <span
              aria-hidden="true"
              className={`absolute -left-[25px] top-1.5 h-2 w-2 rounded-[1px] ${r.state === "revealed" ? "bg-accent" : r.state === "failed" ? "bg-fail" : "bg-ink/40"}`}
            />
            <p className="flex flex-wrap items-baseline gap-x-3 font-mono text-[13px]">
              <span className="w-24">{r.state}</span>
              <span className="text-ink">
                {r.block != null ? <ExplorerLink href={blockUrl(b.network, r.block)}>block {r.block}</ExplorerLink> : "no block"}
              </span>
              <span className="text-ink-soft">{new Date(r.at).toISOString().slice(11, 19)} UTC</span>
            </p>
            {r.extrinsic && (
              <p className="mt-0.5 font-mono text-[11.5px] text-ink-soft">
                extrinsic{" "}
                <ExplorerLink href={blockUrl(b.network, extrinsicBlock(r.extrinsic) ?? r.extrinsic)}>{r.extrinsic}</ExplorerLink>
              </p>
            )}
            {r.readback && (
              <p className="mt-0.5 font-mono text-[11.5px] text-ink-soft">
                read back{" "}
                {Object.entries(r.readback)
                  .map(([u, w]) => `uid ${u}: ${Number(w).toFixed(3)}`)
                  .join(", ")}
              </p>
            )}
            {r.error && <p className="mt-0.5 font-mono text-[11.5px] text-fail">{r.error}</p>}
          </li>
        ))}
      </ol>
    </article>
  );
}

async function Weights() {
  const res = await api<WeightBatch[]>("/v1/weights?limit=20");
  if (!res.ok) return <Offline error={res.error} />;
  if (!res.data.length) return <Empty title="No weight batches yet" />;
  return (
    <div className="border-b border-line">
      {res.data.map((b) => (
        <BatchCard key={b.batch_id} b={b} />
      ))}
    </div>
  );
}

async function Commitments() {
  const res = await api<Commitment[]>("/v1/commitments");
  if (!res.ok) return <Offline error={res.error} />;
  if (!res.data.length) return <Empty title="No engine commitments yet" />;
  return (
    <ul className="grid gap-3 md:grid-cols-2">
      {res.data.map((c) => (
        <li key={`${c.hotkey}-${c.block}`} className="rounded-md border border-line p-5">
          <p className="flex items-baseline justify-between gap-3">
            <span className="font-mono text-[14px]">
              <span className="text-ink-soft">uid {c.uid ?? "?"}</span> {c.label ?? shortKey(c.hotkey)}
            </span>
            <span className="font-mono text-[12.5px] text-ink-soft">block {c.block}</span>
          </p>
          <p className="mt-3 break-all font-mono text-[12px] leading-relaxed text-ink">{c.engine_digest}</p>
          <p className="mt-2 font-mono text-[11.5px] text-ink-soft">
            {c.strategy_version} · signed by {shortKey(c.hotkey)}
          </p>
        </li>
      ))}
    </ul>
  );
}

async function Audits() {
  const res = await api<Audit[]>("/v1/audits?limit=20");
  if (!res.ok) return <Offline error={res.error} />;
  if (!res.data.length) return <Empty title="No audits yet" />;
  return (
    <ul className="border-b border-line">
      {res.data.map((a) => {
        const pass = a.verdict === "pass";
        return (
          <li
            key={a.audit_run}
            className="grid gap-4 border-t border-line py-5 md:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,1fr)] md:items-center"
          >
            <div className="min-w-0">
              <p className="flex flex-wrap items-center gap-3">
                <Badge tone={pass ? "plain" : "fail"}>{a.verdict.toUpperCase()}</Badge>
                <span className="font-mono text-[14px]">
                  <span className="text-ink-soft">uid {a.uid ?? "?"}</span> {a.label ?? shortKey(a.hotkey)}
                </span>
              </p>
              <p className="mt-1.5 font-mono text-[11.5px] text-ink-soft">
                engine {shortHash(a.engine_digest)} · {a.block != null ? `block ${a.block}` : when(a.at)}
              </p>
              {a.reason && <p className="mt-1 text-[13px] text-fail">{a.reason}</p>}
            </div>
            <div className="grid gap-2 font-mono text-[12.5px]">
              {[
                ["live", a.live_mean, "muted"],
                ["audit", a.audit_mean, pass ? "accent" : "muted"],
              ].map(([k, v, tone]) => (
                <div key={k as string} className="grid grid-cols-[3rem_minmax(0,1fr)_3.5rem] items-center gap-3">
                  <span className="text-ink-soft">{k}</span>
                  <Bar value={(v as number | null) ?? 0} tone={tone as "accent" | "muted"} />
                  <span className="text-right">{q(v as number | null)}</span>
                </div>
              ))}
            </div>
            <p className="font-mono text-[12px] text-ink-soft md:text-right">
              tasks {a.tasks.map((t) => (t.quality == null ? "err" : Math.round(t.quality))).join(", ")}
              <span className="block">pass if within {a.margin} points</span>
            </p>
          </li>
        );
      })}
    </ul>
  );
}

export default function ChainPage() {
  return (
    <Page>
      <PageHead title="Chain">
        Everything the validator wrote to the chain, with the block it landed in: weight batches and their receipts,
        each miner&apos;s committed engine hash, and the audits that re-ran those engines offline.
      </PageHead>

      <section aria-labelledby="transactions" className="mb-20">
        <SectionHead id="transactions" title="Transactions">every extrinsic read back from the chain; block opens the explorer</SectionHead>
        <Suspense fallback={<Skeleton rows={3} />}>
          <Transactions />
        </Suspense>
      </section>

      <section aria-labelledby="weights" className="mb-20">
        <SectionHead id="weights" title="Weight batches">proposed, then committed or submitted, then read back</SectionHead>
        <Suspense fallback={<Skeleton rows={3} />}>
          <Weights />
        </Suspense>
      </section>

      <section aria-labelledby="commitments" className="mb-20">
        <SectionHead id="commitments" title="Engine commitments">the Docker image each miner signed on chain</SectionHead>
        <Suspense fallback={<Skeleton rows={2} />}>
          <Commitments />
        </Suspense>
      </section>

      <section aria-labelledby="audits">
        <SectionHead id="audits" title="Audits">committed engine re-run on fresh hidden tasks, no network</SectionHead>
        <Suspense fallback={<Skeleton rows={3} />}>
          <Audits />
        </Suspense>
      </section>
    </Page>
  );
}
