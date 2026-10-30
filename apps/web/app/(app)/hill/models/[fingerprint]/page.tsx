import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { Empty, Page, Skeleton } from "@/components/app/page-parts";
import { BackendPending, FamilyBars, SampleBanner, SourceBadge, StatusBadge, TaskStrip, q1 } from "@/components/hill/ui";
import { shortKey, when } from "@/lib/format";
import { getModel, href, isSample } from "@/lib/hill";

export const metadata: Metadata = { title: "Model | CADRecover" };

type Props = { params: Promise<{ fingerprint: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> };

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1 border-t border-line py-3 sm:grid-cols-[10rem_minmax(0,1fr)] sm:gap-4">
      <dt className="text-[13px] text-ink-soft">{label}</dt>
      <dd className="min-w-0 break-all font-mono text-[13px]">{children}</dd>
    </div>
  );
}

async function Body({ params, searchParams }: Props) {
  const [{ fingerprint }, sp] = await Promise.all([params, searchParams]);
  const sample = isSample(sp);
  const res = await getModel(fingerprint, { sample });
  if (!res.ok && res.error === "not found") return <Empty title="No such model">{fingerprint} has not entered the hill.</Empty>;
  if (!res.ok) return <BackendPending error={res.error} samplePath="/hill/leaderboard?sample=1" />;
  const { model: m, matches, events } = res.data;

  return (
    <>
      {sample && <SampleBanner live={`/hill/models/${fingerprint}`} />}
      <div className="grid gap-10 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <section aria-label="Model card">
          <p className="flex flex-wrap items-center gap-3">
            <StatusBadge m={m} />
            <SourceBadge m={m} />
          </p>
          <h1 className="mt-3 break-words text-3xl font-medium tracking-[-0.03em] md:text-[2.6rem] md:leading-[1.05]">{m.name}</h1>
          {m.reject_reason && <p className="mt-3 text-[15px] text-fail">{m.reject_reason}</p>}

          <div className="mt-8 grid gap-8 sm:grid-cols-[auto_minmax(0,1fr)]">
            <div>
              <p className="text-[13px] text-ink-soft">mean score</p>
              <p className="font-mono text-6xl tracking-[-0.05em]">{q1(m.mean_quality)}</p>
              <p className="mt-2 font-mono text-[12px] text-ink-soft">
                {m.matches_won} won · {m.matches_lost} lost
              </p>
            </div>
            <div className="grid content-start gap-4">
              <FamilyBars per={m.per_family} />
              {m.recent_tasks.length > 0 && <TaskStrip tasks={m.recent_tasks} size="md" />}
            </div>
          </div>

          <dl className="mt-10 border-b border-line">
            <Field label="fingerprint">{m.fingerprint}</Field>
            <Field label="repository">
              {m.repo ? (
                m.hf_url ? (
                  <a href={m.hf_url} target="_blank" rel="noreferrer" className="underline-offset-2 hover:underline">
                    {m.repo}
                  </a>
                ) : (
                  m.repo
                )
              ) : (
                "Chutes catalog model (entered by the validator)"
              )}
            </Field>
            {m.revision && <Field label="revision">{m.revision}</Field>}
            {m.base_model && <Field label="base model">{m.base_model}</Field>}
            {m.hotkey && (
              <Field label="miner">
                uid {m.uid ?? "?"} · {shortKey(m.hotkey)}
              </Field>
            )}
            <Field label="committed">{m.commit_block ? `block ${m.commit_block.toLocaleString("en-US")}` : when(m.submitted_at)}</Field>
            {m.fee && (
              <Field label="evaluation fee">
                {m.fee.amount_tao} TAO{m.fee.simulated && " (simulated on this network)"}
              </Field>
            )}
            <Field label="runs on">
              {m.chutes_url ? (
                <a href={m.chutes_url} target="_blank" rel="noreferrer" className="underline-offset-2 hover:underline">
                  Chutes{m.tee && ", TEE"}
                </a>
              ) : (
                "deployed per match"
              )}
            </Field>
          </dl>
        </section>

        <section aria-label="History" className="grid content-start gap-10">
          <div>
            <p className="mb-4 text-[15px] font-medium">Status history</p>
            <ol className="relative border-l border-line pl-5">
              {events.map((e, i) => (
                <li key={i} className="relative pb-5 last:pb-0">
                  <span
                    aria-hidden="true"
                    className={`absolute -left-[25px] top-1.5 h-2 w-2 rounded-[1px] ${
                      e.status === "champion" ? "bg-accent" : e.status === "rejected" ? "bg-fail" : "bg-ink/40"
                    }`}
                  />
                  <p className="flex flex-wrap items-baseline gap-x-3 font-mono text-[13px]">
                    <span className="w-24">{e.status}</span>
                    <span className="text-ink-soft">{e.block != null ? `block ${e.block}` : when(e.at)}</span>
                  </p>
                  {e.detail && <p className="mt-0.5 text-[13px] text-ink-soft">{e.detail}</p>}
                </li>
              ))}
            </ol>
          </div>
          <div>
            <p className="mb-3 text-[15px] font-medium">Matches</p>
            {matches.length === 0 ? (
              <p className="text-[14px] text-ink-soft">None yet.</p>
            ) : (
              <ul className="border-b border-line">
                {matches.map((x) => (
                  <li key={x.match_id} className="border-t border-line">
                    <Link
                      href={href(`/hill/match/${x.match_id}`, sample)}
                      className="flex items-baseline justify-between gap-3 py-3 text-[14px] hover:text-accent"
                    >
                      <span className="truncate">
                        {x.challenger.name} vs {x.champion?.name ?? "empty hill"}
                      </span>
                      <span className="shrink-0 font-mono text-[12px] text-ink-soft">{x.verdict ?? `${x.tasks_done}/${x.tasks_total}`}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      </div>
    </>
  );
}

export default function ModelPage(props: Props) {
  return (
    <Page>
      <Suspense fallback={<Skeleton rows={6} />}>
        <Body {...props} />
      </Suspense>
    </Page>
  );
}
